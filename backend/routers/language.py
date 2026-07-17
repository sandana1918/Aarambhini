"""Her language — translation and speech for the review surface.

The listing publishes in English; this is only so she can understand what she
is being asked to vouch for. Both routes default to her registered
preferred_language, which the app has always collected and never used.
"""
import asyncio

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from ..auth import current_seller
from ..db import get_db, SELLERS
from ..models import SpeakRequest, TranslateRequest

router = APIRouter(prefix="/language", tags=["language"])

# Translating a whole listing is a handful of short strings; a cap keeps one
# request from turning into a bulk translation job on someone else's key.
_MAX_TEXTS = 12


async def _seller_language(seller_id: str) -> str:
    db = get_db()
    doc = await db[SELLERS].find_one({"_id": ObjectId(seller_id)}, {"preferred_language": 1})
    return (doc or {}).get("preferred_language") or "en"


@router.post("/translate")
async def translate_texts(payload: TranslateRequest, seller_id: str = Depends(current_seller)):
    """English -> her language, for reading only.

    Returns the original text on any failure rather than a blank — a missing
    translation must read as "untranslated", never as "nothing to check".
    """
    import llm  # repo-root seam; lazy so the backend stays importable

    if not payload.texts:
        return {"language": "en", "translations": []}
    if len(payload.texts) > _MAX_TEXTS:
        raise HTTPException(status_code=422, detail=f"At most {_MAX_TEXTS} texts per request.")

    lang = payload.to or await _seller_language(seller_id)

    def work():
        return [llm.translate(t, lang) for t in payload.texts]

    results = await asyncio.to_thread(work)
    return {
        "language": lang,
        "translations": [
            {"original": src, "text": r["text"], "provider": r["provider"]}
            for src, r in zip(payload.texts, results)
        ],
    }


@router.post("/speak")
async def speak_text(payload: SpeakRequest, seller_id: str = Depends(current_seller)):
    """Text -> spoken WAV, in her language.

    The point of the whole feature: a translation she cannot read is still a
    wall. 404 (not 500) when speech is unavailable, so the UI can simply hide
    the button instead of showing her a broken one.
    """
    import llm

    lang = payload.lang or await _seller_language(seller_id)
    audio = await asyncio.to_thread(llm.speak, payload.text, lang)
    if not audio:
        raise HTTPException(status_code=404, detail="No speech available for that text.")
    return Response(
        content=audio,
        media_type="audio/wav",
        headers={"Cache-Control": "no-store"},
    )
