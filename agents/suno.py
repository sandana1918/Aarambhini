"""Suno — the ear + cataloguer. Voice/text (any Indian language) + photo -> facts.

One vision call does three jobs:
  1. Intake — product name, quantity, cost, material, category, language.
  2. Photo gate — judges the photo and rejects bad ones early.
  3. Structured attributes — fills the category's Meesho-style catalogue fields
     (gender, size, colour, fabric/material, pattern, …) from the same words +
     photo, so we don't read the image twice.

(Formerly two agents, Suno + Vivran; merged to save a second vision call.)
"""
import os
import json
import re

from llm import llm_json

_RULES_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "compliance_rules.json")
_ATTR_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "listing_attributes.json")

_rules = None
_attr_spec = None


# ------------------------------------------------------------------ data loads
def _load_rules():
    global _rules
    if _rules is None:
        with open(_RULES_PATH, encoding="utf-8") as f:
            _rules = json.load(f)
    return _rules


def _load_attr_spec():
    global _attr_spec
    if _attr_spec is None:
        with open(_ATTR_PATH, encoding="utf-8") as f:
            _attr_spec = json.load(f)
    return _attr_spec


def _category_hints():
    lines = []
    for key, val in _load_rules()["categories"].items():
        lines.append(f"- {key}: {', '.join(val.get('aliases', []))}")
    return "\n".join(lines)


def known_categories():
    """[{key, label}] — the only categories Niyam has law for.

    Used to offer the seller a choice when the category can't be determined.
    """
    return [
        {"key": key, "label": val.get("label") or key}
        for key, val in _load_rules()["categories"].items()
    ]


def _is_known_category(key):
    return isinstance(key, str) and key in _load_rules()["categories"]


def _pick_category(voice_text):
    """-> a category key, or None when nothing matches.

    None is the important part. This used to return "handicrafts_decor" when no
    alias matched, which meant a seller whose words missed the food aliases
    silently became a handicraft — and handicrafts require no FSSAI, so Niyam
    would never ask for it and she'd publish food believing she was compliant.
    A wrong category is wrong *law*, so an unknown one has to reach her as a
    question (see _blocking_gaps) rather than be guessed here.

    Note this is substring-first-match over dict order, so it is a hint, not a
    classification: "jute bag" legitimately matches both handloom and bags.
    """
    text = voice_text.lower()
    for key, val in _load_rules()["categories"].items():
        if any(alias.lower() in text for alias in val.get("aliases", [])):
            return key
    return None


def resolve_category(raw_category, voice_text, confidence=None):
    """The model's category if it's real AND trustworthy, else the alias hint, else None.

    Two ways this returns None — both meaning "ask her":

    * The model returned an unrecognised key. It must not reach Niyam, which
      would find no rules for it and report no labels or licences at all.
    * The model said "low" and her own words don't corroborate it. A confident
      guess is the dangerous case: asked to describe "this thing I make at
      home", the model answered `toys_games` — nothing in her words said toy.
      An uncorroborated low-confidence guess is worth one tap from her.

    An alias match in her own words counts as corroboration, so a low-confidence
    label she effectively said herself still passes without a question.
    """
    hint = _pick_category(voice_text)
    if _is_known_category(raw_category):
        if str(confidence).lower() == "low" and hint != raw_category:
            return None
        return raw_category
    return hint


def attributes_for(category, raw=None, material=None):
    """Public seam so the graph can rebuild attributes once a clarified
    category is known — they're category-specific and were computed before.
    """
    return _finalize_attributes(category, raw, material)


def missing_for(category, values):
    """Which required fields are still empty -> their labels.

    Needed after she fills one in at approval: merging her answer without
    recomputing this leaves the listing saying a detail is missing that she
    just provided.
    """
    return _missing_required(_attr_fields_for(category), values or {})


def askable_fields(category):
    """[{key, label, type, options, required}] she could still be asked about.

    `missing_attributes` carries labels only ("Age Group"), which is enough to
    show her but not to fill anything — this maps back to the key and, for an
    enum, the exact options the marketplace accepts.
    """
    return [
        {
            "key": f["key"],
            "label": f["label"],
            "type": f.get("type", "text"),
            "options": f.get("options") or [],
            "required": bool(f.get("required")),
        }
        for f in _attr_fields_for(category)
        if not _is_fixed(f)
    ]


def resolve_attribute_value(category, key, spoken_text):
    """Her spoken answer -> a value this field will accept.

    She says "for small children, about two years old"; the marketplace wants
    exactly "1.5-3 Years". For an enum the model must pick one of the listed
    options or nothing — never invent a sixth. Free-text fields keep her own
    words, tidied.

    Returns {"value": str|None, "provider": "gemini"|"verbatim"|"none"}.
    """
    field = next((f for f in askable_fields(category) if f["key"] == key), None)
    said = (spoken_text or "").strip()
    if not field or not said:
        return {"value": None, "provider": "none"}

    options = field["options"]
    if options:
        listed = "\n".join(f"- {o}" for o in options)
        prompt = (
            f"A seller was asked for the '{field['label']}' of her product and answered, "
            f"in her own words:\n\"\"\"{said}\"\"\"\n\n"
            f"Choose the ONE option that matches what she meant:\n{listed}\n\n"
            'Return STRICT JSON: {"value": "<exactly one option above, or null if '
            'her answer does not match any>"}. Never invent an option.'
        )
    else:
        prompt = (
            f"A seller was asked for the '{field['label']}' of her product and answered, "
            f"in her own words:\n\"\"\"{said}\"\"\"\n\n"
            "Return STRICT JSON: {\"value\": \"<her answer as a short marketplace field "
            'value in English, or null if she gave no usable answer>"}. Keep her meaning; '
            "do not embellish."
        )

    try:
        raw = llm_json(prompt)
        value = (raw or {}).get("value")
        value = value.strip() if isinstance(value, str) else None
        if options and value not in options:
            value = None  # a hallucinated option is worse than asking again
        if value:
            return {"value": value, "provider": "gemini"}
    except Exception:  # noqa: BLE001 - fall through to her own words
        pass

    # Model unavailable or unhelpful. For free text her words are still the
    # best answer we have; for an enum we cannot honestly pick, so we don't.
    if not options:
        return {"value": said[:80], "provider": "verbatim"}
    return {"value": None, "provider": "none"}


# ------------------------------------------------------------- attribute spec
def _attr_fields_for(category):
    """common attributes + the category's own, in display order.

    No category → no fields. The common ones alone would be a half-filled
    attribute set built on a category we don't know yet; the graph rebuilds
    these via attributes_for() once she's told us which it is.
    """
    if not category:
        return []
    spec = _load_attr_spec()
    return spec.get("common", []) + spec.get("categories", {}).get(category, {}).get("attributes", [])


def _is_fixed(f):
    """A constant field (e.g. country of origin = India) — never guessed or asked."""
    return f.get("type") == "fixed" or f.get("infer") == "fixed"


# Fields the model should NOT fill — derived deterministically instead.
_MODEL_SKIP = {"net_quantity"}


def _compact_attr_spec():
    """Per-category askable fields (with enum options) to inject into the prompt."""
    spec = _load_attr_spec()
    common = [f for f in spec.get("common", []) if not _is_fixed(f) and f["key"] not in _MODEL_SKIP]
    lines = []
    for cat, body in spec.get("categories", {}).items():
        fields = [f for f in common + body.get("attributes", []) if f["key"] not in _MODEL_SKIP]
        parts = []
        for f in fields:
            opts = f.get("options")
            parts.append(f"{f['key']}[{'|'.join(opts)}]" if opts else f["key"])
        lines.append(f"- {cat}: {', '.join(parts)}")
    return "\n".join(lines)


def _missing_required(fields, values):
    missing = []
    for f in fields:
        if f.get("required"):
            v = values.get(f["key"])
            if v is None or v == "" or v == []:
                missing.append(f["label"])
    return missing


def _deterministic_attrs(fields, material, size, colour):
    """Fill what we can with no model — fallback and safety net."""
    out = {}
    for f in fields:
        key = f["key"]
        if _is_fixed(f):
            out[key] = f.get("value")
        elif key == "color":
            out[key] = colour
        elif key == "net_quantity":
            # Units the BUYER receives per order — default 1, not the seller's
            # stock count (that lives in suno.quantity). The model may still set
            # "Pack of N" if the seller actually sells in multipacks.
            out[key] = f.get("default", "1")
        elif key in ("fabric", "material", "wax_type") and material:
            out[key] = material
        elif key == "size" and size:
            out[key] = size
        else:
            out[key] = None
    return out


def _finalize_attributes(category, raw, material):
    """Merge model output with fixed values + deterministic backfill; report gaps."""
    fields = _attr_fields_for(category)
    if not fields:
        return {}, []
    raw = raw if isinstance(raw, dict) else {}
    det = _deterministic_attrs(fields, material, raw.get("size"), raw.get("color"))

    attributes = {}
    for f in fields:
        key = f["key"]
        if _is_fixed(f):
            attributes[key] = f.get("value")
        elif key in _MODEL_SKIP:
            attributes[key] = det.get(key)  # derived, never the model's guess
        else:
            v = raw.get(key)
            attributes[key] = v if v not in (None, "", []) else det.get(key)
    return attributes, _missing_required(fields, attributes)


# ------------------------------------------------------------------ price help
_RUPEE_WORDS = r"rs\.?|rupees?|rupee|₹|ரூபாய்|ரூபா|रुपये|रुपए|রুপি|টাকা|রুপয়া|ರೂಪಾಯಿ|రూపాయలు|രൂപ"


def _extract_rupees(text):
    """Pull a stated money amount out of the text, in any Indian script.

    A seller often says just '₹200' without the word 'cost' — that amount must
    not be dropped. Prefer a number attached to a rupee symbol/word.
    """
    m = re.search(r"₹\s*([0-9]+)", text)
    if m:
        return int(m.group(1))
    m = re.search(r"([0-9]+)\s*(?:" + _RUPEE_WORDS + r")", text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    m = re.search(r"(?:" + _RUPEE_WORDS + r")\s*([0-9]+)", text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None


# ------------------------------------------------------------------ photo gate
def _photo_quality(image):
    if image is None:
        return False, "no photo provided, please upload one clear product photo"
    try:
        gray = image.convert("L")
        pixels = list(gray.resize((32, 32)).getdata())
        brightness = sum(pixels) / len(pixels)
        if brightness < 35:
            return False, "too dark, retake near a window"
        if min(image.size) < 180:
            return False, "photo is too small, move closer and retake"
    except Exception:
        return True, None
    return True, None


# ------------------------------------------------------------------- fallback
_NAME_BY_CATEGORY = {
    "handloom_textiles": "handwoven jute bag",
    "apparel_readymade": "readymade garment",
    "food_packaged": "homemade food product",
    "jewellery_precious": "precious jewellery",
    "imitation_jewellery": "imitation jewellery",
    "cosmetics_handmade": "handmade soap",
    "handicrafts_decor": "handmade decor item",
    "home_furnishing": "home furnishing item",
    "toys_games": "handmade toy",
    "bags_leather": "handmade bag",
    "ayurvedic_herbal": "herbal product",
    "candles_fragrance": "handmade candle",
    "stationery_paper": "handmade paper product",
}
_MATERIAL_BY_CATEGORY = {
    "handloom_textiles": "jute",
    "apparel_readymade": "cotton",
    "food_packaged": None,
    "jewellery_precious": "precious metal",
    "imitation_jewellery": "mixed material",
    "cosmetics_handmade": None,
    "handicrafts_decor": "terracotta or craft material",
    "home_furnishing": "cotton",
    "toys_games": "wood",
    "bags_leather": "jute",
    "ayurvedic_herbal": None,
    "candles_fragrance": "wax",
    "stationery_paper": "handmade paper",
}


def _fallback(voice_text, image):
    """Deterministic demo intake + attributes when the live model is unavailable."""
    category = _pick_category(voice_text)
    cost = _extract_rupees(voice_text)
    nums = [int(n) for n in re.findall(r"\d+", voice_text)]
    qty_candidates = [n for n in nums if n != cost]
    quantity = qty_candidates[0] if qty_candidates else (nums[0] if nums else None)
    if cost is None and len(nums) >= 2:
        cost = nums[-1]
    photo_ok, photo_issue = _photo_quality(image)
    detected_language = "hi" if re.search(r"[ऀ-ॿ]", voice_text) else "en"
    product_name = _NAME_BY_CATEGORY.get(category, "handmade product")
    material = _MATERIAL_BY_CATEGORY.get(category)

    product_attributes, missing = _finalize_attributes(category, {}, material)
    return {
        "product_name": product_name,
        "quantity": quantity,
        "cost_price_inr": cost,
        "material": material,
        "category": category,
        "attributes": {"size": None, "colour": product_attributes.get("color")},
        "photo_ok": photo_ok,
        "photo_issue": photo_issue,
        "photo_authenticity": "unsure",
        "authenticity_note": None,
        "detected_language": detected_language,
        "product_attributes": product_attributes,
        "missing_attributes": missing,
        "demo_fallback_used": True,
    }


# ------------------------------------------------------------------------ run
def run(voice_text, image=None):
    """voice_text: str (any language). image: PIL.Image | None. -> dict.

    Returns intake facts, the photo verdict, AND the category's structured
    attributes (product_attributes) + missing_attributes — all from one call.
    """
    has_image = image is not None
    photo_instruction = (
        "A product photo IS attached. Judge its quality honestly: if it is dark, "
        "blurry, cluttered, or the product is unclear, set photo_ok=false and give a "
        "short, kind photo_issue like 'too dark, retake near a window'. Otherwise "
        "photo_ok=true and photo_issue=null. Use the photo to fill visual attributes "
        "(colour, pattern, type). Also assess authenticity: does it look like an "
        "ORIGINAL phone photo of a real handmade product, or does it have a visible "
        "watermark/logo, look like a professional stock/catalogue image, or look "
        "AI-generated? Be conservative — a plain, slightly imperfect phone photo is "
        "'original'. Only flag clear cases."
        if has_image
        else "NO product photo was provided. Set photo_ok=false and photo_issue="
        "'no photo provided, please upload one clear product photo'."
    )

    prompt = f"""You are Suno, the intake agent for a marketplace helper serving rural
women sellers in India. A seller has described her product in her own language.

Seller's words:
\"\"\"{voice_text}\"\"\"

{photo_instruction}

STEP 1 — Pick the single best category from this list, matching the seller's words
against the aliases:
{_category_hints()}

Do NOT choose the closest one when you are unsure. Set "category" to null instead, and
say so in "category_confidence". This category decides which Indian law applies to her
— the labels she must print and whether she is asked for an FSSAI, BIS or AYUSH licence.
Guessing does not help her: if you guess wrong she is told she is compliant when she is
not. If you return null she is simply shown the list and picks it herself, which costs
her one tap. Use "high" only when her words or the photo clearly indicate the category;
otherwise "low".

STEP 2 — Fill the structured attributes for THE CATEGORY YOU PICKED, using only that
category's fields below. For a field marked [opt1|opt2|...], choose exactly one listed
option (or null). Use the photo for visual fields; leave a field null if you truly
cannot tell — never guess:
{_compact_attr_spec()}

IMPORTANT about price: if the seller states ANY amount in rupees (₹, "rupees", or the
word for rupees in her language), capture that number as cost_price_inr — this is the
base amount we price from. Only use null if she mentions no amount at all.

IMPORTANT about net_quantity: this is how many identical items the buyer receives in
ONE order — use "1" unless the seller clearly sells a fixed set/multipack. A count of
pieces she has made or has in stock (e.g. "4 pieces", "40 bags") is NOT net_quantity;
put that stock count in "quantity" instead.

Return STRICT JSON only, exactly these keys:
{{
  "product_name": "<short product name in English>",
  "quantity": <integer number of pieces, or null if not stated>,
  "cost_price_inr": <integer rupee amount the seller stated, or null>,
  "material": "<main material, or null>",
  "category": "<one of the category keys above, or null if not clearly indicated>",
  "category_confidence": "<high | low>",
  "photo_ok": <true or false>,
  "photo_issue": <short string or null>,
  "photo_authenticity": "<original | watermarked | stock_or_catalogue | likely_ai | unsure>",
  "authenticity_note": <short reason or null>,
  "detected_language": "<ISO code like hi, en, ta, bn>",
  "product_attributes": {{ <the chosen category's field keys>: <value or null> }}
}}"""

    try:
        raw = llm_json(prompt, image=image)
        if not isinstance(raw, dict):
            raise ValueError("expected an object")
    except Exception as exc:  # noqa: BLE001 - demo must remain runnable
        result = _fallback(voice_text, image)
        result["fallback_reason"] = str(exc)
        return result

    category = resolve_category(
        raw.get("category"), voice_text, raw.get("category_confidence")
    )
    quantity = raw.get("quantity")
    material = raw.get("material")
    product_name = raw.get("product_name") or "handmade product"

    # Price safety net: never drop a stated ₹ amount.
    cost = raw.get("cost_price_inr")
    if not cost:
        cost = _extract_rupees(voice_text)

    product_attributes, missing = _finalize_attributes(
        category, raw.get("product_attributes"), material
    )
    return {
        "product_name": product_name,
        "quantity": quantity,
        "cost_price_inr": cost,
        "material": material,
        "category": category,
        "attributes": {"size": product_attributes.get("size"), "colour": product_attributes.get("color")},
        "photo_ok": bool(raw.get("photo_ok")),
        "photo_issue": raw.get("photo_issue"),
        "photo_authenticity": raw.get("photo_authenticity") or "original",
        "authenticity_note": raw.get("authenticity_note"),
        "detected_language": raw.get("detected_language"),
        "product_attributes": product_attributes,
        "missing_attributes": missing,
    }


if __name__ == "__main__":
    example = "நான் ஜூட் பேக் செஞ்சிருவேன். நாலு பீஸ் ₹200 ஸ்மால் சைஸ்."
    print(json.dumps(run(example), ensure_ascii=False, indent=2))
