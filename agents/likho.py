"""Likho — the pen. Turns Suno's facts into a marketplace-ready listing.

When the compliance loop hands it a required disclaimer, that text MUST land
verbatim at the end of the description.
"""
import json

from llm import llm_json


def _fallback(suno, append_disclaimer=None, revision_note=None, size_guide=None):
    product = suno.get("product_name") or "handmade product"
    category = suno.get("category") or "handmade"
    material = suno.get("material")
    qty = suno.get("quantity")
    title = product.title()
    bits = [f"Handmade {product} lovingly crafted by a rural woman seller."]
    if material:
        bits.append(f"Made from {material}, chosen for everyday durability.")
    if qty:
        bits.append(f"Available quantity: {qty} pieces.")
    bits.append("Ideal for buyers who value honest craft, clear details, and careful packing.")
    if revision_note:
        # Quality re-run: add a benefit line so the listing reads fuller.
        bits.append("Each piece carries the small variations that mark genuine handwork.")
    description = " ".join(bits)
    if size_guide:
        description = (description.rstrip() + " " + size_guide).strip()
    if append_disclaimer:
        description = (description.rstrip() + " " + append_disclaimer).strip()
    keywords = [
        "handmade",
        "women seller",
        "rural craft",
        product,
        category.replace("_", " "),
        "handcrafted",
    ]
    return {
        "title": title,
        "description": description,
        "category": category,
        "keywords": keywords[:8],
        "maker_story": "Made with care by a woman artisan preparing her product for online buyers.",
        "appended_disclaimers": [append_disclaimer] if append_disclaimer else [],
        "demo_fallback_used": True,
    }


def run(suno, append_disclaimer=None, revision_note=None, size_guide=None):
    """Write / rewrite a listing.

    suno             : dict from Suno.
    append_disclaimer: compliance loop — exact label text to append verbatim.
    revision_note    : quality loop — Mukhiya's instruction to make it richer.
    size_guide       : returns loop — size/fit guidance to append.
    """
    disclaimer_rule = ""
    if append_disclaimer:
        disclaimer_rule = (
            "\n\nMANDATORY: The description MUST end with this exact legal/label text, "
            "word for word, unchanged:\n"
            f"\"{append_disclaimer}\"\n"
            "Also include that exact string as an item in appended_disclaimers."
        )
    revision_rule = ""
    if revision_note:
        revision_rule = (
            "\n\nREVISION REQUESTED by the editor — fix this before returning: "
            f"{revision_note}"
        )
    size_guide_rule = ""
    if size_guide:
        size_guide_rule = (
            "\n\nRETURN-PROOFING: weave this size/fit guidance naturally into the "
            f"description so buyers know what to expect: \"{size_guide}\""
        )

    prompt = f"""You are Likho, a warm, honest copywriter for a rural women's marketplace.
Write a listing from these product facts (JSON):
{json.dumps(suno, ensure_ascii=False)}

Guidance:
- Title: crisp, searchable, buyer-friendly.
- Description: 2-4 full sentences, true to the facts, no invented claims.
- maker_story: one authentic line honouring the woman artisan / SHG behind it.
- keywords: 5-8 useful search terms.
{revision_rule}{size_guide_rule}{disclaimer_rule}

Return STRICT JSON only, exactly these keys:
{{
  "title": "...",
  "description": "...",
  "category": "{suno.get('category', '')}",
  "keywords": ["...", "..."],
  "maker_story": "...",
  "appended_disclaimers": [{('"' + append_disclaimer + '"') if append_disclaimer else ''}]
}}"""

    try:
        result = llm_json(prompt)
    except Exception as exc:  # noqa: BLE001 - demo must remain runnable
        result = _fallback(
            suno, append_disclaimer=append_disclaimer,
            revision_note=revision_note, size_guide=size_guide,
        )
        result["fallback_reason"] = str(exc)

    # Belt-and-braces: guarantee the size guide is present (returns loop).
    if size_guide and size_guide not in result.get("description", ""):
        result["description"] = (result.get("description", "").rstrip() + " " + size_guide).strip()

    # Belt-and-braces: guarantee the disclaimer is actually present (compliance loop).
    if append_disclaimer:
        desc = result.get("description", "")
        if append_disclaimer not in desc:
            result["description"] = (desc.rstrip() + " " + append_disclaimer).strip()
        appended = result.get("appended_disclaimers") or []
        if append_disclaimer not in appended:
            appended.append(append_disclaimer)
        result["appended_disclaimers"] = appended
    else:
        result.setdefault("appended_disclaimers", [])

    return result


if __name__ == "__main__":
    demo = {
        "product_name": "handwoven jute bags",
        "quantity": 40,
        "cost_price_inr": 200,
        "material": "jute",
        "category": "handloom_textiles",
        "attributes": {"size": None, "colour": None},
    }
    print(json.dumps(run(demo), ensure_ascii=False, indent=2))
