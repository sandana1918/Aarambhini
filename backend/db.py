"""Async MongoDB (Atlas) connection via Motor, plus index setup.

Nothing connects at import time — call get_db()/connect() explicitly so the app
(and the seed script) fail loudly and clearly when MONGODB_URI is missing.
"""
import certifi
from motor.motor_asyncio import AsyncIOMotorClient

from .config import settings

_client = None
_db = None


def get_client():
    global _client
    if _client is None:
        if not settings.has_db:
            raise RuntimeError(
                "MONGODB_URI is not set. Add your Atlas connection string to .env."
            )
        _client = AsyncIOMotorClient(
            settings.MONGODB_URI,
            tlsCAFile=certifi.where(),  # Windows/Python often lacks a usable CA store for Atlas TLS
            serverSelectionTimeoutMS=8000,
        )
    return _client


def get_db():
    global _db
    if _db is None:
        _db = get_client()[settings.DB_NAME]
    return _db


# Collection names — single source of truth (matches the HLD schemas).
SELLERS = "sellers"
LISTINGS = "listings"
COMPLIANCE_RULES = "compliance_rules"
PRICE_BENCHMARKS = "price_benchmarks"
IMAGE_FINGERPRINTS = "image_fingerprints"
AUDIT_LOG = "audit_log"


async def ensure_indexes():
    """Idempotent — safe to call on every startup."""
    db = get_db()
    await db[SELLERS].create_index("phone", unique=True)
    await db[LISTINGS].create_index("seller_id")
    await db[LISTINGS].create_index("status")
    await db[COMPLIANCE_RULES].create_index("category", unique=True)
    await db[PRICE_BENCHMARKS].create_index([("category", 1), ("region", 1)], unique=True)
    await db[IMAGE_FINGERPRINTS].create_index("phash")
    await db[IMAGE_FINGERPRINTS].create_index("seller_id")
    await db[AUDIT_LOG].create_index([("listing_id", 1), ("ts", -1)])


async def ping() -> bool:
    await get_client().admin.command("ping")
    return True
