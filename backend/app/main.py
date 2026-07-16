"""
main.py
--------
SentinelAI FastAPI application entrypoint.

Responsibilities:
  - Initializes the database schema on startup
  - Starts the background automation scheduler (log monitoring, backups,
    auto-encryption) on startup, and shuts it down cleanly on exit
  - Wires up CORS for the React frontend
  - Mounts all API routers under a single versioned prefix
  - Exposes /health for uptime checks and a friendly root route

Run with:
    uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, chat, events, files
from app.config import get_settings
from app.database import init_db
from app.scheduler import shutdown_scheduler, start_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("sentinelai.main")

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Modern FastAPI startup/shutdown hook (replaces the deprecated
    @app.on_event decorators). Everything before `yield` runs on startup;
    everything after runs on shutdown.
    """
    logger.info("Starting %s in '%s' mode...", settings.app_name, settings.environment)

    init_db()
    logger.info("Database initialized.")

    start_scheduler()

    yield

    logger.info("Shutting down %s...", settings.app_name)
    shutdown_scheduler()


app = FastAPI(
    title=settings.app_name,
    description="Autonomous log intelligence & file security copilot.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix=settings.api_prefix)
app.include_router(events.router, prefix=settings.api_prefix)
app.include_router(files.router, prefix=settings.api_prefix)
app.include_router(chat.router, prefix=settings.api_prefix)


@app.get("/health", tags=["system"])
def health_check() -> dict:
    return {
        "status": "ok",
        "app": settings.app_name,
        "environment": settings.environment,
    }


@app.get("/", tags=["system"])
def root() -> dict:
    return {
        "message": f"{settings.app_name} API is running.",
        "docs": "/docs",
        "health": "/health",
    }
