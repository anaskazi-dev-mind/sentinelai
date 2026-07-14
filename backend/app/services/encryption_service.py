"""
encryption_service.py
-----------------------
Automation module: File Encryption & Decryption.

Uses Fernet (symmetric AES-128-CBC + HMAC, from the `cryptography`
package) rather than hand-rolled crypto -- writing your own encryption
primitive is a well-known anti-pattern; Fernet is the industry-standard
"boring, correct" choice for this kind of application-level file
encryption.

Every encrypted file is paired with a SHA-256 hash of its *original*
content, stored in FileRecord.file_hash -- this lets the system later
verify a decrypted file wasn't corrupted/tampered with (integrity check),
independent of the encryption itself.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import FileRecord

settings = get_settings()

ENCRYPTED_SUFFIX = ".enc"
VAULT_DIR_NAME = "encrypted_vault"


class DecryptionError(Exception):
    """Raised when a file can't be decrypted -- wrong key, corrupted data, or tampering."""


def _fernet() -> Fernet:
    return Fernet(settings.fernet_key.encode())


def _vault_dir() -> Path:
    path = Path(settings.backup_dir).parent / VAULT_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def compute_file_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encrypt_file(db: Session, source_path: str | Path) -> FileRecord:
    """
    Encrypts the file at source_path, stores the ciphertext in the vault
    directory, and records a FileRecord row. The original plaintext file
    on disk is left untouched -- this service produces a protected COPY,
    it does not destroy the source (a safer default for an automation
    tool acting without a human confirming every step).
    """
    source_path = Path(source_path)
    if not source_path.exists():
        raise FileNotFoundError(f"Cannot encrypt: {source_path} does not exist.")

    plaintext = source_path.read_bytes()
    file_hash = compute_file_hash(plaintext)
    ciphertext = _fernet().encrypt(plaintext)

    stored_path = _vault_dir() / f"{source_path.name}{ENCRYPTED_SUFFIX}"
    stored_path.write_bytes(ciphertext)

    record = FileRecord(
        original_path=str(source_path),
        stored_path=str(stored_path),
        is_encrypted=True,
        file_hash=file_hash,
        size_bytes=len(plaintext),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def decrypt_file(db: Session, file_id: str) -> bytes:
    """
    Decrypts a previously encrypted FileRecord and verifies its integrity
    against the stored hash before returning the plaintext bytes.
    """
    record = db.get(FileRecord, file_id)
    if record is None:
        raise FileNotFoundError(f"No FileRecord with id={file_id}")
    if not record.is_encrypted:
        raise ValueError(f"FileRecord {file_id} is not marked as encrypted.")

    ciphertext = Path(record.stored_path).read_bytes()

    try:
        plaintext = _fernet().decrypt(ciphertext)
    except InvalidToken as exc:
        raise DecryptionError(
            "Decryption failed -- the key is wrong or the file has been tampered with."
        ) from exc

    if compute_file_hash(plaintext) != record.file_hash:
        raise DecryptionError(
            "Integrity check failed -- decrypted content does not match the stored hash."
        )

    return plaintext


def encrypt_high_risk_file(db: Session, file_path: str | Path) -> FileRecord | None:
    """
    Convenience entry point called by the risk pipeline: encrypts a file
    ONLY if it exists and isn't already protected, so repeated critical
    events on the same file don't create duplicate vault copies.
    """
    file_path = Path(file_path)
    if not file_path.exists():
        return None

    existing = (
        db.query(FileRecord)
        .filter(
            FileRecord.original_path == str(file_path), FileRecord.is_encrypted == True
        )  # noqa: E712
        .first()
    )
    if existing:
        return existing

    return encrypt_file(db, file_path)
