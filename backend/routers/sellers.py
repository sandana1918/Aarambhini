"""Seller registration + lookup."""
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, HTTPException

from ..db import get_db, SELLERS
from ..models import SellerCreate

router = APIRouter(prefix="/sellers", tags=["sellers"])


def _out(doc: dict) -> dict:
    doc["id"] = str(doc.pop("_id"))
    return doc


@router.post("")
async def create_seller(payload: SellerCreate):
    db = get_db()
    doc = payload.model_dump()
    doc["created_at"] = datetime.now(timezone.utc)
    try:
        res = await db[SELLERS].insert_one(doc)
    except Exception as exc:  # duplicate phone → 409
        raise HTTPException(status_code=409, detail=f"Could not create seller: {exc}")
    doc["_id"] = res.inserted_id
    return _out(doc)


@router.get("/{seller_id}")
async def get_seller(seller_id: str):
    db = get_db()
    doc = await db[SELLERS].find_one({"_id": ObjectId(seller_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Seller not found")
    return _out(doc)
