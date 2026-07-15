"""
api/chat.py
------------
Routes for the AI copilot (Automation: Chatbot module).

Anonymous visitors are scoped by a browser-generated X-Session-Id header
(see frontend/src/api.js) so two different visitors never see each
other's conversation. Logged-in users are scoped by their real user_id
instead, which takes priority if both are present.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status
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
    x_session_id: str | None = Header(default=None, alias="X-Session-Id"),
) -> ChatResponse:
    user_id = current_user.id if current_user else None

    try:
        reply = ask_copilot(
            db, payload.message, user_id=user_id, session_id=x_session_id
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The AI copilot is temporarily unavailable. Please try again.",
        ) from exc

    history = get_chat_history(db, user_id=user_id, session_id=x_session_id, limit=20)
    return ChatResponse(reply=reply, history=history)


@router.get("/history", response_model=list[ChatMessageOut])
def chat_history(
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
    x_session_id: str | None = Header(default=None, alias="X-Session-Id"),
    limit: int = 50,
) -> list:
    user_id = current_user.id if current_user else None
    return get_chat_history(db, user_id=user_id, session_id=x_session_id, limit=limit)
