"""Niyam — the rulekeeper. The adversary in the loop.

Reads the real rules base, decides what labels/licenses a product needs, drafts
the exact label text to append, and stays UNSATISFIED (compliance_ok=false) until
Likho has appended that text and Daam has absorbed the label overhead.
"""
import os
import json

from llm import llm_json

_RULES_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "compliance_rules.json")

_rules = None


def _load_rules():
    global _rules
    if _rules is None:
        with open(_RULES_PATH, encoding="utf-8") as f:
            _rules = json.load(f)
    return _rules


def _gst_note(rules):
    thr = rules["gst"]["goods_threshold_inr"]
    return (
        f"Seller turnover assumed below the ₹{thr:,} GST threshold, so registration "
        "is likely not required. Confirm actual annual turnover."
    )


def run(category, product_name, quantity, label_applied=False, label_text=None):
    """-> dict. label_applied flips compliance_ok true once labels are on the listing.

    On a recheck, pass the already-drafted label_text so Niyam echoes the exact
    text that was appended instead of regenerating different wording (which would
    be incoherent, and wastes an LLM call).
    """
    rules = _load_rules()
    cat = rules["categories"].get(category, {})
    required_labels = cat.get("required_labels", [])
    required_licenses = cat.get("required_licenses", [])
    label_overhead = 5 if required_labels else 0

    # Draft the actual on-pack label text via the LLM (product-specific), grounded
    # in the required_labels the rules base demands. On recheck, reuse the exact
    # text already appended — don't regenerate (keeps it coherent + saves a call).
    required_label_text = ""
    if required_labels and label_applied and label_text:
        required_label_text = label_text
    elif required_labels:
        prompt = f"""You are Niyam, a compliance officer. Draft the exact printed label text
for this product so it satisfies Indian Legal Metrology / category rules.

Product: {product_name}
Category: {category}
Required label fields (must all appear): {', '.join(required_labels)}

Rules for fields you don't know the value of: use a clear placeholder in angle
brackets, e.g. <seller name>, <address>, <mfg date>. Keep it to ONE compact line.

Return STRICT JSON only:
{{"required_label_text": "<one line of label text>"}}"""
        try:
            required_label_text = llm_json(prompt).get("required_label_text", "")
        except Exception:
            # Deterministic fallback so the loop never stalls without the LLM.
            required_label_text = "; ".join(f"<{f}>" for f in required_labels)

    actions = []
    if required_labels:
        actions.append(
            {"agent": "likho", "instruction": "append required_label_text to the description"}
        )
        actions.append(
            {"agent": "daam", "instruction": "absorb label_overhead_inr and re-price"}
        )

    # Compliance is satisfied once the labels are on the listing. Missing licenses
    # (e.g. FSSAI) are surfaced as warnings — the system can't auto-obtain them.
    compliance_ok = (not required_labels) or label_applied

    return {
        "compliance_ok": bool(compliance_ok),
        "required_labels": required_labels,
        "required_licenses": required_licenses,
        "gst_note": _gst_note(rules),
        "required_label_text": required_label_text,
        "label_overhead_inr": label_overhead,
        "category_notes": cat.get("notes", ""),
        "optional_marks": cat.get("optional_marks", []),
        "actions": actions,
    }


if __name__ == "__main__":
    print(json.dumps(run("handloom_textiles", "handwoven jute bags", 40), ensure_ascii=False, indent=2))
    print("--- after label applied ---")
    print(json.dumps(run("handloom_textiles", "handwoven jute bags", 40, label_applied=True), ensure_ascii=False, indent=2))
