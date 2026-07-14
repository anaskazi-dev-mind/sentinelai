"""
scheduler.py
------------
The automation "engine" -- runs the Log Monitoring, Backup, and
auto-encryption pipelines as background jobs, without any user needing
to click a button. This is what makes SentinelAI a *copilot* rather
than a manual tool: it watches and reacts on its own.

Uses APScheduler's BackgroundScheduler (thread-based, in-process) --
sufficient for a single-instance deployment; a multi-instance production
deployment would swap this for a distributed job queue (e.g. Celery +
Redis), a natural "Future Enhancement" to mention in the report.
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import get_settings
from app.database import SessionLocal
from app.models import Event, SeverityLevel
from app.services.backup_service import backup_directory_snapshot, prune_old_backups
from app.services.encryption_service import encrypt_high_risk_file
from app.services.log_ingestion_service import (
    append_simulated_activity,
    scan_and_ingest,
)

settings = get_settings()
logger = logging.getLogger("sentinelai.scheduler")

_scheduler: BackgroundScheduler | None = None


def _job_generate_and_scan_logs() -> None:
    """
    Job 1 (runs every SCAN_INTERVAL_SECONDS):
    Appends a few realistic log lines, then immediately scans for and
    classifies any new lines across the watch directory. This is the
    Log Monitoring automation module running continuously, unattended.
    """
    db = SessionLocal()
    try:
        append_simulated_activity(n_lines=3)
        ingested = scan_and_ingest(db)
        if ingested:
            logger.info("Log scan ingested %d new event(s).", ingested)

        _auto_protect_critical_files(db)
    except Exception:
        logger.exception("Log scan job failed.")
    finally:
        db.close()


def _auto_protect_critical_files(db) -> None:
    """
    Reacts to CRITICAL events that reference a real file path by
    automatically encrypting that file -- this is the "copilot" behavior:
    the system doesn't just flag risk, it takes a protective action on
    its own, without waiting for a human to click anything.
    """
    recent_critical = (
        db.query(Event)
        .filter(Event.severity == SeverityLevel.CRITICAL, Event.file_path.isnot(None))
        .order_by(Event.created_at.desc())
        .limit(5)
        .all()
    )

    for event in recent_critical:
        try:
            encrypt_high_risk_file(db, event.file_path)
        except FileNotFoundError:
            # Expected for demo/simulated file paths that don't exist on
            # disk -- real deployments would point at real file paths.
            continue


def _job_backup_snapshot() -> None:
    """
    Job 2 (runs every BACKUP_INTERVAL_MINUTES):
    Snapshots the entire log-watch directory into a compressed archive.
    """
    try:
        archive_path = backup_directory_snapshot(settings.log_watch_dir)
        logger.info("Backup snapshot created: %s", archive_path)
    except FileNotFoundError:
        logger.warning("Backup skipped -- log watch directory not found yet.")
    except Exception:
        logger.exception("Backup snapshot job failed.")


def _job_prune_backups() -> None:
    """Job 3 (runs once every 24h): deletes backups past the retention window."""
    try:
        removed = prune_old_backups()
        if removed:
            logger.info("Pruned %d expired backup archive(s).", removed)
    except Exception:
        logger.exception("Backup pruning job failed.")


def start_scheduler() -> BackgroundScheduler:
    """
    Creates, configures, and starts the background scheduler. Called once
    from main.py's startup event. Idempotent -- calling it twice returns
    the existing instance instead of double-scheduling jobs.
    """
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    scheduler = BackgroundScheduler(timezone="UTC")

    scheduler.add_job(
        _job_generate_and_scan_logs,
        trigger=IntervalTrigger(seconds=settings.scan_interval_seconds),
        id="log_scan",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.add_job(
        _job_backup_snapshot,
        trigger=IntervalTrigger(minutes=settings.backup_interval_minutes),
        id="backup_snapshot",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.add_job(
        _job_prune_backups,
        trigger=IntervalTrigger(hours=24),
        id="prune_backups",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.start()
    _scheduler = scheduler
    logger.info(
        "Scheduler started: log scan every %ds, backups every %dm.",
        settings.scan_interval_seconds,
        settings.backup_interval_minutes,
    )
    return scheduler


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
