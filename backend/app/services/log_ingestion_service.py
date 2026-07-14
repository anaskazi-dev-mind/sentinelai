"""
log_ingestion_service.py
-------------------------
Automation module: Log Monitoring.

Watches a directory of log files, incrementally reads only newly-appended
lines (never re-processes the whole file on every scan), classifies each
new line through the ML pipeline (app.ml.predict), and persists it as an
Event. This function is what the scheduler calls every N seconds -- it IS
the "Log Monitoring" automation module in action, not a simulation of it.

Also includes a lightweight synthetic activity generator so the log
monitor always has real new lines to watch during development/demo --
in a real deployment this would simply be the host system's own log
output instead of this generator.
"""

from __future__ import annotations

import json
import random
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import get_settings
from app.ml.predict import predict_event
from app.models import Event

settings = get_settings()

STATE_FILE_NAME = ".log_offsets.json"
DEMO_LOG_FILENAME = "system_activity.log"

_DEMO_DEVICES_NORMAL = ["WKSTN-01", "WKSTN-02", "SRV-DB-PRIMARY", "LAPTOP-ADMIN"]
_DEMO_DEVICES_UNKNOWN = ["UNKNOWN-HOST", "EXT-192.168.77.14", "EXT-10.0.9.201"]


def _watch_dir() -> Path:
    path = Path(settings.log_watch_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _state_path() -> Path:
    return _watch_dir() / STATE_FILE_NAME


def _load_offsets() -> dict[str, int]:
    state_path = _state_path()
    if state_path.exists():
        try:
            return json.loads(state_path.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def _save_offsets(offsets: dict[str, int]) -> None:
    _state_path().write_text(json.dumps(offsets, indent=2))


def _read_new_lines(file_path: Path, offsets: dict[str, int]) -> list[str]:
    """Reads only the bytes appended since the last recorded offset for this file."""
    key = str(file_path)
    last_offset = offsets.get(key, 0)

    with file_path.open("r", encoding="utf-8", errors="ignore") as f:
        f.seek(last_offset)
        new_content = f.read()
        offsets[key] = f.tell()

    return [line.strip() for line in new_content.splitlines() if line.strip()]


def ingest_message(
    db: Session, source: str, raw_message: str, file_path: str | None = None
) -> Event:
    """Runs one message through the ML pipeline and persists it as an Event."""
    prediction = predict_event(raw_message, file_path=file_path)

    event = Event(
        source=source,
        raw_message=raw_message,
        file_path=file_path,
        severity=prediction.severity,
        risk_score=prediction.risk_score,
        cluster_id=prediction.cluster_id,
        model_used=prediction.model_used,
        explanation=prediction.explanation,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def scan_and_ingest(db: Session) -> int:
    """
    Scans every *.log file in the watched directory for lines appended
    since the last scan, classifies each through the ML pipeline, and
    stores it as an Event. Returns the number of events ingested.
    """
    watch_dir = _watch_dir()
    offsets = _load_offsets()
    ingested_count = 0

    for log_file in watch_dir.glob("*.log"):
        for line in _read_new_lines(log_file, offsets):
            ingest_message(db, source="log_monitor", raw_message=line)
            ingested_count += 1

    _save_offsets(offsets)
    return ingested_count


# =====================================================================
# Synthetic activity generator -- keeps the demo log file alive so the
# live dashboard always has fresh, realistic events to classify.
# =====================================================================


def _random_normal_line() -> str:
    device = random.choice(_DEMO_DEVICES_NORMAL)
    return (
        f"Login node {device}: {random.randint(0, 1)} failed attempts, "
        f"{random.randint(1, 5)} active connections, "
        f"{random.randint(1, 8)} file operations in session (after-hours=no)."
    )


def _random_suspicious_line() -> str:
    device = random.choice(_DEMO_DEVICES_NORMAL + _DEMO_DEVICES_UNKNOWN)
    return (
        f"Login node {device}: {random.randint(2, 5)} failed attempts, "
        f"{random.randint(6, 12)} active connections, "
        f"{random.randint(10, 20)} file operations in session (after-hours=yes)."
    )


def _random_critical_line() -> str:
    device = random.choice(_DEMO_DEVICES_UNKNOWN)
    return (
        f"Login node {device}: {random.randint(6, 10)} failed attempts, "
        f"{random.randint(13, 25)} active connections, "
        f"{random.randint(25, 45)} file operations in session (after-hours=yes)."
    )


def append_simulated_activity(n_lines: int = 3) -> Path:
    """
    Appends a few realistic log lines to the demo log file, mostly normal
    with occasional suspicious/critical spikes -- mirrors a real
    environment's activity mix. Called periodically by scheduler.py so the
    live dashboard has something genuine to show during a demo.
    """
    log_path = _watch_dir() / DEMO_LOG_FILENAME
    lines = []
    for _ in range(n_lines):
        roll = random.random()
        if roll < 0.70:
            lines.append(_random_normal_line())
        elif roll < 0.92:
            lines.append(_random_suspicious_line())
        else:
            lines.append(_random_critical_line())

    timestamp = datetime.now(timezone.utc).isoformat()
    with log_path.open("a", encoding="utf-8") as f:
        for line in lines:
            f.write(f"[{timestamp}] {line}\n")

    return log_path
