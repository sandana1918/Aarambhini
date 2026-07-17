"""Aarambhini FastAPI backend.

Run from the repo root so the root-level `orchestrator` import resolves:
    uvicorn backend.main:app --reload
"""
import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

log = logging.getLogger("aarambhini")

from .config import settings
from .db import ensure_indexes, ping
from .routers import sellers, listings, rules, sessions, language


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.has_db:
        try:
            await ping()
            await ensure_indexes()
            app.state.db_ok = True
        except Exception as exc:  # noqa: BLE001 - don't crash startup on a bad URI
            app.state.db_ok = False
            app.state.db_error = str(exc)
    else:
        app.state.db_ok = False
        app.state.db_error = "MONGODB_URI not set"

    # Surface a missing SESSION_SECRET at /health instead of letting the service
    # boot green and 500 on every login. Outside dev the app already refuses to
    # issue tokens without it (backend/auth.py), so a "healthy" container that
    # can't log anyone in is the worst signal — the health check should catch it.
    app.state.config_error = None
    if not settings.is_dev and not settings.SESSION_SECRET:
        app.state.config_error = "SESSION_SECRET is not set (required outside dev)"
        log.error(app.state.config_error)
    yield


app = FastAPI(title="Aarambhini API", version="0.1.0", lifespan=lifespan)

# Dev: allow the Next.js app on any localhost port. In production, set
# CORS_ORIGINS to an explicit comma-separated list of your real origins.
_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins or [],
    allow_origin_regex=None if _origins else r"http://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sessions.router)
app.include_router(sellers.router)
app.include_router(listings.router)
app.include_router(rules.router)
app.include_router(language.router)


@app.get("/health", tags=["meta"])
async def health():
    db_ok = getattr(app.state, "db_ok", False)
    config_error = getattr(app.state, "config_error", None)
    healthy = db_ok and not config_error
    out = {
        "status": "ok" if healthy else "degraded",
        "env": settings.APP_ENV,
        "db": "connected" if db_ok else "unavailable",
    }
    if not db_ok:
        out["db_error"] = getattr(app.state, "db_error", "unknown")
    if config_error:
        out["config_error"] = config_error
    return out


@app.get("/", tags=["meta"])
async def root():
    return {"service": "Aarambhini API", "docs": "/docs", "health": "/health"}
