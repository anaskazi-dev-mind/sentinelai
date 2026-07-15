"""
schemas.py
----------
Pydantic request/response contracts for the API layer.

Keeping these separate from `models.py` (the ORM layer) is a deliberate
architectural choice: it lets the API's public shape evolve independently
of the database schema, and prevents accidentally leaking internal-only
fields (like hashed_password) to clients.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import SeverityLevel

# =====================================================================
# Auth
# =====================================================================


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserLogin(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    email: str
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# =====================================================================
# Events (log monitoring + ML classification results)
# =====================================================================


class EventIngest(BaseModel):
    """What the log-monitoring service submits for a freshly observed event."""

    source: str = Field(description="e.g. 'log_monitor' or 'file_scan'")
    raw_message: str
    file_path: str | None = None


class ManualEventRequest(BaseModel):
    """A log-style line typed by a person to test the classifier live."""

    message: str = Field(min_length=5, max_length=500)


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source: str
    raw_message: str
    file_path: str | None
    severity: SeverityLevel
    risk_score: float
    cluster_id: int | None
    model_used: str
    explanation: str | None
    created_at: datetime


class EventListResponse(BaseModel):
    total: int
    items: list[EventOut]


class RiskTrendPoint(BaseModel):
    """One point on the risk-over-time chart (Linear Regression forecast)."""

    timestamp: datetime
    actual_risk: float
    predicted_risk: float | None = None


class RiskTrendResponse(BaseModel):
    history: list[RiskTrendPoint]
    forecast: list[RiskTrendPoint]


class ClusterSummary(BaseModel):
    """One K-Means cluster, summarized for the dashboard's cluster view."""

    cluster_id: int
    event_count: int
    dominant_severity: SeverityLevel
    sample_messages: list[str]


# =====================================================================
# Files (backup + encryption pipeline)
# =====================================================================


class FileRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    original_path: str
    stored_path: str
    backup_path: str | None
    is_encrypted: bool
    file_hash: str
    size_bytes: int
    created_at: datetime
    updated_at: datetime


class FileActionRequest(BaseModel):
    file_id: str


# =====================================================================
# Chat (natural-language copilot)
# =====================================================================


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class ChatMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    role: str
    content: str
    created_at: datetime


class ChatResponse(BaseModel):
    reply: str
    history: list[ChatMessageOut]
