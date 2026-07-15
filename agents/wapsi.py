"""Wapsi — the returns forecaster that LEARNS from real returns.

Given the category's actual return history (passed in as `history` — an aggregate
from the return_events collection), Wapsi grounds its forecast on that data,
weighting it above general knowledge. With no history yet, it falls back to
category reasoning. It does NOT use any other marketplace's private return data —
only returns logged on Aarambhini itself.
"""
import json

from llm import llm_json

_REASON_LABEL = {
    "size_mismatch": "size mismatch",
    "colour_mismatch": "colour mismatch",
    "damaged": "damaged / broken in transit",
    "quality_issue": "quality not as expected",
    "not_as_described": "not as described",
    "late_or_lost": "late or lost delivery",
    "other": "other reasons",
}


def _history_line(history):
    """Human/LLM-readable summary of the category's real return history."""
    if not history or not history.get("total"):
        return None
    parts = [f"{_REASON_LABEL.get(r, r)}: {n}" for r, n in (history.get("by_reason") or {}).items()]
    return (f"Aarambhini's own return history for this category — {history['total']} past "
            f"returns: " + "; ".join(parts) + ".")


def _fallback(product_name, category, attributes, history):
    """Deterministic path. If we have return history, LEARN the top reason from it."""
    size = (attributes or {}).get("size")
    colour = (attributes or {}).get("colour")

    if history and history.get("total", 0) >= 3 and history.get("top_reason"):
        top = history["top_reason"]
        reason = _REASON_LABEL.get(top, top)
        # Confident data → higher risk; a spread-out history → medium.
        risk = "high" if history.get("top_share", 0) >= 0.5 else "medium"
        mit_by_reason = {
            "size_mismatch": ["state exact size/dimensions", "add a size guide"],
            "colour_mismatch": ["add a natural-light photo", "note handmade shade variation"],
            "damaged": ["cushion all sides", "use a rigid outer box", "add a fragile label"],
            "quality_issue": ["describe the material honestly", "show close-up photos"],
            "not_as_described": ["match the title to the photo", "list full details"],
            "late_or_lost": ["prefer regional fulfilment", "share a dispatch estimate"],
        }
        mitigations = mit_by_reason.get(top, ["describe the product accurately", "add clear photos"])
        prompt = None if (size and colour) else "Confirm the exact size and colour before publishing."
        return {
            "top_return_reason": reason,
            "risk_level": risk,
            "mitigations": mitigations,
            "needs_seller_confirmation": bool(prompt),
            "confirmation_prompt": prompt,
            "learned_from_returns": history["total"],
            "demo_fallback_used": True,
        }

    # No history yet — category reasoning.
    if category == "food_packaged":
        reason, risk = "spoilage, leakage, or unclear ingredients", "high"
        mitigations = ["add ingredients and best-before date", "use leak-proof packing", "prefer regional delivery"]
        prompt = "Confirm ingredients, batch date, and best-before date before publishing."
    elif category in ("handicrafts_decor", "candles_fragrance"):
        reason, risk = "breakage in transit", "medium"
        mitigations = ["wrap with cushioning", "show size in the listing", "add a fragile handling note"]
        prompt = "Confirm the exact size and packing material before publishing."
    else:
        reason = "size or colour mismatch"
        risk = "medium" if not (size and colour) else "low"
        mitigations = ["confirm exact colour shade", "add size or dimensions", "include a natural-light photo"]
        prompt = None if size and colour else "Confirm the exact colour shade and size before publishing."
    return {
        "top_return_reason": reason,
        "risk_level": risk,
        "mitigations": mitigations,
        "needs_seller_confirmation": bool(prompt),
        "confirmation_prompt": prompt,
        "learned_from_returns": (history or {}).get("total", 0),
        "demo_fallback_used": True,
    }


def run(product_name, category, attributes, history=None):
    """-> dict. history: aggregate return stats for this category (or None)."""
    hist_line = _history_line(history)
    grounding = (
        f"\n\nREAL RETURN DATA — weight this ABOVE general knowledge:\n{hist_line}\n"
        "If the data clearly points to a reason, make it the top_return_reason and set "
        "risk_level from how dominant it is."
        if hist_line
        else "\n\n(No return history for this category yet — reason from general "
        "knowledge of Indian online-shopping return patterns.)"
    )

    prompt = f"""You are Wapsi, the returns forecaster for a rural women's marketplace.
Forecast why THIS product is likely to be returned and how to reduce it.

Product: {product_name}
Category: {category}
Attributes: {json.dumps(attributes, ensure_ascii=False)}
{grounding}

If a colour or size assumption is uncertain, ask the seller to confirm it.

Return STRICT JSON only, exactly these keys:
{{
  "top_return_reason": "...",
  "risk_level": "low|medium|high",
  "mitigations": ["...", "...", "..."],
  "needs_seller_confirmation": <true or false>,
  "confirmation_prompt": "<a short question for the seller, or null>"
}}"""

    try:
        result = llm_json(prompt)
        result["learned_from_returns"] = (history or {}).get("total", 0)
        return result
    except Exception as exc:  # noqa: BLE001 - demo must remain runnable
        result = _fallback(product_name, category, attributes, history)
        result["fallback_reason"] = str(exc)
        return result


if __name__ == "__main__":
    demo_history = {"total": 12, "by_reason": {"damaged": 8, "not_as_described": 4},
                    "top_reason": "damaged", "top_share": 0.67}
    print(json.dumps(run("terracotta wall hanging", "handicrafts_decor", {}, demo_history),
                     ensure_ascii=False, indent=2))
