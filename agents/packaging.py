"""Packaging — deterministic packing plan from the category's fragile/perishable flags.

No LLM. Reads the same benchmarks table Daam uses, so fragile/perishable stay in
one place. Returns a plan the seller can act on and that lowers return risk.
"""
import os

import pandas as pd

_CSV_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "price_benchmarks.csv")

_benchmarks = None


def _load_benchmarks():
    global _benchmarks
    if _benchmarks is None:
        _benchmarks = pd.read_csv(_CSV_PATH).set_index("category")
    return _benchmarks


def _flags(category):
    bench = _load_benchmarks()
    if category in bench.index:
        row = bench.loc[category]
        return bool(row.get("fragile", False)), bool(row.get("perishable", False))
    return False, False


def run(category, material=None):
    """-> dict with primary_pack, outer_pack, handling_note, materials, label."""
    fragile, perishable = _flags(category)

    if perishable:
        primary = "food-grade sealed pouch / airtight jar"
        outer = "rigid corrugated box with cushioning"
        handling = "Perishable — prefer regional/expedited delivery; keep away from heat."
        materials = ["food-grade pouch", "tamper seal", "corrugated box", "cushioning"]
        label = "PERISHABLE · THIS SIDE UP"
    elif fragile:
        primary = "bubble-wrap the item (2 layers)"
        outer = "double-walled corrugated box with corner protection"
        handling = "Fragile — cushion all sides; no loose space inside the box."
        materials = ["bubble wrap", "double-wall box", "corner guards", "void fill"]
        label = "FRAGILE · HANDLE WITH CARE"
    elif category in ("handloom_textiles", "home_furnishing", "apparel"):
        primary = "fold and seal in a poly bag to keep it clean"
        outer = "tamper-proof courier bag"
        handling = "Keep dry; a product tag helps buyers trust the item."
        materials = ["poly bag", "courier mailer", "product tag"]
        label = "KEEP DRY"
    else:
        primary = "wrap in kraft paper"
        outer = "tamper-proof courier bag or small box"
        handling = "Standard packing; ensure the item cannot move inside."
        materials = ["kraft paper", "courier mailer"]
        label = None

    return {
        "primary_pack": primary,
        "outer_pack": outer,
        "handling_note": handling,
        "materials": materials,
        "shipping_label": label,
        "fragile": fragile,
        "perishable": perishable,
    }


if __name__ == "__main__":
    import json

    for c in ["handloom_textiles", "food", "handicrafts_decor", "jewellery_precious"]:
        print(c, "->", json.dumps(run(c), ensure_ascii=False))
