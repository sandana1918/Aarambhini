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


def checkpointer():
    """The MongoDB-backed LangGraph checkpointer (durable pause/resume/history)."""
    global _checkpointer
    if _checkpointer is None:
        from langgraph.checkpoint.mongodb import MongoDBSaver

        _checkpointer = MongoDBSaver(_get_client(), db_name=_DB_NAME)
    return _checkpointer
