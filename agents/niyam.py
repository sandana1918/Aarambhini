"""Niyam — the rulekeeper. The adversary in the loop.

Reads the real rules base, decides what labels/licenses a product needs, drafts
the exact label text to append, and stays UNSATISFIED (compliance_ok=false) until
Likho has appended that text and Daam has absorbed the label overhead.
"""
import os
import re
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


def _known_values(product_attributes):
    """The listing's own attribute values, as label-ready lines.

    Niyam used to draft the label with none of this, so it invented values that
    contradicted the listing — a teddy attributed "0-1.5 Years" was labelled
    "Age Grading: 3+ Years". The label and the listing describe one product;
    they have to come from one set of facts.
    """
    if not product_attributes:
        return ""
    lines = [
        f"- {k}: {v}" for k, v in product_attributes.items()
        if v not in (None, "", [])
    ]
    return "\n".join(lines)


# Every category spells the packer field differently — manufacturer_name_and_
# address, fbo_name_and_address, packer_name_and_address — but they all mean
# the same thing: who made this and where. Matched by shape, not an exhaustive
# list, so a category added later still gets her real details instead of a
# blank the moment it asks for a name-and-address field.
_NAME_ADDRESS_FIELD = re.compile(r"name.*address|address.*name", re.I)


def _packer_line(packer_label):
    """Her name + address, ready to drop into a label line, or None."""
    if not packer_label or not packer_label.get("name") or not packer_label.get("address"):
        return None
    return f"{packer_label['name']}, {packer_label['address']}"


def _match_field(reported, product_attributes):
    """Map a model-named field onto a real attribute key, or None.

    It answers with whatever it likes — "age_grading" where the listing calls it
    "age_group" — and a mismatch would quote the listing as saying "None".
    """
    attrs = product_attributes or {}
    key = (reported or "").strip().lower().replace(" ", "_")
    if key in attrs:
        return key
    # Same words, different arrangement: age_grading -> age_group.
    tokens = {t for t in key.split("_") if t}
    for k in attrs:
        if tokens & {t for t in k.split("_") if t}:
            return k
    return None


def _age_conflict(product_attributes, label_text):
    """Does the drafted label grade the age differently from the listing?

    This is the one field where a mismatch can hurt a child: a small-parts toy
    sold as suitable for a 0-1.5-year-old while the box says 3+. We do not
    silently pick a side — the listing keeps her value and she is told, because
    which one is right is a judgement about her product, not a formatting bug.
    """
    listed = (product_attributes or {}).get("age_group")
    if not listed or not label_text:
        return None
    # The label carries the listing's own wording -> nothing to reconcile.
    if listed.lower() in label_text.lower():
        return None
    found = re.search(r"(\d+\s*\+?\s*(?:-\s*[\d.]+)?\s*(?:years|yrs))", label_text, re.I)
    if not found:
        return None
    return {
        "field": "age_group",
        "listing_says": listed,
        "label_says": found.group(1).strip(),
        "why": (
            "The listing and the printed label disagree about who this toy is for. "
            "Age grading is a safety statement — please confirm which is right "
            "before printing."
        ),
    }


def run(category, product_name, quantity, label_applied=False, label_text=None,
        product_attributes=None, packer_label=None):
    """-> dict. label_applied flips compliance_ok true once labels are on the listing.

    On a recheck, pass the already-drafted label_text so Niyam echoes the exact
    text that was appended instead of regenerating different wording (which would
    be incoherent, and wastes an LLM call).

    `product_attributes` are the listing's own facts. Without them Niyam drafts
    the label blind and makes up values that contradict the listing.

    `packer_label` is {name, address} from the seller's own profile. Every
    category requires a name-and-address field on the label (manufacturer,
    packer, FBO — the wording varies, the requirement doesn't), and without this
    Niyam had nothing to put there but "<Manufacturer Name>, <Full Address>" — a
    blank on the one document Legal Metrology actually inspects. The data has
    sat in her profile since registration.
    """
    rules = _load_rules()
    cat = rules["categories"].get(category, {})
    required_labels = cat.get("required_labels", [])
    required_licenses = cat.get("required_licenses", [])
    label_overhead = 5 if required_labels else 0
    packer_line = _packer_line(packer_label)
    name_address_field = next(
        (f for f in required_labels if _NAME_ADDRESS_FIELD.search(f)), None
    )

    # Draft the actual on-pack label text via the LLM (product-specific), grounded
    # in the required_labels the rules base demands. On recheck, reuse the exact
    # text already appended — don't regenerate (keeps it coherent + saves a call).
    required_label_text = ""
    conflicts = []
    if required_labels and label_applied and label_text:
        required_label_text = label_text
    elif required_labels:
        known = _known_values(product_attributes)
        packer_note = (
            f'\n\nThe seller\'s real name and address, for the {name_address_field} '
            f'field — use exactly this, not a placeholder: "{packer_line}"'
            if name_address_field and packer_line else ""
        )
        prompt = f"""You are Niyam, a compliance officer. Draft the exact printed label text
for this product so it satisfies Indian Legal Metrology / category rules.

Product: {product_name}
Category: {category}
Required label fields (must all appear): {', '.join(required_labels)}

These are the listing's own confirmed values. Where a label field corresponds to
one of these, use THIS EXACT VALUE — the label and the listing describe the same
product, and a label that contradicts the listing is worse than no label:
{known or "(none confirmed yet)"}{packer_note}

If the law requires a value that differs from the listing above (for example a
stricter age grading for a choking hazard), do NOT quietly print the different
value: keep the listing's value and report it in "conflicts" so the seller is
asked. Only use an angle-bracket placeholder for a field whose value is genuinely
unknown, e.g. <mfg date>. Keep the label to ONE compact line.

Return STRICT JSON only:
{{"required_label_text": "<one line of label text>",
  "conflicts": [{{"field": "<attribute key>", "label_says": "<value the law needs>",
                 "why": "<one short sentence for the seller>"}}]}}"""
        try:
            raw = llm_json(prompt)
            required_label_text = raw.get("required_label_text", "")
            # A model can still ignore the instruction and print the placeholder
            # anyway — this is not optional the way a style note is, so replace
            # it deterministically rather than hope the wording landed.
            if name_address_field and packer_line:
                required_label_text = re.sub(
                    r"<[^<>]*(?:name|address)[^<>]*>", packer_line,
                    required_label_text, count=1, flags=re.I,
                )
            for c in raw.get("conflicts") or []:
                if not isinstance(c, dict) or not c.get("field"):
                    continue
                # The model names the field freely ("age_grading" for age_group),
                # so match it to a real attribute key before quoting the listing.
                field = _match_field(c["field"], product_attributes)
                listed = (product_attributes or {}).get(field) if field else None
                if not listed:
                    # She hasn't stated a value, so there is nothing to
                    # contradict — it's a blank she is already being asked for,
                    # and "your listing says None" is noise that trains her to
                    # ignore the one warning that matters.
                    continue
                conflicts.append({
                    "field": field,
                    "listing_says": listed,
                    "label_says": c.get("label_says"),
                    "why": c.get("why") or "The law may require a different value here.",
                })
        except Exception:
            # Deterministic fallback so the loop never stalls without the LLM.
            # Still use her real details where we have them — a model outage is
            # not a reason to print a blank for a fact we already know.
            required_label_text = "; ".join(
                packer_line if f == name_address_field and packer_line else f"<{f}>"
                for f in required_labels
            )

    actions = []
    if required_labels:
        actions.append(
            {"agent": "likho", "instruction": "append required_label_text to the description"}
        )
        actions.append(
            {"agent": "daam", "instruction": "absorb label_overhead_inr and re-price"}
        )

    # Trusting the model to declare its own contradiction isn't enough on the one
    # field that can hurt a child, so re-read the drafted label and check it
    # against the listing regardless of what it reported.
    detected = _age_conflict(product_attributes, required_label_text)
    if detected and not any(c["field"] == "age_group" for c in conflicts):
        conflicts.append(detected)

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
        "conflicts": conflicts,
        "actions": actions,
    }


if __name__ == "__main__":
    print(json.dumps(run("handloom_textiles", "handwoven jute bags", 40), ensure_ascii=False, indent=2))
    print("--- after label applied ---")
    print(json.dumps(run("handloom_textiles", "handwoven jute bags", 40, label_applied=True), ensure_ascii=False, indent=2))
