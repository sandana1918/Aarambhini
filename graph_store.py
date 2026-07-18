"""Durable storage for the LangGraph run: image bytes + checkpoints.

Two things must live in a serializable store, not in graph state:

  * The product photo — a live PIL.Image cannot be checkpointed, so the bytes go
    to GridFS and only a string image_ref travels through the graph.
  * The checkpoints themselves — a MongoDB-backed MongoDBSaver so an interrupted
    or failed run resumes from its last successful node.

One sync pymongo client backs both (pymongo connects lazily, so importing this
module never blocks). Env-driven, like llm.py, so it needs no backend imports.
"""
import io
import os
from pathlib import Path

import certifi
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

_URI = os.getenv("MONGODB_URI")
_DB_NAME = os.getenv("DB_NAME", "aarambhini")

_client = None
_fs = None
_checkpointer = None


def _get_client():
    global _client
    if _client is None:
        if not _URI:
            raise RuntimeError("MONGODB_URI is not set. Add it to .env.")
        from pymongo import MongoClient

        # pymongo is lazy: this does not connect until the first operation.
        _client = MongoClient(_URI, tlsCAFile=certifi.where(), serverSelectionTimeoutMS=8000)
    return _client


def _get_fs():
    global _fs
    if _fs is None:
        import gridfs

        _fs = gridfs.GridFS(_get_client()[_DB_NAME], collection="product_images")
    return _fs


def save_image(data: bytes, filename: str = "photo") -> str:
    """Store raw image bytes in GridFS; return a string ref to keep in state."""
    return str(_get_fs().put(data, filename=filename))


def load_image_bytes(image_ref):
    """Raw image bytes for a ref, or None — for sending the photo to an external
    store (Shopify wants base64 of the original bytes, not a re-encoded PIL image).
    """
    if not image_ref:
        return None
    try:
        from bson import ObjectId

        return _get_fs().get(ObjectId(image_ref)).read()
    except Exception:  # noqa: BLE001 - a missing image just means no photo is sent
        return None


def load_image(image_ref):
    """Load a PIL.Image from a ref, or None. Never raises into the graph."""
    if not image_ref:
        return None
    try:
        from bson import ObjectId
        from PIL import Image

        data = _get_fs().get(ObjectId(image_ref)).read()
        img = Image.open(io.BytesIO(data))
        img.load()
        return img
    except Exception:  # noqa: BLE001 - a missing/corrupt image must not crash a node
        return None


def get_packer_label(seller_id):
    """A seller's {name, address} for the printed compliance label, or None.

    This has sat in every seller's profile since registration — packer_label is
    exactly what Legal Metrology wants for "Mfd by: <name>, <address>" — and
    nothing read it, so Niyam printed the placeholder itself: "Mfr: <Manufacturer
    Name>, <Full Address>". A label with blanks on it is not compliant; the data
    to fill them was one query away the whole time.

    Never raises into the graph: a missing/malformed seller_id (anonymous runs
    have none) just means Niyam falls back to a placeholder, same as before.
    """
    if not seller_id:
        return None
    try:
        from bson import ObjectId

        seller = _get_client()[_DB_NAME]["sellers"].find_one(
            {"_id": ObjectId(seller_id)}, {"packer_label": 1}
        )
        label = (seller or {}).get("packer_label") or {}
        name, address = label.get("name"), label.get("address")
        return {"name": name, "address": address} if name and address else None
    except Exception:  # noqa: BLE001 - a lookup failure must not crash a node
        return None


def checkpointer():
    """The MongoDB-backed LangGraph checkpointer (durable pause/resume/history)."""
    global _checkpointer
    if _checkpointer is None:
        from langgraph.checkpoint.mongodb import MongoDBSaver

        _checkpointer = MongoDBSaver(_get_client(), db_name=_DB_NAME)
    return _checkpointer


# ---------------------------------------------------- image authenticity (pHash)
def phash(image, hash_size: int = 8) -> str:
    """Perceptual dHash (difference hash) — pure PIL, no extra dependency.

    Resizes to grayscale (hash_size+1 × hash_size) and encodes whether each pixel
    is brighter than its right neighbour into 64 bits. Near-identical images (even
    resized/re-compressed) hash within a small Hamming distance; different products
    hash far apart.
    """
    small = image.convert("L").resize((hash_size + 1, hash_size))
    px = list(small.getdata())
    bits = 0
    for row in range(hash_size):
        for col in range(hash_size):
            left = px[row * (hash_size + 1) + col]
            right = px[row * (hash_size + 1) + col + 1]
            bits = (bits << 1) | (1 if left > right else 0)
    return f"{bits:016x}"


def _hamming(a: str, b: str) -> int:
    return bin(int(a, 16) ^ int(b, 16)).count("1")


def check_and_store_fingerprint(image, seller_id, image_ref, threshold: int = 6) -> dict:
    """Fingerprint a photo, look for a near-duplicate already in the system, and
    store it. A match under a DIFFERENT seller is the strong 'stolen photo' signal.

    Returns {phash, duplicate, cross_seller, duplicate_of_seller}.
    """
    from datetime import datetime, timezone

    col = _get_client()[_DB_NAME]["image_fingerprints"]
    ph = phash(image)

    dup = None
    # Prototype-scale linear scan; for production, bucket by hash prefix (LSH).
    for fp in col.find({}, {"phash": 1, "seller_id": 1, "image_ref": 1}).limit(5000):
        if fp.get("phash") and _hamming(ph, fp["phash"]) <= threshold:
            dup = fp
            break

    col.insert_one({
        "phash": ph,
        "seller_id": seller_id,
        "image_ref": image_ref,
        "created_at": datetime.now(timezone.utc),
    })

    cross_seller = bool(
        dup and seller_id and dup.get("seller_id") and str(dup["seller_id"]) != str(seller_id)
    )
    return {
        "phash": ph,
        "duplicate": bool(dup),
        "cross_seller": cross_seller,
        "duplicate_of_seller": str(dup["seller_id"]) if dup and dup.get("seller_id") else None,
    }


# ------------------------------------------------- returns feedback (Wapsi learns)
# Canonical return reasons, so history aggregates cleanly.
RETURN_REASONS = ("size_mismatch", "colour_mismatch", "damaged", "quality_issue",
                  "not_as_described", "late_or_lost", "other")


def record_return_event(listing_id, seller_id, category, reason, notes=None, attributes=None):
    """Log a real buyer return — this is what Wapsi learns from over time."""
    from datetime import datetime, timezone

    _get_client()[_DB_NAME]["return_events"].insert_one({
        "listing_id": listing_id,
        "seller_id": seller_id,
        "category": category,
        "reason": reason if reason in RETURN_REASONS else "other",
        "notes": notes,
        "attributes": attributes or {},
        "created_at": datetime.now(timezone.utc),
    })


def return_stats(category, limit: int = 1000) -> dict:
    """Aggregate a category's real return history for Wapsi to reason over."""
    from collections import Counter

    col = _get_client()[_DB_NAME]["return_events"]
    reasons = Counter()
    total = 0
    for e in col.find({"category": category}, {"reason": 1}).limit(limit):
        reasons[e.get("reason") or "other"] += 1
        total += 1
    ranked = reasons.most_common()
    return {
        "category": category,
        "total": total,
        "by_reason": dict(ranked),
        "top_reason": ranked[0][0] if ranked else None,
        # share of the single most common reason — a rough confidence signal
        "top_share": round(ranked[0][1] / total, 2) if total else 0.0,
    }
