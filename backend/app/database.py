"""
database.py
-----------
SQLAlchemy engine + session setup.

Uses SQLite for local development (zero-setup, file-based) but the
connection string is fully swappable via DATABASE_URL -- switching to
Postgres in production requires no code change here, only an env var.
"""

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

settings = get_settings()

# SQLite needs this flag because, by default, it only allows one thread
# to talk to a connection; FastAPI's async request handling uses multiple.
connect_args = (
    {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)

# Ensure the SQLite database's parent directory exists before connecting --
# SQLite won't create it automatically, and this avoids a startup crash.
if settings.database_url.startswith("sqlite"):
    db_file_path = settings.database_url.replace("sqlite:///", "", 1)
    Path(db_file_path).parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    pool_pre_ping=True,  # detects and recycles stale connections
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Base class every ORM model inherits from."""

    pass


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency: yields a DB session per request and guarantees
    it's closed afterward, even if the request raises an exception.

    Usage in a route:
        def endpoint(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """
    Creates all tables from models that inherit from Base.
    Called once at app startup (see main.py). Import models here so
    they're registered on Base.metadata before create_all runs.
    """
    from app import (
        models,
    )  # noqa: F401  (import needed for side-effect: table registration)

    Base.metadata.create_all(bind=engine)
