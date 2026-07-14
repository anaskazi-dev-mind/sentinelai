"""
chatbot_service.py
--------------------
Automation module: Chatbot.

Powered by Google's Gemini API (free tier) instead of a scripted
rule-based bot. Pulls real, live numbers from the database (event
counts, severity breakdown, recent critical events) and hands them to
Gemini as grounded context, instructing it to answer strictly from that
data -- a retrieval-augmented pattern, not open-ended generation.

Conversation history is persisted in ChatMessage so the copilot has
short-term memory across turns, and so the report can show a real
transcript as evidence of a working feature.
"""

from __future__ import annotations

from google import genai
from google.genai import types
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import ChatMessage, Event, SeverityLevel

settings = get_settings()

MODEL = "gemini-2.5-flash"
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
    """
    Pulls a real, current snapshot of the system's security state --
    this is what makes the copilot's answers grounded instead of generic.
    """
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


def _get_recent_history(db: Session, user_id: str | None) -> list[dict]:
    """
    Returns recent turns in Gemini's expected format. Note: Gemini uses
    the role "model" for assistant turns (not "assistant" like other
    APIs) -- this mapping is what makes our stored history compatible.
    """
    query = db.query(ChatMessage).order_by(ChatMessage.created_at.desc())
    if user_id:
        query = query.filter(ChatMessage.user_id == user_id)

    recent = query.limit(MAX_HISTORY_MESSAGES).all()
    recent.reverse()  # chronological order for the API call

    gemini_role = {"user": "user", "assistant": "model"}
    return [
        {"role": gemini_role.get(m.role, "user"), "parts": [{"text": m.content}]}
        for m in recent
    ]


def ask_copilot(db: Session, message: str, user_id: str | None = None) -> str:
    """
    Full round-trip: store the user's message, gather grounded context,
    call Gemini with conversation history, store and return the reply.
    """
    user_msg = ChatMessage(user_id=user_id, role="user", content=message)
    db.add(user_msg)
    db.commit()

    history = _get_recent_history(db, user_id)
    security_context = _build_security_context(db)

    # The last history entry is the message we just stored -- replace it
    # with a version that also carries the grounded security context.
    grounded_message = (
        f"SECURITY DATA CONTEXT:\n{security_context}\n\nUSER QUESTION: {message}"
    )
    contents = history[:-1] + [{"role": "user", "parts": [{"text": grounded_message}]}]

    client = _get_client()
    response = client.models.generate_content(
        model=MODEL,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            max_output_tokens=800,
        ),
    )
    reply_text = response.text or "I couldn't generate a response -- please try again."

    assistant_msg = ChatMessage(user_id=user_id, role="assistant", content=reply_text)
    db.add(assistant_msg)
    db.commit()

    return reply_text


def get_chat_history(
    db: Session, user_id: str | None = None, limit: int = 50
) -> list[ChatMessage]:
    query = db.query(ChatMessage).order_by(ChatMessage.created_at.asc())
    if user_id:
        query = query.filter(ChatMessage.user_id == user_id)
    return query.limit(limit).all()
