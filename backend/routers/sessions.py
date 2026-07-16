"""Seller login — phone + password in, a signed session token out."""
import asyncio
import secrets

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException

from ..auth import (
    check_login_allowed,
    clear_login_failures,
    current_seller,
    hash_password,
    issue_token,
    record_login_failure,
    verify_password,
)
from ..config import settings
from ..db import get_db, SELLERS
from ..models import SessionOut, SessionStart

router = APIRouter(prefix="/sessions", tags=["sessions"])

_BAD_CREDENTIALS = "That phone number or password is incorrect."

# A real hash of an unguessable password, used when the phone isn't registered.
# verify_password() returns False immediately on a missing hash, so without this
# an unknown phone would answer ~100ms faster than a known one — which times the
# difference between "wrong password" and "no such seller" and hands out exactly
# the account enumeration the identical error message is meant to prevent.
_DUMMY_HASH = hash_password(secrets.token_urlsafe(32))


@router.post("", response_model=SessionOut)
async def log_in(payload: SessionStart):
    """Log in. Wrong phone and wrong password are deliberately indistinguishable
    — a distinct "no such seller" reply would let anyone enumerate which of
    these women have accounts here.
    """
    check_login_allowed(payload.phone)
    db = get_db()
    seller = await db[SELLERS].find_one({"phone": payload.phone})

    # Always run a full scrypt verify — against a dummy hash when the phone is
    # unknown — so the reply takes the same ~100ms either way.
    stored = seller.get("password_hash") if seller else _DUMMY_HASH
    ok = await asyncio.to_thread(verify_password, payload.password, stored or _DUMMY_HASH)

    if not seller or not ok:
        record_login_failure(payload.phone)
        raise HTTPException(status_code=401, detail=_BAD_CREDENTIALS)

    clear_login_failures(payload.phone)
    seller_id = str(seller["_id"])
    return SessionOut(
        token=issue_token(seller_id),
        seller_id=seller_id,
        name=seller.get("name", ""),
        expires_in_hours=settings.SESSION_TTL_HOURS,
    )


@router.get("/me")
async def whoami(seller_id: str = Depends(current_seller)):
    """Resolve the current session to its seller — the frontend uses this to
    tell a still-valid session from an expired one on page load.
    """
    db = get_db()
    seller = await db[SELLERS].find_one({"_id": ObjectId(seller_id)})
    if not seller:
        # Signed token, but the seller is gone — treat as no session at all.
        raise HTTPException(status_code=401, detail="That seller no longer exists.")
    return {"seller_id": seller_id, "name": seller.get("name", ""), "phone": seller.get("phone", "")}
