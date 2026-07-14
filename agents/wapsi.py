"""Wapsi — the returns forecaster (light build).

One reasoning call about likely return drivers for this category. Honest framing:
it REASONS about returns and learns over time — it does not query any real
marketplace's return database.
"""
import json

from llm import llm_json


def _fallback(product_name, category, attributes):
    size = (attributes or {}).get("size")
    colour = (attributes or {}).get("colour")
    if category == "food":
        reason = "spoilage, leakage, or unclear ingredients"
        risk = "high"
        mitigations = [
            "add ingredients and best-before date clearly",
            "use leak-proof packing",
            "prefer regional delivery first",
        ]
        prompt = "Confirm ingredients, batch date, and best-before date before publishing."
    elif category == "handicrafts_decor":
        reason = "breakage in transit"
        risk = "medium"
        mitigations = [
            "wrap with cushioning",
            "show size in the listing",
            "add fragile handling note",
        ]
        prompt = "Confirm the exact size and packing material before publishing."
    else:
        reason = "size or colour mismatch"
        risk = "medium" if not (size and colour) else "low"
        mitigations = [
            "confirm exact colour shade",
            "add size or dimensions",
            "include a natural-light photo",
        ]
        prompt = None if size and colour else "Confirm the exact colour shade and size before publishing."
    return {
        "top_return_reason": reason,
        "risk_level": risk,
        "mitigations": mitigations,
        "needs_seller_confirmation": bool(prompt),
        "confirmation_prompt": prompt,
        "demo_fallback_used": True,
    }


def run(product_name, category, attributes):
    """-> dict."""
    prompt = f"""You are Wapsi. Reason about why THIS product is likely to be returned and
how to reduce that, drawing on general knowledge of Indian online-shopping return
patterns (you do NOT have this marketplace's actual return data).

Product: {product_name}
Category: {category}
Attributes: {json.dumps(attributes, ensure_ascii=False)}

Consider category-typical drivers (e.g. textiles/apparel -> size & colour mismatch;
fragile decor -> breakage in transit; food -> spoilage/taste). If a colour or size
assumption is uncertain, ask the seller to confirm it.

Return STRICT JSON only, exactly these keys:
{{
  "top_return_reason": "...",
  "risk_level": "low|medium|high",
  "mitigations": ["...", "...", "..."],
  "needs_seller_confirmation": <true or false>,
  "confirmation_prompt": "<a short question for the seller, or null>"
}}"""

    try:
        return llm_json(prompt)
    except Exception as exc:  # noqa: BLE001 - demo must remain runnable
        result = _fallback(product_name, category, attributes)
        result["fallback_reason"] = str(exc)
        return result


if __name__ == "__main__":
    print(
        json.dumps(
            run("handwoven jute bags", "handloom_textiles", {"size": None, "colour": None}),
            ensure_ascii=False,
            indent=2,
        )
    )
