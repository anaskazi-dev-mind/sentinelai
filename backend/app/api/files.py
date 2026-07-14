"""
api/files.py
-------------
Routes for the file protection pipeline: backup, encrypt, decrypt, and
listing tracked files / backup archives.

Mutating routes (backup/encrypt/decrypt) require authentication --
these actions touch the filesystem and produce sensitive plaintext, so
they're deliberately NOT open to anonymous callers, unlike /chat which
allows anonymous demo use.
"""

from __future__ import annotations

import base64

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import FileRecord, User
from app.schemas import FileRecordOut
from app.security import get_current_user
from app.services.backup_service import backup_single_file, list_backups
from app.services.encryption_service import DecryptionError, decrypt_file, encrypt_file

router = APIRouter(prefix="/files", tags=["files"])


class FilePathRequest(BaseModel):
    path: str


class DecryptResponse(BaseModel):
    file_id: str
    filename: str
    content_base64: str


@router.get("", response_model=list[FileRecordOut])
def list_tracked_files(db: Session = Depends(get_db)) -> list[FileRecord]:
    return db.query(FileRecord).order_by(FileRecord.updated_at.desc()).all()


@router.get("/backups")
def list_backup_archives(_: User = Depends(get_current_user)) -> list[dict]:
    return list_backups()


@router.post(
    "/backup", response_model=FileRecordOut, status_code=status.HTTP_201_CREATED
)
def create_backup(
    payload: FilePathRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> FileRecord:
    try:
        return backup_single_file(db, payload.path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/encrypt", response_model=FileRecordOut, status_code=status.HTTP_201_CREATED
)
def encrypt(
    payload: FilePathRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> FileRecord:
    try:
        return encrypt_file(db, payload.path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/decrypt/{file_id}", response_model=DecryptResponse)
def decrypt(
    file_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> DecryptResponse:
    """
    Returns decrypted content as base64 in a JSON response rather than a
    raw file stream -- keeps this endpoint simple and testable via Swagger
    docs directly, which matters for a live demo in front of your guide.
    """
    record = db.get(FileRecord, file_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"No file record with id={file_id}")

    try:
        plaintext = decrypt_file(db, file_id)
    except DecryptionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    from pathlib import Path

    filename = Path(record.original_path).name
    return DecryptResponse(
        file_id=file_id,
        filename=filename,
        content_base64=base64.b64encode(plaintext).decode(),
    )
