"""Seller registration + lookup."""
import asyncio
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, HTTPException
from pymongo.errors import DuplicateKeyError

from ..auth import hash_password, issue_token
from ..config import settings
from ..db import get_db, SELLERS
from ..models import SellerRegister, SessionOut

router = APIRouter(prefix="/sellers", tags=["sellers"])

# Never let the password hash leave the API, even hashed.
_PUBLIC = {"password_hash": 0}


def _out(doc: dict) -> dict:
    doc["id"] = str(doc.pop("_id"))
    doc.pop("password_hash", None)
    return doc


@router.post("", response_model=SessionOut, status_code=201)
async def register_seller(payload: SellerRegister):
    """Register a seller and log her straight in.

    Returning a session here means she lands on the sell flow ready to work,
    rather than being bounced to a login form to retype what she just typed.
    """
    db = get_db()
    doc = payload.model_dump(exclude={"password"})
    # ~100ms of scrypt — off the event loop so it can't stall other requests.
    doc["password_hash"] = await asyncio.to_thread(hash_password, payload.password)
    doc["created_at"] = datetime.now(timezone.utc)

    try:
        res = await db[SELLERS].insert_one(doc)
    except DuplicateKeyError:
        # The unique index on phone is what actually prevents two accounts
        # racing to the same number; this just turns it into a clear 409.
        raise HTTPException(
            status_code=409,
            detail="That phone number is already registered. Please log in instead.",
        )

    seller_id = str(res.inserted_id)
    return SessionOut(
        token=issue_token(seller_id),
        seller_id=seller_id,
        name=payload.name,
        expires_in_hours=settings.SESSION_TTL_HOURS,
    )


@router.get("/{seller_id}")
async def get_seller(seller_id: str):
    db = get_db()
    try:
        oid = ObjectId(seller_id)
    except Exception:  # noqa: BLE001 - a malformed id is a 404, not a 500
        raise HTTPException(status_code=404, detail="Seller not found")
    doc = await db[SELLERS].find_one({"_id": oid}, _PUBLIC)
    if not doc:
        raise HTTPException(status_code=404, detail="Seller not found")
    return _out(doc)
