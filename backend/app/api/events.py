"""
api/events.py
--------------
Routes for the core security-event pipeline: listing classified events,
triggering a manual log scan, and two dashboard-facing analytics
endpoints (risk trend forecast, cluster summary).

Note the risk-trend forecast here is a SECOND, distinct use of Linear
Regression from the one in app/ml/train_models.py: that one predicts
risk_score from an event's raw features, this one predicts risk_score
from TIME (a small time-series trend fit on the fly). Two genuinely
different applications of the same algorithm -- worth calling out in
the viva as intentional, not duplicated code.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

import numpy as np
from fastapi import APIRouter, Depends, Query
from sklearn.linear_model import LinearRegression
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Event, SeverityLevel
from app.schemas import (
    ClusterSummary,
    EventListResponse,
    EventOut,
    RiskTrendPoint,
    RiskTrendResponse,
)
from app.services.log_ingestion_service import scan_and_ingest

router = APIRouter(prefix="/events", tags=["events"])

BUCKET_MINUTES = 30
FORECAST_BUCKETS_AHEAD = 6


@router.get("", response_model=EventListResponse)
def list_events(
    db: Session = Depends(get_db),
    severity: SeverityLevel | None = Query(default=None),
    limit: int = Query(default=50, le=500),
    offset: int = Query(default=0, ge=0),
):
    query = db.query(Event)
    if severity is not None:
        query = query.filter(Event.severity == severity)

    total = query.count()
    items = query.order_by(desc(Event.created_at)).offset(offset).limit(limit).all()

    return EventListResponse(total=total, items=items)


@router.get("/{event_id}", response_model=EventOut)
def get_event(event_id: str, db: Session = Depends(get_db)) -> Event:
    from fastapi import HTTPException

    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found.")
    return event


@router.post("/scan")
def trigger_scan(db: Session = Depends(get_db)) -> dict:
    """
    Manually triggers what the scheduler otherwise runs automatically --
    useful for demoing the log-monitoring pipeline on-demand in a viva
    without waiting for the next scheduled interval.
    """
    ingested = scan_and_ingest(db)
    return {"ingested_events": ingested}


@router.get("/analytics/risk-trend", response_model=RiskTrendResponse)
def risk_trend(
    db: Session = Depends(get_db), hours_back: int = Query(default=6, le=72)
) -> RiskTrendResponse:
    """
    Buckets recent events into fixed time windows, averages risk_score per
    bucket (history), then fits a fresh Linear Regression on bucket-index
    vs avg-risk to project the next few buckets forward (forecast).
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_back)
    events = (
        db.query(Event.created_at, Event.risk_score)
        .filter(Event.created_at >= cutoff)
        .order_by(Event.created_at.asc())
        .all()
    )

    if not events:
        return RiskTrendResponse(history=[], forecast=[])

    buckets: dict[datetime, list[float]] = defaultdict(list)
    bucket_span = timedelta(minutes=BUCKET_MINUTES)

    for created_at, risk_score in events:
        bucket_start = created_at - timedelta(
            minutes=created_at.minute % BUCKET_MINUTES,
            seconds=created_at.second,
            microseconds=created_at.microsecond,
        )
        buckets[bucket_start].append(risk_score)

    sorted_buckets = sorted(buckets.items())
    history = [
        RiskTrendPoint(timestamp=ts, actual_risk=round(float(np.mean(scores)), 2))
        for ts, scores in sorted_buckets
    ]

    forecast: list[RiskTrendPoint] = []
    if len(history) >= 3:
        X = np.arange(len(history)).reshape(-1, 1)
        y = np.array([point.actual_risk for point in history])
        trend_model = LinearRegression().fit(X, y)

        last_ts = history[-1].timestamp
        future_X = np.arange(
            len(history), len(history) + FORECAST_BUCKETS_AHEAD
        ).reshape(-1, 1)
        future_y = np.clip(trend_model.predict(future_X), 0, 100)

        forecast = [
            RiskTrendPoint(
                timestamp=last_ts + bucket_span * (i + 1),
                actual_risk=0.0,
                predicted_risk=round(float(value), 2),
            )
            for i, value in enumerate(future_y)
        ]

    return RiskTrendResponse(history=history, forecast=forecast)


@router.get("/analytics/clusters", response_model=list[ClusterSummary])
def cluster_summary(db: Session = Depends(get_db)) -> list[ClusterSummary]:
    """
    Summarizes events by their K-Means cluster_id (assigned at ingestion
    time in app.ml.predict). Shows how the unsupervised model groups
    behavior patterns, independent of the supervised severity labels.
    """
    events = (
        db.query(Event.cluster_id, Event.severity, Event.raw_message)
        .filter(Event.cluster_id.isnot(None))
        .all()
    )

    grouped: dict[int, list] = defaultdict(list)
    for cluster_id, severity, raw_message in events:
        grouped[cluster_id].append((severity, raw_message))

    summaries = []
    for cluster_id, members in sorted(grouped.items()):
        severities = [m[0] for m in members]
        dominant = Counter(severities).most_common(1)[0][0]
        samples = [m[1] for m in members[:3]]

        summaries.append(
            ClusterSummary(
                cluster_id=cluster_id,
                event_count=len(members),
                dominant_severity=dominant,
                sample_messages=samples,
            )
        )

    return summaries
