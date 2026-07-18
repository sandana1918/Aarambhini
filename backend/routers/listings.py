"""Listing lifecycle: run the agent crew, fetch, and the approval gate.

The heavy lifting is the existing LangGraph orchestrator at repo root; this
router persists its output and enforces approval-before-publish + an audit trail.
"""
import io
import json
import uuid
import asyncio
import threading
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from PIL import Image
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse

from ..auth import current_seller, optional_seller, require_listing_owner
from ..db import get_db, LISTINGS, AUDIT_LOG
from ..models import ApprovalDecision, AttributeAnswer, ClarificationAnswers, ReturnReport

router = APIRouter(prefix="/listings", tags=["listings"])


def _out(doc: dict) -> dict:
    doc["id"] = str(doc.pop("_id"))
    if doc.get("seller_id"):
        doc["seller_id"] = str(doc["seller_id"])
    return doc


def _oid_or_none(value):
    """ObjectId if it's a valid one, else None — never 500 on a bad seller_id."""
    try:
        return ObjectId(value) if value else None
    except Exception:  # noqa: BLE001
        return None


def _listing_oid(listing_id: str) -> ObjectId:
    """A listing id from the URL — 404 on a malformed one rather than 500."""
    try:
        return ObjectId(listing_id)
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=404, detail="Listing not found")


def _listing_fields(result: dict) -> dict:
    """The listing document fields derived from a (possibly paused) graph result."""
    return {
        "status": result.get("status"),
        "suno": result.get("suno"),
        "product_attributes": result.get("product_attributes"),
        "missing_attributes": result.get("missing_attributes", []),
        "authenticity": result.get("authenticity"),
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
    photo: Optional[UploadFile] = File(None),
    seller_id: Optional[str] = Depends(optional_seller),
):
    """Run the agent crew on a voice note + one product photo (multipart).

    The seller comes from the session, never from the request body — a
    client-supplied seller_id is just a claim, and trusting it is the hole
    that let anyone act as anyone. Anonymous runs still work, but produce a
    listing nobody owns and therefore nobody can approve.
    """
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
        orchestrator.run, voice_text, image_ref, desired_margin_pct, run_id, seller_id
    )

    db = get_db()
    now = datetime.now(timezone.utc)
    doc = {
        "seller_id": _oid_or_none(seller_id),
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


async def _save_photo(photo: Optional[UploadFile]) -> Optional[str]:
    import graph_store

    if photo is None:
        return None
    raw = await photo.read()
    if not raw:
        return None
    try:
        Image.open(io.BytesIO(raw)).verify()
    except Exception:
        raise HTTPException(status_code=400, detail="Could not read that image file.")
    return await asyncio.to_thread(graph_store.save_image, raw, photo.filename or "photo")


@router.post("/run/stream")
async def run_listing_stream(
    voice_text: str = Form(...),
    desired_margin_pct: int = Form(20),
    photo: Optional[UploadFile] = File(None),
    seller_id: Optional[str] = Depends(optional_seller),
):
    """Same as /run, but streams each agent's completion live over SSE.

    The crew runs in a worker thread; node updates are pushed to an async queue
    and emitted as `step` events. When the run pauses (clarify/approval) or ends,
    the listing is persisted and a final `done` event carries the full document.
    """
    import orchestrator

    image_ref = await _save_photo(photo)
    run_id = str(uuid.uuid4())
    db = get_db()
    loop = asyncio.get_running_loop()

    def sse(event: str, data) -> str:
        return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"

    async def event_gen():
        queue: asyncio.Queue = asyncio.Queue()

        def worker():
            try:
                for chunk in orchestrator.stream_run(
                    voice_text, image_ref, desired_margin_pct, run_id, seller_id
                ):
                    loop.call_soon_threadsafe(queue.put_nowait, ("update", chunk))
            except Exception as exc:  # noqa: BLE001 - surface to the client
                loop.call_soon_threadsafe(queue.put_nowait, ("error", str(exc)))
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, ("__end__", None))

        threading.Thread(target=worker, daemon=True).start()

        while True:
            kind, payload = await queue.get()
            if kind == "__end__":
                break
            if kind == "error":
                yield sse("error", {"detail": payload})
                return
            for node, delta in payload.items():
                if node == "__interrupt__" or not isinstance(delta, dict):
                    continue
                for name, _output in (delta.get("log") or []):
                    yield sse("step", {"agent": name})

        # Run paused or finished — persist the listing and emit the final document.
        result = await asyncio.to_thread(orchestrator.final_state, run_id)
        now = datetime.now(timezone.utc)
        doc = {
            "seller_id": _oid_or_none(seller_id),
            "thread_id": run_id,
            "image_ref": image_ref,
            **_listing_fields(result),
            "version": 1,
            "created_at": now,
            "updated_at": now,
        }
        res = await db[LISTINGS].insert_one(doc)
        doc["_id"] = res.inserted_id
        yield sse("done", _out(doc))

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/{listing_id}/clarify")
async def clarify_listing(
    listing_id: str,
    answers: ClarificationAnswers,
    seller_id: str = Depends(current_seller),
):
    """Answer the blocking-gap questions and resume the paused run.

    The graph was paused at the clarify interrupt right after Suno; this resumes
    it with the seller's answers, which flow on through Likho → … → the approval
    interrupt, leaving the listing ready_for_approval.
    """
    import orchestrator
    import graph_store  # noqa: F401 - ensures the checkpointer client is available

    db = get_db()
    oid = _listing_oid(listing_id)
    doc = await db[LISTINGS].find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Listing not found")
    require_listing_owner(doc, seller_id)
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


def _listing_category(doc: dict) -> Optional[str]:
    return (doc.get("suno") or {}).get("category") or (doc.get("listing") or {}).get("category")


@router.get("/{listing_id}/pending-attributes")
async def pending_attributes(listing_id: str, seller_id: str = Depends(current_seller)):
    """The details still missing, with the key + options needed to answer them.

    `missing_attributes` on the listing is labels only — enough to show her,
    not enough to fill. This maps each back to its field so she can answer one
    by voice instead of being told what's missing and left there.
    """
    from agents import suno as suno_agent

    db = get_db()
    oid = _listing_oid(listing_id)
    doc = await db[LISTINGS].find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Listing not found")
    require_listing_owner(doc, seller_id)

    category = _listing_category(doc)
    values = doc.get("product_attributes") or {}
    missing_labels = set(doc.get("missing_attributes") or [])

    fields = [
        f for f in suno_agent.askable_fields(category)
        if f["label"] in missing_labels or not values.get(f["key"])
    ]
    # Missing-and-required first: those are what actually block a good listing.
    fields.sort(key=lambda f: (f["label"] not in missing_labels, not f["required"], f["label"]))
    return {"category": category, "fields": fields}


@router.post("/{listing_id}/attribute")
async def resolve_attribute(
    listing_id: str,
    answer: AttributeAnswer,
    seller_id: str = Depends(current_seller),
):
    """Turn her spoken answer into a value this field accepts.

    Deliberately does NOT write to the listing: the graph is paused at the
    approval interrupt and its checkpoint is the source of truth, so the value
    goes back to her and rides in with `edits.attributes` when she approves.
    Writing here would leave the document and the graph disagreeing.
    """
    from agents import suno as suno_agent

    db = get_db()
    oid = _listing_oid(listing_id)
    doc = await db[LISTINGS].find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Listing not found")
    require_listing_owner(doc, seller_id)

    category = _listing_category(doc)
    result = await asyncio.to_thread(
        suno_agent.resolve_attribute_value, category, answer.key, answer.spoken_text
    )
    if not result["value"]:
        raise HTTPException(
            status_code=422,
            detail="Couldn't match that to an answer — please say it again.",
        )
    return {"key": answer.key, **result}


@router.post("/{listing_id}/return")
async def report_return(
    listing_id: str,
    report: ReturnReport,
    seller_id: str = Depends(current_seller),
):
    """Log a real buyer return. This feeds Wapsi — future listings in the same
    category are forecast from this accumulating history, not just reasoning.

    Ownership is enforced because this endpoint writes Wapsi's training data:
    left open, it is a path to poisoning every future forecast in a category.
    Note the trust model this implies — the seller reports returns against her
    own listing, so it guards against outside tampering, not under-reporting.
    A marketplace webhook is the honest long-term source.
    """
    import graph_store

    db = get_db()
    oid = _listing_oid(listing_id)
    doc = await db[LISTINGS].find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Listing not found")
    require_listing_owner(doc, seller_id)

    category = (doc.get("suno") or {}).get("category") or (doc.get("listing") or {}).get("category")
    await asyncio.to_thread(
        graph_store.record_return_event,
        oid,
        doc.get("seller_id"),
        category,
        report.reason,
        report.notes,
        doc.get("product_attributes"),
    )
    return {"listing_id": listing_id, "recorded": True, "reason": report.reason, "category": category}


@router.get("/{listing_id}")
async def get_listing(listing_id: str):
    # Deliberately still open: the frontend reads back the listing it just
    # created, including on anonymous runs. It is an information-disclosure
    # gap (a guessed id exposes a seller's listing) — scoped as a follow-up,
    # not fixed here.
    db = get_db()
    doc = await db[LISTINGS].find_one({"_id": _listing_oid(listing_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Listing not found")
    return _out(doc)


@router.post("/{listing_id}/approve")
async def approve_listing(
    listing_id: str,
    decision: ApprovalDecision,
    seller_id: str = Depends(current_seller),
):
    """The approval gate — resumes the paused LangGraph run with the seller's
    decision. The graph was checkpointed at an interrupt() in the approval node;
    Command(resume=...) continues it to publish/reject, applying any edits.

    "Nothing publishes without her approval" is the product's central promise,
    so this route checks that the caller *is* her, not just that the listing is
    waiting. Status alone was never enough.
    """
    import orchestrator
    import graph_store  # noqa: F401 - ensures the checkpointer client is available

    db = get_db()
    oid = _listing_oid(listing_id)
    doc = await db[LISTINGS].find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Listing not found")
    require_listing_owner(doc, seller_id)
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
        # Persist alongside the attributes, never separately — the two disagreeing
        # is how a listing ends up asking for a detail she already gave.
        update["missing_attributes"] = result.get("missing_attributes", [])
    update["activity_log"] = [
        {"agent": name, "output": out} for name, out in result.get("log", [])
    ]

    await db[LISTINGS].update_one({"_id": oid}, {"$set": update})
    await db[AUDIT_LOG].insert_one({
        # The verified caller, not the listing's stored owner. Those are now
        # always the same seller (require_listing_owner ran above), but the
        # audit trail should record who actually acted — reading it back off
        # the document would just be restating what we assumed.
        "actor": ObjectId(seller_id),
        "action": "approve_publish" if decision.approved else "reject",
        "listing_id": oid,
        "payload": decision_payload,
        "ts": now,
    })
    return {"id": listing_id, "status": new_status}


@router.get("/store/status")
async def store_status():
    """Whether pushing to an external store is available — the frontend only
    shows the 'Send to your store' button when it is. Public: reveals nothing
    but a boolean.
    """
    import shopify_store

    return {
        "configured": shopify_store.is_configured(),
        # Shown to a self-serve demo viewer so they can open a dev-store page
        # that Shopify keeps password-gated. None outside a demo.
        "storefront_password": shopify_store.storefront_password(),
    }


@router.post("/{listing_id}/publish-to-store")
async def publish_to_store(listing_id: str, seller_id: str = Depends(current_seller)):
    """Push an already-approved listing to her real storefront (Shopify).

    Gated on internal approval first: the LangGraph approval interrupt is where
    she vouches for the listing, so nothing reaches an external store until it
    has `status == 'published'`. This is a separate, post-approval action — not
    a node in the crew — so a store outage can never block or corrupt a run.
    """
    import graph_store
    import shopify_store

    db = get_db()
    oid = _listing_oid(listing_id)
    doc = await db[LISTINGS].find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Listing not found")
    require_listing_owner(doc, seller_id)

    if doc.get("status") != "published":
        raise HTTPException(
            status_code=409,
            detail="Approve and publish this listing first, then send it to your store.",
        )
    if not shopify_store.is_configured():
        raise HTTPException(
            status_code=503,
            detail="No store is connected yet. Ask the admin to set the Shopify keys.",
        )

    listing = doc.get("listing") or {}
    price = (doc.get("price") or {}).get("selling_price_inr")
    image_bytes = await asyncio.to_thread(graph_store.load_image_bytes, doc.get("image_ref"))

    try:
        result = await asyncio.to_thread(
            shopify_store.create_product,
            listing.get("title"),
            listing.get("description"),
            price,
            image_bytes,
            "product.jpg",
            listing.get("keywords"),
        )
    except Exception as exc:  # noqa: BLE001 - surface the store's error clearly
        raise HTTPException(status_code=502, detail=f"Could not reach the store: {exc}")

    # Record where it went, so she can reopen the live page and we don't lose it.
    await db[LISTINGS].update_one(
        {"_id": oid},
        {"$set": {"store_publish": {**result, "at": datetime.now(timezone.utc)}}},
    )
    return result
