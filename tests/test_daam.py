"""Daam — deterministic pricing. price = cost + shipping + overhead + margin;
discount_floor = break-even. No LLM in this agent at all (HANDOVER.md §9.1:
"money and law must be defensible"), so every case here is exact arithmetic,
not a fuzzy assertion.
"""
from agents import daam


def test_known_category_uses_its_shipping_and_range():
    r = daam.run(200, "handloom_textiles", desired_margin_pct=20)
    # handloom_textiles' shipping_flat_inr from data/price_benchmarks.csv.
    assert r["breakdown"]["shipping"] > 0
    assert r["breakdown"]["cost"] == 200
    base = r["breakdown"]["cost"] + r["breakdown"]["shipping"] + r["breakdown"]["overhead"]
    assert r["discount_floor_inr"] == base
    assert r["selling_price_inr"] == base + r["breakdown"]["margin_inr"]


def test_margin_percent_is_applied_to_the_base_not_the_cost_alone():
    r = daam.run(200, "handloom_textiles", desired_margin_pct=20)
    base = r["discount_floor_inr"]
    assert r["breakdown"]["margin_inr"] == round(base * 0.20)


def test_unknown_category_falls_back_to_safe_defaults_not_a_crash():
    r = daam.run(200, "not_a_real_category", desired_margin_pct=20)
    assert r["breakdown"]["shipping"] == 50
    assert r["typical_range_inr"] is None
    assert r["within_typical_range"] is True  # [0, 1e9] always contains it


def test_label_overhead_raises_price_and_floor_together():
    """The compliance loop's whole mechanic: a licence costs ₹5, Daam absorbs
    it into BOTH the price and the break-even floor so her margin survives —
    HANDOVER.md's "hero moment".
    """
    plain = daam.run(200, "handloom_textiles", desired_margin_pct=20)
    with_label = daam.run(200, "handloom_textiles", desired_margin_pct=20, extra_overhead_inr=5)
    assert with_label["discount_floor_inr"] == plain["discount_floor_inr"] + 5
    assert with_label["selling_price_inr"] > plain["selling_price_inr"]
    assert with_label["extra_overhead_absorbed_inr"] == 5


def test_zero_or_missing_cost_never_crashes():
    r = daam.run(None, "handloom_textiles")
    assert r["breakdown"]["cost"] == 0
    assert r["selling_price_inr"] >= 0


def test_price_is_always_an_int_never_a_float_a_seller_would_distrust():
    r = daam.run(233, "handloom_textiles", desired_margin_pct=17)
    assert isinstance(r["selling_price_inr"], int)
    assert isinstance(r["discount_floor_inr"], int)
