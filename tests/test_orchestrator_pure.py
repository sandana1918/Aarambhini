"""orchestrator._blocking_gaps — pure function of state, no graph run needed.

This is the "speak once" boundary: only a missing price or an unresolved
category ever interrupts her, because a wrong category is wrong law (see
test_suno.py's category-gate tests for why), and everything else gets a safe
default or lands on the post-publish checklist instead of a question.
"""
from orchestrator import _blocking_gaps


def test_no_gaps_when_price_and_category_are_both_known():
    state = {"suno": {"cost_price_inr": 200, "category": "food_packaged"}}
    assert _blocking_gaps(state) == []


def test_missing_price_is_a_blocking_gap():
    state = {"suno": {"cost_price_inr": None, "category": "food_packaged"}}
    gaps = _blocking_gaps(state)
    assert [g["field"] for g in gaps] == ["cost_price_inr"]


def test_zero_price_is_treated_as_missing_not_a_real_free_listing():
    state = {"suno": {"cost_price_inr": 0, "category": "food_packaged"}}
    gaps = _blocking_gaps(state)
    assert any(g["field"] == "cost_price_inr" for g in gaps)


def test_unresolved_category_is_a_blocking_gap_with_all_options_offered():
    state = {"suno": {"cost_price_inr": 200, "category": None}}
    gaps = _blocking_gaps(state)
    assert [g["field"] for g in gaps] == ["category"]
    assert gaps[0]["type"] == "choice"
    assert len(gaps[0]["options"]) == 13  # every category in compliance_rules.json


def test_both_missing_raises_both_gaps_in_one_pause():
    # One interrupt, two questions — not two separate pauses.
    state = {"suno": {"cost_price_inr": None, "category": None}}
    gaps = _blocking_gaps(state)
    assert {g["field"] for g in gaps} == {"cost_price_inr", "category"}
