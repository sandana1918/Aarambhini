"""Aarambhini FastAPI backend.

Run from the repo root so the root-level `orchestrator` import resolves:
    uvicorn backend.main:app --reload
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import ensure_indexes, ping
from .routers import sellers, listings, rules


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

app.include_router(sellers.router)
app.include_router(listings.router)
app.include_router(rules.router)


@app.get("/health", tags=["meta"])
async def health():
    db_ok = getattr(app.state, "db_ok", False)
    out = {"status": "ok", "env": settings.APP_ENV, "db": "connected" if db_ok else "unavailable"}
    if not db_ok:
        out["db_error"] = getattr(app.state, "db_error", "unknown")
    return out


@app.get("/", tags=["meta"])
async def root():
    return {"service": "Aarambhini API", "docs": "/docs", "health": "/health"}
