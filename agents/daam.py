"""Daam — the pricer. Deterministic cost-plus so the number is defensible.

price = cost + shipping + extra_overhead + margin
discount_floor = break-even (cost + shipping + overhead) — never sell below this.
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


def run(cost_price_inr, category, desired_margin_pct=20, extra_overhead_inr=0):
    """Pure arithmetic — no LLM. -> dict."""
    bench = _load_benchmarks()
    cost = int(cost_price_inr or 0)
    overhead = int(extra_overhead_inr or 0)

    if category in bench.index:
        row = bench.loc[category]
        shipping = int(row["shipping_flat_inr"])
        low = int(row["typical_low_inr"])
        high = int(row["typical_high_inr"])
    else:
        # Unknown category: safe defaults, still runnable.
        shipping = 50
        low, high = 0, 10 ** 9

    base = cost + shipping + overhead
    margin_inr = round(base * desired_margin_pct / 100)
    selling_price = base + margin_inr
    discount_floor = base  # break-even

    return {
        "selling_price_inr": int(selling_price),
        "margin_pct": desired_margin_pct,
        "discount_floor_inr": int(discount_floor),
        "breakdown": {
            "cost": cost,
            "shipping": shipping,
            "overhead": overhead,
            "margin_inr": int(margin_inr),
        },
        "within_typical_range": bool(low <= selling_price <= high),
        "typical_range_inr": [low, high] if category in bench.index else None,
        "extra_overhead_absorbed_inr": overhead,
    }


if __name__ == "__main__":
    import json

    print(json.dumps(run(200, "handloom_textiles"), indent=2))
    print(json.dumps(run(200, "handloom_textiles", extra_overhead_inr=5), indent=2))
