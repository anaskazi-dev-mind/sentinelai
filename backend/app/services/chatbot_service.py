"""
chatbot_service.py
--------------------
Automation module: Chatbot.

Powered by Google's Gemini API. Pulls real, live numbers from the
database and hands them to Gemini as grounded context. Anonymous
visitors are scoped by a browser-generated session_id (instead of a
real user_id) so two different visitors never see each other's
conversation history.
"""

from __future__ import annotations

from google import genai
from google.genai import types
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import ChatMessage, Event, SeverityLevel

settings = get_settings()

# Ordered by preference. If the primary model gets deprecated or removed
# (which has happened with little notice on this API before), the
# service automatically falls back to the next one instead of failing.
CANDIDATE_MODELS = ["gemini-3.1-flash-lite", "gemini-3-flash-preview"]

MAX_HISTORY_MESSAGES = 10
MAX_RECENT_EVENTS_IN_CONTEXT = 8

SYSTEM_PROMPT = """You are SentinelAI's security copilot, embedded in a log-monitoring
and file-security dashboard.

Rules you must follow strictly:
1. Answer ONLY using the SECURITY DATA CONTEXT provided in each message.
   Never invent event counts, file names, or incidents that aren't in the context.
2. If the context doesn't contain enough information to answer, say so plainly
   and suggest what the user could check instead (e.g. "check the Live Feed tab").
3. Be concise and precise -- you're talking to someone monitoring live security
   data, not writing an essay. Prefer short paragraphs or bullet points.
4. When referencing a specific event, mention its severity and, if available,
   which file was involved.
5. You may highlight patterns or trends across the given data, but always stay
   grounded in the provided numbers -- never speculate about causes not
   supported by the context.
"""


def _get_client() -> genai.Client:
    api_key = settings.gemini_api_key
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set. Add it to backend/.env.")
    return genai.Client(api_key=api_key)


def _build_security_context(db: Session) -> str:
    total_events = db.query(func.count(Event.id)).scalar() or 0

    severity_counts = dict(
        db.query(Event.severity, func.count(Event.id)).group_by(Event.severity).all()
    )
    severity_summary = (
        ", ".join(
            f"{sev.value if hasattr(sev, 'value') else sev}: {count}"
            for sev, count in severity_counts.items()
        )
        or "no events recorded yet"
    )

    recent_critical = (
        db.query(Event)
        .filter(Event.severity == SeverityLevel.CRITICAL)
        .order_by(Event.created_at.desc())
        .limit(MAX_RECENT_EVENTS_IN_CONTEXT)
        .all()
    )
    critical_lines = [
        f"- [{e.created_at.isoformat()}] risk={e.risk_score} "
        f"file={e.file_path or 'N/A'} :: {e.raw_message}"
        for e in recent_critical
    ] or ["(none)"]

    avg_risk = db.query(func.avg(Event.risk_score)).scalar()
    avg_risk_str = f"{avg_risk:.1f}" if avg_risk is not None else "N/A"

    return (
        f"Total events recorded: {total_events}\n"
        f"Severity breakdown: {severity_summary}\n"
        f"Average risk score: {avg_risk_str}\n"
        f"Most recent CRITICAL events:\n" + "\n".join(critical_lines)
    )


def _get_recent_history(
    db: Session, user_id: str | None, session_id: str | None
) -> list[dict]:
    """
    Logged-in users are scoped by user_id; anonymous visitors are scoped
    by their browser-generated session_id instead, so two different
    anonymous visitors never see each other's conversation.
    """
    query = db.query(ChatMessage).order_by(ChatMessage.created_at.desc())
    if user_id:
        query = query.filter(ChatMessage.user_id == user_id)
    elif session_id:
        query = query.filter(ChatMessage.session_id == session_id)
    else:
        return []  # no identity at all -- nothing to scope history to

    recent = query.limit(MAX_HISTORY_MESSAGES).all()
    recent.reverse()

    gemini_role = {"user": "user", "assistant": "model"}
    return [
        {"role": gemini_role.get(m.role, "user"), "parts": [{"text": m.content}]}
        for m in recent
    ]


def ask_copilot(
    db: Session,
    message: str,
    user_id: str | None = None,
    session_id: str | None = None,
) -> str:
    user_msg = ChatMessage(
        user_id=user_id, session_id=session_id, role="user", content=message
    )
    db.add(user_msg)
    db.commit()

    history = _get_recent_history(db, user_id, session_id)
    security_context = _build_security_context(db)

    grounded_message = (
        f"SECURITY DATA CONTEXT:\n{security_context}\n\nUSER QUESTION: {message}"
    )
    contents = history[:-1] + [{"role": "user", "parts": [{"text": grounded_message}]}]

    client = _get_client()
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        max_output_tokens=800,
    )

    reply_text = None
    last_error = None
    for model_name in CANDIDATE_MODELS:
        try:
            response = client.models.generate_content(
                model=model_name, contents=contents, config=config
            )
            reply_text = (
                response.text or "I couldn't generate a response -- please try again."
            )
            break
        except genai.errors.ClientError as exc:
            last_error = exc
            continue

    if reply_text is None:
        raise RuntimeError(
            f"All Gemini model candidates failed. Last error: {last_error}"
        )

    assistant_msg = ChatMessage(
        user_id=user_id, session_id=session_id, role="assistant", content=reply_text
    )
    db.add(assistant_msg)
    db.commit()

    return reply_text


def get_chat_history(
    db: Session,
    user_id: str | None = None,
    session_id: str | None = None,
    limit: int = 50,
) -> list[ChatMessage]:
    query = db.query(ChatMessage).order_by(ChatMessage.created_at.asc())
    if user_id:
        query = query.filter(ChatMessage.user_id == user_id)
    elif session_id:
        query = query.filter(ChatMessage.session_id == session_id)
    else:
        return []
    return query.limit(limit).all()
