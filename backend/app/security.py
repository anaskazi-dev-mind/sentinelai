"""
security.py
------------
Password hashing + JWT issuing/verification, and the FastAPI dependency
that protected routes use to identify the current user.

Uses passlib[bcrypt] for hashing (never store plaintext or reversibly-
encrypted passwords) and python-jose for JWTs (industry-standard,
stateless auth -- no server-side session store needed).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import User

settings = get_settings()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# tokenUrl points at the login route clients should hit to obtain a token;
# used only for OpenAPI docs' "Authorize" button, not for redirection logic.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.api_prefix}/auth/login")


# =====================================================================
# Password hashing
# =====================================================================


def hash_password(plain_password: str) -> str:
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


# =====================================================================
# JWT issuing
# =====================================================================


def create_access_token(subject: str, expires_minutes: int | None = None) -> str:
    """subject is the user's id (stored in the token's `sub` claim)."""
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes or settings.access_token_expire_minutes
    )
    payload = {"sub": subject, "exp": expire, "iat": datetime.now(timezone.utc)}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> str:
    """Returns the user id from a valid token, or raises JWTError."""
    payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    subject = payload.get("sub")
    if subject is None:
        raise JWTError("Token payload missing 'sub' claim.")
    return subject


# =====================================================================
# FastAPI dependency: get the currently authenticated user
# =====================================================================

_CREDENTIALS_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    try:
        user_id = decode_access_token(token)
    except JWTError as exc:
        raise _CREDENTIALS_ERROR from exc

    user = db.get(User, user_id)
    if user is None:
        raise _CREDENTIALS_ERROR
    return user


def get_current_user_optional(
    token: str | None = Depends(
        OAuth2PasswordBearer(
            tokenUrl=f"{settings.api_prefix}/auth/login", auto_error=False
        )
    ),
    db: Session = Depends(get_db),
) -> User | None:
    """
    Same as get_current_user but never raises -- used on routes (like /chat)
    that work for anonymous demo use but personalize history when logged in.
    """
    if token is None:
        return None
    try:
        user_id = decode_access_token(token)
    except JWTError:
        return None
    return db.get(User, user_id)
