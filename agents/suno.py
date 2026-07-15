"""Suno — the ear. Voice/text (any Indian language) + photo -> structured facts.

Also the quality gate: judges the photo and rejects bad ones so nothing bad
flows downstream.
"""
import os
import json
import re

from llm import llm_json

_RULES_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "compliance_rules.json")


def _category_hints():
    with open(_RULES_PATH, encoding="utf-8") as f:
        rules = json.load(f)
    lines = []
    for key, val in rules["categories"].items():
        lines.append(f"- {key}: {', '.join(val.get('aliases', []))}")
    return "\n".join(lines)


def _pick_category(voice_text):
    text = voice_text.lower()
    with open(_RULES_PATH, encoding="utf-8") as f:
        rules = json.load(f)
    for key, val in rules["categories"].items():
        if any(alias.lower() in text for alias in val.get("aliases", [])):
            return key
    return "handicrafts_decor"


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


def _fallback(voice_text, image):
    """Deterministic demo intake when the live model is unavailable."""
    category = _pick_category(voice_text)
    nums = [int(n) for n in re.findall(r"\d+", voice_text)]
    quantity = nums[0] if nums else None
    cost = nums[-1] if nums else None
    photo_ok, photo_issue = _photo_quality(image)
    # Keys must match the canonical taxonomy in data/compliance_rules.json.
    name_by_category = {
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
    material_by_category = {
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
    detected_language = "hi" if re.search(r"[\u0900-\u097F]", voice_text) else "en"
    return {
        "product_name": name_by_category.get(category, "handmade product"),
        "quantity": quantity,
        "cost_price_inr": cost,
        "material": material_by_category.get(category),
        "category": category,
        "attributes": {"size": None, "colour": None},
        "photo_ok": photo_ok,
        "photo_issue": photo_issue,
        "detected_language": detected_language,
        "demo_fallback_used": True,
    }


def run(voice_text, image=None):
    """voice_text: str (any language). image: PIL.Image | None. -> dict."""
    has_image = image is not None
    photo_instruction = (
        "A product photo IS attached. Judge its quality honestly: if it is dark, "
        "blurry, cluttered, or the product is unclear, set photo_ok=false and give a "
        "short, kind photo_issue like 'too dark, retake near a window'. Otherwise "
        "photo_ok=true and photo_issue=null."
        if has_image
        else "NO product photo was provided. Set photo_ok=false and photo_issue="
        "'no photo provided, please upload one clear product photo'."
    )

    prompt = f"""You are Suno, the intake agent for a marketplace helper serving rural
women sellers in India. A seller has described her product in her own language.

Seller's words:
\"\"\"{voice_text}\"\"\"

{photo_instruction}

Pick the single best category from this list, matching the seller's words against
the aliases (fuzzy match is fine; if unsure, choose the closest):
{_category_hints()}

Extract the facts. Return STRICT JSON only, exactly these keys:
{{
  "product_name": "<short product name in English>",
  "quantity": <integer number of pieces, or null if not stated>,
  "cost_price_inr": <integer cost to make one piece in INR, or null if not stated>,
  "material": "<main material, or null>",
  "category": "<one of the category keys above>",
  "attributes": {{"size": <string or null>, "colour": <string or null>}},
  "photo_ok": <true or false>,
  "photo_issue": <short string or null>,
  "detected_language": "<ISO code like hi, en, ta, bn>"
}}"""

    try:
        return llm_json(prompt, image=image)
    except Exception as exc:  # noqa: BLE001 - demo must remain runnable
        result = _fallback(voice_text, image)
        result["fallback_reason"] = str(exc)
        return result


if __name__ == "__main__":
    example = "मैं हाथ से बने जूट बैग बनाती हूँ, 40 पीस, ₹200 लागत।"
    print(json.dumps(run(example), ensure_ascii=False, indent=2))
