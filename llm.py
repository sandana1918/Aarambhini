"""Single, swappable LLM wrapper for Aarambhini.

Everything goes through llm() / llm_json() so the provider is isolated in one
place. Gemini today; could become Azure OpenAI tomorrow without touching agents.
"""
import os
import re
import json
import time
from pathlib import Path

from dotenv import load_dotenv

# Explicit path so the agents work no matter what the working directory is.
load_dotenv(Path(__file__).resolve().parent / ".env")

_API_KEY = os.getenv("GEMINI_API_KEY")
_MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-flash-latest")

_client = None


def _get_client():
    global _client
    if _client is None:
        if not _API_KEY:
            raise RuntimeError(
                "GEMINI_API_KEY is not set. Copy .env.example to .env and add your key."
            )
        from google import genai

        _client = genai.Client(api_key=_API_KEY)
    return _client


def _is_rate_limit(exc):
    s = str(exc)
    return "RESOURCE_EXHAUSTED" in s or "429" in s


def _retry_delay_seconds(exc, default=6.0, cap=8.0):
    m = re.search(r"retry in ([0-9.]+)s", str(exc))
    delay = float(m.group(1)) if m else default
    return min(delay, cap)


def llm(prompt, image=None, rate_limit_retries=1):
    """The one place the provider lives.

    prompt : str
    image  : PIL.Image.Image | None  (Gemini reads it natively)
    returns: str  (raw model text)

    Swap providers by rewriting only this function. On a transient rate-limit
    (per-minute) it retries briefly; if the model is truly exhausted it raises,
    and the calling agent falls back to its deterministic path.
    """
    client = _get_client()
    contents = [prompt]
    if image is not None:
        contents.append(image)  # google-genai accepts PIL.Image objects directly
    for attempt in range(rate_limit_retries + 1):
        try:
            resp = client.models.generate_content(model=_MODEL_NAME, contents=contents)
            return resp.text
        except Exception as exc:  # noqa: BLE001
            if _is_rate_limit(exc) and attempt < rate_limit_retries:
                time.sleep(_retry_delay_seconds(exc))
                continue
            raise


_STT_PROVIDER = os.getenv("STT_PROVIDER", "gemini").lower()
_SARVAM_API_KEY = os.getenv("SARVAM_API_KEY")
_SARVAM_MODEL = os.getenv("SARVAM_STT_MODEL", "saarika:v2.5")
_SARVAM_URL = "https://api.sarvam.ai/speech-to-text"


def _transcribe_sarvam(audio_bytes, mime_type):
    """Sarvam Saarika STT — India-first, tuned for regional + code-mixed, noisy phone audio.

    Audio arrives as 16 kHz mono WAV (normalized in the browser), which Saarika
    accepts directly. language_code='unknown' lets Saarika auto-detect the language.
    """
    import requests

    resp = requests.post(
        _SARVAM_URL,
        headers={"api-subscription-key": _SARVAM_API_KEY},
        files={"file": ("voice-note.wav", audio_bytes, mime_type or "audio/wav")},
        data={"model": _SARVAM_MODEL, "language_code": "unknown"},
        timeout=60,
    )
    resp.raise_for_status()
    return (resp.json().get("transcript") or "").strip()


def _transcribe_gemini(audio_bytes, mime_type):
    """Gemini native audio — the fallback provider."""
    client = _get_client()
    from google.genai import types

    prompt = (
        "Transcribe this seller voice note exactly enough for product intake. "
        "Keep the original language/script when possible. Include product name, "
        "quantity, cost, material, size, colour, and any other selling details you hear. "
        "Return only the transcript text, no markdown."
    )
    audio_part = types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)
    resp = client.models.generate_content(model=_MODEL_NAME, contents=[prompt, audio_part])
    return (resp.text or "").strip()


def transcribe_audio(audio_bytes, mime_type="audio/wav"):
    """Transcribe a seller voice note into text for the same agent pipeline.

    Sarvam is primary (best for Indian regional + code-mixed, noisy field audio);
    Gemini is the automatic fallback so a Sarvam outage never breaks the flow.
    Set STT_PROVIDER=gemini to skip Sarvam entirely.

    Returns {"text": str, "provider": "sarvam" | "gemini" | "gemini_after_sarvam_error"}.
    """
    use_sarvam = _STT_PROVIDER == "sarvam" and _SARVAM_API_KEY
    if use_sarvam:
        try:
            return {"text": _transcribe_sarvam(audio_bytes, mime_type), "provider": "sarvam"}
        except Exception:  # noqa: BLE001 - fall back to Gemini on any Sarvam failure
            return {
                "text": _transcribe_gemini(audio_bytes, mime_type),
                "provider": "gemini_after_sarvam_error",
            }
    return {"text": _transcribe_gemini(audio_bytes, mime_type), "provider": "gemini"}


def _extract_json(text):
    """Pull a JSON object out of a model reply that may be fenced or chatty."""
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start : end + 1]
    return json.loads(text)


def llm_json(prompt, image=None, retries=2):
    """Call the model and return parsed JSON, retrying with a firmer nudge."""
    last_err = None
    attempt_prompt = prompt
    for _ in range(retries + 1):
        raw = llm(attempt_prompt, image=image)
        try:
            return _extract_json(raw)
        except Exception as e:  # noqa: BLE001 - we want any parse failure to retry
            last_err = e
            attempt_prompt = (
                prompt
                + "\n\nIMPORTANT: Reply with ONLY valid JSON — no prose, no markdown "
                "fences. Your previous reply could not be parsed."
            )
    raise ValueError(f"Model did not return valid JSON after {retries + 1} tries: {last_err}")


if __name__ == "__main__":
    # Smoke test: prove one text+image call works.
    print("Model:", _MODEL_NAME)
    print(llm("Reply with exactly: Aarambhini LLM wrapper is alive."))
