"""Aarambhini FastAPI backend.

Run from the repo root so the root-level `orchestrator` import resolves:
    uvicorn backend.main:app --reload
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI

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
