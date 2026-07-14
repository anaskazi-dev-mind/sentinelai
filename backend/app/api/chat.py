"""
api/chat.py
------------
Routes for the AI copilot (Automation: Chatbot module).

Deliberately allows anonymous use (via get_current_user_optional) so the
chat panel works instantly in a demo without requiring a login step --
but still personalizes conversation history per user when a valid JWT
is present. Errors from the Anthropic call are caught and turned into a
clean 502, not a raw stack trace leaking to the client.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas import ChatMessageOut, ChatRequest, ChatResponse
from app.security import get_current_user_optional
from app.services.chatbot_service import ask_copilot, get_chat_history

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
) -> ChatResponse:
    user_id = current_user.id if current_user else None

    try:
        reply = ask_copilot(db, payload.message, user_id=user_id)
    except RuntimeError as exc:
        # Raised by chatbot_service when ANTHROPIC_API_KEY is missing.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except (
        Exception
    ) as exc:  # noqa: BLE001 - upstream API failure, don't leak internals
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The AI copilot is temporarily unavailable. Please try again.",
        ) from exc

    history = get_chat_history(db, user_id=user_id, limit=20)
    return ChatResponse(reply=reply, history=history)


@router.get("/history", response_model=list[ChatMessageOut])
def chat_history(
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
    limit: int = 50,
) -> list:
    user_id = current_user.id if current_user else None
    return get_chat_history(db, user_id=user_id, limit=limit)
