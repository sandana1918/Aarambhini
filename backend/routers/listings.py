"""Listing lifecycle: run the agent crew, fetch, and the approval gate.

The heavy lifting is the existing LangGraph orchestrator at repo root; this
router persists its output and enforces approval-before-publish + an audit trail.
"""
import io
import uuid
import asyncio
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from PIL import Image
from fastapi import APIRouter, HTTPException, UploadFile, File, Form

from ..db import get_db, LISTINGS, AUDIT_LOG
from ..models import ApprovalDecision, ClarificationAnswers

router = APIRouter(prefix="/listings", tags=["listings"])


def _out(doc: dict) -> dict:
    doc["id"] = str(doc.pop("_id"))
    if doc.get("seller_id"):
        doc["seller_id"] = str(doc["seller_id"])
    return doc


def _listing_fields(result: dict) -> dict:
    """The listing document fields derived from a (possibly paused) graph result."""
    return {
        "status": result.get("status"),
        "suno": result.get("suno"),
        "product_attributes": result.get("product_attributes"),
        "missing_attributes": result.get("missing_attributes", []),
        "clarification": result.get("clarification"),
        "listing": result.get("listing"),
        "price": result.get("price"),
        "compliance": result.get("compliance"),
        "returns": result.get("returns"),
        "packaging_plan": result.get("packaging_plan"),
        "action_checklist": result.get("action_checklist", []),
        "approvals": result.get("approvals", []),
        "seller_notes": result.get("seller_notes"),
        "activity_log": [{"agent": name, "output": out} for name, out in result.get("log", [])],
        "reason": result.get("reason"),
    }


@router.post("/run")
async def run_listing(
    voice_text: str = Form(...),
    desired_margin_pct: int = Form(20),
    seller_id: Optional[str] = Form(None),
    photo: Optional[UploadFile] = File(None),
):
    """Run the agent crew on a voice note + one product photo (multipart)."""
    import orchestrator  # repo-root module; imported lazily so backend stays importable
    import graph_store

    # Validate the image, then store the bytes in GridFS — only a string ref
    # travels through the (checkpointed) graph.
    image_ref = None
    if photo is not None:
        raw = await photo.read()
        if raw:
            try:
                Image.open(io.BytesIO(raw)).verify()
            except Exception:
                raise HTTPException(status_code=400, detail="Could not read that image file.")
            image_ref = await asyncio.to_thread(
                graph_store.save_image, raw, photo.filename or "photo"
            )

    # A stable run id keys the checkpoint (so the run is resumable) and links the
    # listing to its graph thread.
    run_id = str(uuid.uuid4())
    result = await asyncio.to_thread(
        orchestrator.run, voice_text, image_ref, desired_margin_pct, run_id
    )

    db = get_db()
    now = datetime.now(timezone.utc)
    doc = {
        "seller_id": ObjectId(seller_id) if seller_id else None,
        "thread_id": run_id,
        "image_ref": image_ref,
        **_listing_fields(result),
        "version": 1,
        "created_at": now,
        "updated_at": now,
    }
    res = await db[LISTINGS].insert_one(doc)
    doc["_id"] = res.inserted_id
    return _out(doc)


@router.post("/{listing_id}/clarify")
async def clarify_listing(listing_id: str, answers: ClarificationAnswers):
    """Answer the blocking-gap questions and resume the paused run.

    The graph was paused at the clarify interrupt right after Suno; this resumes
    it with the seller's answers, which flow on through Likho → … → the approval
    interrupt, leaving the listing ready_for_approval.
    """
    import orchestrator
    import graph_store  # noqa: F401 - ensures the checkpointer client is available

    db = get_db()
    oid = ObjectId(listing_id)
    doc = await db[LISTINGS].find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Listing not found")
    if doc.get("status") != "needs_clarification":
        raise HTTPException(status_code=409, detail=f"Listing is '{doc.get('status')}', not awaiting clarification")
    thread_id = doc.get("thread_id")
    if not thread_id:
        raise HTTPException(status_code=409, detail="This listing has no resumable graph thread.")

    result = await asyncio.to_thread(
        orchestrator.resume, thread_id, answers.model_dump(exclude_none=True)
    )

    now = datetime.now(timezone.utc)
    update = {**_listing_fields(result), "updated_at": now}
    await db[LISTINGS].update_one({"_id": oid}, {"$set": update})
    updated = await db[LISTINGS].find_one({"_id": oid})
    return _out(updated)


@router.post("/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    """Speech-to-text: a seller voice note -> transcript, in the seller's own language.

    Same transcript then feeds /run, so voice and typed input share one pipeline.
    Gemini reads the audio natively (22 Indian languages); on failure we surface a
    clear error rather than a silent empty listing.
    """
    import llm  # repo-root module; imported lazily so the backend stays importable

    raw = await audio.read()
    if not raw:
        raise HTTPException(status_code=400, detail="The recording was empty — please try again.")

    try:
        result = await asyncio.to_thread(
            llm.transcribe_audio, raw, audio.content_type or "audio/wav"
        )
    except Exception as exc:  # noqa: BLE001 - report transcription failure clearly
        raise HTTPException(status_code=502, detail=f"Could not transcribe the audio: {exc}")

    text = result["text"]
    if not text:
        raise HTTPException(
            status_code=422,
            detail="Couldn't make out any speech — please record again in a quiet spot.",
        )
    return {"text": text, "detected_via": result["provider"]}


@router.get("/{listing_id}")
async def get_listing(listing_id: str):
    db = get_db()
    doc = await db[LISTINGS].find_one({"_id": ObjectId(listing_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Listing not found")
    return _out(doc)


@router.post("/{listing_id}/approve")
async def approve_listing(listing_id: str, decision: ApprovalDecision):
    """The approval gate — resumes the paused LangGraph run with the seller's
    decision. The graph was checkpointed at an interrupt() in the approval node;
    Command(resume=...) continues it to publish/reject, applying any edits.
    """
    import orchestrator
    import graph_store  # noqa: F401 - ensures the checkpointer client is available

    db = get_db()
    oid = ObjectId(listing_id)
    doc = await db[LISTINGS].find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Listing not found")
    if doc.get("status") != "ready_for_approval":
        raise HTTPException(status_code=409, detail=f"Listing is '{doc.get('status')}', not awaiting approval")
    thread_id = doc.get("thread_id")
    if not thread_id:
        raise HTTPException(status_code=409, detail="This listing has no resumable graph thread.")

    decision_payload = {
        "approved": decision.approved,
        "notes": decision.notes,
        "edits": decision.edits.model_dump(exclude_none=True) if decision.edits else None,
    }
    result = await asyncio.to_thread(orchestrator.resume, thread_id, decision_payload)

    now = datetime.now(timezone.utc)
    new_status = result.get("status", "published" if decision.approved else "rejected_by_seller")
    update = {
        "status": new_status,
        "updated_at": now,
        "seller_notes": result.get("seller_notes"),
    }
    # Persist any edits the seller made at approval time.
    if result.get("price"):
        update["price"] = result["price"]
    if result.get("listing"):
        update["listing"] = result["listing"]
    if result.get("product_attributes"):
        update["product_attributes"] = result["product_attributes"]
    update["activity_log"] = [
        {"agent": name, "output": out} for name, out in result.get("log", [])
    ]

    await db[LISTINGS].update_one({"_id": oid}, {"$set": update})
    await db[AUDIT_LOG].insert_one({
        "actor": doc.get("seller_id"),
        "action": "approve_publish" if decision.approved else "reject",
        "listing_id": oid,
        "payload": decision_payload,
        "ts": now,
    })
    return {"id": listing_id, "status": new_status}
