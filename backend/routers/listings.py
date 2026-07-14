"""Listing lifecycle: run the agent crew, fetch, and the approval gate.

The heavy lifting is the existing LangGraph orchestrator at repo root; this
router persists its output and enforces approval-before-publish + an audit trail.
"""
import io
import asyncio
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from PIL import Image
from fastapi import APIRouter, HTTPException, UploadFile, File, Form

from ..db import get_db, LISTINGS, AUDIT_LOG
from ..models import ApprovalDecision

router = APIRouter(prefix="/listings", tags=["listings"])


def _out(doc: dict) -> dict:
    doc["id"] = str(doc.pop("_id"))
    if doc.get("seller_id"):
        doc["seller_id"] = str(doc["seller_id"])
    return doc


@router.post("/run")
async def run_listing(
    voice_text: str = Form(...),
    desired_margin_pct: int = Form(20),
    seller_id: Optional[str] = Form(None),
    photo: Optional[UploadFile] = File(None),
):
    """Run the agent crew on a voice note + one product photo (multipart)."""
    import orchestrator  # repo-root module; imported lazily so backend stays importable

    image = None
    if photo is not None:
        raw = await photo.read()
        if raw:
            try:
                image = Image.open(io.BytesIO(raw))
                image.load()
            except Exception:
                raise HTTPException(status_code=400, detail="Could not read that image file.")

    result = await asyncio.to_thread(
        orchestrator.run, voice_text, image, desired_margin_pct
    )

    db = get_db()
    now = datetime.now(timezone.utc)
    doc = {
        "seller_id": ObjectId(seller_id) if seller_id else None,
        "status": result.get("status"),
        "suno": result.get("suno"),
        "listing": result.get("listing"),
        "price": result.get("price"),
        "compliance": result.get("compliance"),
        "returns": result.get("returns"),
        "packaging_plan": result.get("packaging_plan"),
        "action_checklist": result.get("action_checklist", []),
        "approvals": result.get("approvals", []),
        "activity_log": [{"agent": name, "output": out} for name, out in result.get("log", [])],
        "reason": result.get("reason"),
        "version": 1,
        "created_at": now,
        "updated_at": now,
    }
    res = await db[LISTINGS].insert_one(doc)
    doc["_id"] = res.inserted_id
    return _out(doc)


@router.get("/{listing_id}")
async def get_listing(listing_id: str):
    db = get_db()
    doc = await db[LISTINGS].find_one({"_id": ObjectId(listing_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Listing not found")
    return _out(doc)


@router.post("/{listing_id}/approve")
async def approve_listing(listing_id: str, decision: ApprovalDecision):
    """The approval gate — nothing publishes without this explicit call."""
    db = get_db()
    oid = ObjectId(listing_id)
    doc = await db[LISTINGS].find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Listing not found")
    if doc.get("status") != "ready_for_approval":
        raise HTTPException(status_code=409, detail=f"Listing is '{doc.get('status')}', not awaiting approval")

    new_status = "published" if decision.approved else "rejected_by_seller"
    now = datetime.now(timezone.utc)
    await db[LISTINGS].update_one({"_id": oid}, {"$set": {"status": new_status, "updated_at": now}})
    await db[AUDIT_LOG].insert_one({
        "actor": doc.get("seller_id"),
        "action": "approve_publish" if decision.approved else "reject",
        "listing_id": oid,
        "payload": {"notes": decision.notes},
        "ts": now,
    })
    return {"id": listing_id, "status": new_status}
