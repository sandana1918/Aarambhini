"""Vivran — the cataloguer. Fills the category's Meesho-style product attributes.

Real marketplaces need structured, buyer-facing fields per category (gender, size,
colour, fabric/material, pattern, …), not just prose. Vivran reads the category's
attribute spec, fills what it can from the seller's words + the photo (Gemini vision
infers colour/pattern/type), applies safe defaults (country of origin = India), and
reports which REQUIRED fields are still missing so the seller can complete them.
"""
import os
import json

from llm import llm_json

_SPEC_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "listing_attributes.json")

_spec = None


def _load_spec():
    global _spec
    if _spec is None:
        with open(_SPEC_PATH, encoding="utf-8") as f:
            _spec = json.load(f)
    return _spec


def _fields_for(category):
    """common attributes + the category's own, in display order."""
    spec = _load_spec()
    common = spec.get("common", [])
    cat = spec.get("categories", {}).get(category, {})
    return common + cat.get("attributes", [])


def _is_fixed(f):
    """A constant field (e.g. country of origin = India) — never guessed or asked."""
    return f.get("type") == "fixed" or f.get("infer") == "fixed"


def _deterministic(fields, suno):
    """Fill what we can with no model — used as fallback and as a safety net."""
    out = {}
    attrs = suno.get("attributes", {}) or {}
    for f in fields:
        key, infer = f["key"], f.get("infer")
        if _is_fixed(f):
            out[key] = f.get("value")
        elif key == "color":
            out[key] = attrs.get("colour") or None
        elif key in ("net_quantity",):
            qty = suno.get("quantity")
            out[key] = str(qty) if qty else f.get("default")
        elif key in ("fabric", "material", "wax_type") and suno.get("material"):
            out[key] = suno.get("material")
        elif key == "size" and attrs.get("size"):
            out[key] = attrs.get("size")
        else:
            out[key] = None
    return out


def _missing_required(fields, values):
    missing = []
    for f in fields:
        if f.get("required"):
            v = values.get(f["key"])
            if v is None or v == "" or v == []:
                missing.append(f["label"])
    return missing


def run(suno, image=None):
    """suno: dict from Suno. image: PIL.Image | None. -> dict.

    Returns {attributes, missing_required, category}. attributes is keyed by the
    spec's field keys with human values (or null where unknown).
    """
    category = suno.get("category", "")
    fields = _fields_for(category)
    if not fields:
        return {"attributes": {}, "missing_required": [], "category": category}

    # Fixed values are never guessed.
    fixed = {f["key"]: f.get("value") for f in fields if _is_fixed(f)}
    askable = [f for f in fields if not _is_fixed(f)]

    spec_lines = []
    for f in askable:
        opts = f.get("options")
        constraint = f" (one of: {', '.join(opts)})" if opts else ""
        multi = " — you may return an array of the applicable options" if f.get("type") == "multi" else ""
        spec_lines.append(f'- "{f["key"]}" — {f["label"]}{constraint}{multi}')

    prompt = f"""You are Vivran, a cataloguing assistant for an Indian marketplace.
Fill in structured product attributes for this listing, matching the fields a real
Meesho catalogue needs. Use the seller's facts and the product PHOTO (if provided)
to determine colour, pattern, type, etc. Be honest: if you cannot tell a field from
the words or the image, return null for it — do NOT guess.

Product facts (JSON):
{json.dumps(suno, ensure_ascii=False)}

Fields to fill (return a JSON value for each key; null if unknown). For enum fields,
the value MUST be exactly one of the listed options (or null):
{chr(10).join(spec_lines)}

Return STRICT JSON only: an object mapping each key to its value or null."""

    try:
        filled = llm_json(prompt, image=image)
        if not isinstance(filled, dict):
            raise ValueError("expected an object")
    except Exception:  # noqa: BLE001 - demo must stay runnable without the model
        filled = _deterministic(askable, suno)

    # Merge: fixed values + model/deterministic values. Backfill any missing key
    # with the deterministic guess so the shape is always complete.
    det = _deterministic(fields, suno)
    attributes = {}
    for f in fields:
        key = f["key"]
        if key in fixed:
            attributes[key] = fixed[key]
        else:
            v = filled.get(key)
            attributes[key] = v if v not in (None, "", []) else det.get(key)

    return {
        "attributes": attributes,
        "missing_required": _missing_required(fields, attributes),
        "category": category,
    }


if __name__ == "__main__":
    demo = {
        "product_name": "handwoven jute bag",
        "quantity": 40,
        "cost_price_inr": 200,
        "material": "jute",
        "category": "handloom_textiles",
        "attributes": {"size": None, "colour": "blue and beige"},
    }
    print(json.dumps(run(demo), ensure_ascii=False, indent=2))
