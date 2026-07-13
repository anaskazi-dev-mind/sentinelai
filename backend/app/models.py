"""
models.py
---------
SQLAlchemy ORM models (SQLite now, Postgres-ready later with zero changes).

Four tables:
    User          - auth
    Event         - every log/file-activity event + its ML predictions
    FileRecord    - files tracked by the backup/encryption pipeline
    ChatMessage   - chatbot conversation history (for context + audit trail)
"""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


class SeverityLevel(str, enum.Enum):
    NORMAL = "normal"
    SUSPICIOUS = "suspicious"
    CRITICAL = "critical"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    username: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    email: Mapped[str] = mapped_column(
        String(128), unique=True, index=True, nullable=False
    )
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    chat_messages: Mapped[list["ChatMessage"]] = relationship(back_populates="user")


class Event(Base):
    """
    A single observed log line / file-activity event, enriched with
    predictions from the ML pipeline (see app/ml/predict.py).
    """

    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)

    # ----- Raw observed data -----
    source: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # "log_monitor" | "file_scan"
    raw_message: Mapped[str] = mapped_column(Text, nullable=False)
    file_path: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # ----- ML predictions (populated by app/ml/predict.py) -----
    severity: Mapped[SeverityLevel] = mapped_column(
        Enum(SeverityLevel), default=SeverityLevel.NORMAL, index=True
    )
    risk_score: Mapped[float] = mapped_column(
        Float, default=0.0, index=True
    )  # KNN Regression / Linear Regression
    cluster_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # K-Means
    model_used: Mapped[str] = mapped_column(
        String(64), default="random_forest"
    )  # which classifier decided this
    explanation: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # Decision Tree rule path

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )


class FileRecord(Base):
    """Tracks every file the system has backed up and/or encrypted."""

    __tablename__ = "file_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)

    original_path: Mapped[str] = mapped_column(String(512), nullable=False)
    stored_path: Mapped[str] = mapped_column(String(512), nullable=False)
    backup_path: Mapped[str | None] = mapped_column(String(512), nullable=True)

    is_encrypted: Mapped[bool] = mapped_column(Boolean, default=False)
    file_hash: Mapped[str] = mapped_column(
        String(64), nullable=False
    )  # SHA-256, for integrity checks
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class ChatMessage(Base):
    """Stores the copilot chat history so the assistant has conversation context."""

    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    role: Mapped[str] = mapped_column(
        String(16), nullable=False
    )  # "user" | "assistant"
    content: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )

    user: Mapped["User | None"] = relationship(back_populates="chat_messages")
