"""
backup_service.py
-------------------
Automation module: File Backup & Compression.

Two complementary responsibilities:
  1. Per-file backups tied to a FileRecord (so the dashboard can show
     "this file has a backup from <time>" against a specific tracked file).
  2. Whole-directory snapshot backups (e.g. the log-watch directory),
     compressed with Python's built-in `zipfile` -- this IS the
     "Compressing files and folders / ZIP file handling" course module,
     applied to something real (not a toy example zip of two text files).

Also includes retention pruning: unbounded backup accumulation is a real
operational problem, so old backups are automatically cleaned up past a
configurable retention window -- a genuine automation concern, not just
"create a backup and forget about it".
"""

from __future__ import annotations

import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import FileRecord

settings = get_settings()

BACKUP_TIMESTAMP_FMT = "%Y%m%d_%H%M%S"
DEFAULT_RETENTION_DAYS = 14


def _backup_dir() -> Path:
    path = Path(settings.backup_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _timestamped_name(stem: str, suffix: str = ".zip") -> str:
    ts = datetime.now(timezone.utc).strftime(BACKUP_TIMESTAMP_FMT)
    return f"{stem}_{ts}{suffix}"


# =====================================================================
# 1. Per-file backup (tracked against a FileRecord)
# =====================================================================


def backup_single_file(db: Session, source_path: str | Path) -> FileRecord:
    """
    Compresses one file into a timestamped .zip inside the backup
    directory, and links it to (or creates) a FileRecord so the
    dashboard's File Vault can show backup status per file.
    """
    source_path = Path(source_path)
    if not source_path.exists():
        raise FileNotFoundError(f"Cannot back up: {source_path} does not exist.")

    archive_name = _timestamped_name(source_path.stem)
    archive_path = _backup_dir() / archive_name

    with zipfile.ZipFile(
        archive_path, mode="w", compression=zipfile.ZIP_DEFLATED
    ) as zf:
        zf.write(source_path, arcname=source_path.name)

    record = (
        db.query(FileRecord)
        .filter(FileRecord.original_path == str(source_path))
        .first()
    )

    if record is None:
        import hashlib

        file_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
        record = FileRecord(
            original_path=str(source_path),
            stored_path=str(source_path),
            backup_path=str(archive_path),
            is_encrypted=False,
            file_hash=file_hash,
            size_bytes=source_path.stat().st_size,
        )
        db.add(record)
    else:
        record.backup_path = str(archive_path)

    db.commit()
    db.refresh(record)
    return record


# =====================================================================
# 2. Whole-directory snapshot backup (e.g. the log-watch directory)
# =====================================================================


def backup_directory_snapshot(
    source_dir: str | Path, archive_stem: str = "logs_snapshot"
) -> Path:
    """
    Zips an entire directory tree into one timestamped archive.
    Used by the scheduler to periodically snapshot the log-watch
    directory, independent of any single FileRecord.
    """
    source_dir = Path(source_dir)
    if not source_dir.exists():
        raise FileNotFoundError(f"Cannot snapshot: {source_dir} does not exist.")

    archive_name = _timestamped_name(archive_stem)
    archive_path = _backup_dir() / archive_name

    with zipfile.ZipFile(
        archive_path, mode="w", compression=zipfile.ZIP_DEFLATED
    ) as zf:
        for file_path in source_dir.rglob("*"):
            if file_path.is_file():
                zf.write(file_path, arcname=file_path.relative_to(source_dir))

    return archive_path


# =====================================================================
# Retention: prune backups older than N days
# =====================================================================


def prune_old_backups(retention_days: int = DEFAULT_RETENTION_DAYS) -> int:
    """
    Deletes backup archives older than `retention_days`. Returns the
    number of archives removed. This is what stops a long-running
    deployment from silently filling up disk with backups forever.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    removed = 0

    for archive in _backup_dir().glob("*.zip"):
        modified_time = datetime.fromtimestamp(archive.stat().st_mtime, tz=timezone.utc)
        if modified_time < cutoff:
            archive.unlink()
            removed += 1

    return removed


def list_backups() -> list[dict]:
    """Returns metadata for every backup currently on disk (used by the API/dashboard)."""
    backups = []
    for archive in sorted(_backup_dir().glob("*.zip"), reverse=True):
        stat = archive.stat()
        backups.append(
            {
                "filename": archive.name,
                "size_bytes": stat.st_size,
                "created_at": datetime.fromtimestamp(
                    stat.st_mtime, tz=timezone.utc
                ).isoformat(),
            }
        )
    return backups
