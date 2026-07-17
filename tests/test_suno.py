"""Suno — the two highest-risk regressions this project actually had.

1. _pick_category used to default to "handicrafts_decor" when nothing matched,
   which silently routed food to a category with no FSSAI requirement. It must
   now return None so the graph asks instead of guessing (orchestrator.py's
   _blocking_gaps — see test_orchestrator_pure.py).

2. Fields marked infer:"seller" in data/listing_attributes.json (age_group,
   purity, certification, shelf_life, ...) must never be filled by the model,
   even if the model returns a value for them anyway — a fabricated
   "BIS Hallmark" or a fabricated toy age_group is a false claim with her name
   on it.
"""
from agents import suno


# --------------------------------------------------------------- category gate
def test_unmatched_text_returns_none_not_a_silent_default():
    assert suno._pick_category("this is some completely unrelated sentence xyz") is None


def test_alias_match_still_works():
    assert suno._pick_category("I make wooden toys for children") == "toys_games"
    assert suno._pick_category("I make mango pickle in jars") == "food_packaged"


def test_resolve_category_rejects_a_hallucinated_key():
    # The model can return anything; an unrecognised key must not reach Niyam,
    # which would find no rules for it and silently report zero requirements.
    assert suno.resolve_category("food", "random unrelated words") is None


def test_resolve_category_trusts_a_real_key_from_the_model():
    assert suno.resolve_category("food_packaged", "anything") == "food_packaged"


def test_resolve_category_falls_back_to_alias_hint_when_model_gives_nothing():
    assert suno.resolve_category(None, "I make wooden toys") == "toys_games"


def test_resolve_category_asks_on_low_confidence_uncorroborated_by_her_words():
    # The exact case that motivated this: "I make this thing at home" is not
    # a toy in her own words, so a low-confidence "toys_games" must not survive.
    assert suno.resolve_category("toys_games", "I make this thing at home", "low") is None


def test_resolve_category_keeps_low_confidence_when_her_words_corroborate_it():
    got = suno.resolve_category("toys_games", "I make wooden toys for children", "low")
    assert got == "toys_games"


def test_resolve_category_trusts_high_confidence_even_if_unusual():
    got = suno.resolve_category("toys_games", "I make this thing at home", "high")
    assert got == "toys_games"


# ------------------------------------------------------- seller-only fabrication
def test_seller_only_field_is_never_filled_from_a_model_guess():
    # age_group is infer:"seller" for toys_games — even if the model returns
    # one, it must be dropped so she is asked instead of quietly overruled.
    raw = {"color": "Beige", "material": "Cotton", "product_type": "Soft toy",
           "age_group": "0-1.5 Years"}
    attrs, missing = suno._finalize_attributes("toys_games", raw, "Cotton")
    assert attrs.get("age_group") is None
    assert "Age Group" in missing


def test_seller_only_field_absent_from_the_prompt_the_model_sees():
    # Withheld entirely, not just filtered after the fact — showing it invites
    # a guess in the first place.
    spec = suno._compact_attr_spec()
    toy_line = next(l for l in spec.splitlines() if l.startswith("- toys_games"))
    assert "age_group" not in toy_line


def test_seller_only_field_is_nulled_even_if_the_caller_tries_to_sneak_one_in():
    # _finalize_attributes is Suno's OWN intake call — it has no way to tell a
    # legitimate seller answer from a value it made up itself, so it nulls
    # every infer:"seller" field unconditionally, no matter what's in `raw`.
    # This is defence in depth on top of the prompt withholding the field:
    # even a caller passing a pre-filled value here gets it stripped. Her
    # real answer reaches the listing through a different, later path —
    # resolve_attribute_value() at approval time (backend/routers/listings.py
    # /attribute), not by re-running Suno's intake.
    attrs, missing = suno._finalize_attributes(
        "toys_games", {"age_group": "1.5-3 Years", "color": "Beige"}, "Cotton"
    )
    assert attrs.get("age_group") is None
    assert "Age Group" in missing


def test_fixed_field_is_never_left_to_the_model_or_to_her():
    attrs, _ = suno._finalize_attributes("toys_games", {}, "Cotton")
    assert attrs.get("country_of_origin") == "India"


def test_no_category_means_no_fabricated_attribute_set():
    # A half-filled attribute grid built on an unknown category would be worse
    # than none — attributes_for(None) must come back empty, not guessed.
    attrs, missing = suno.attributes_for(None, {}, None)
    assert attrs == {}
    assert missing == []


# ------------------------------------------------------------------ money parsing
def test_extract_rupees_reads_the_symbol_without_the_word_cost():
    assert suno._extract_rupees("teddy bear ₹200 small size") == 200


def test_extract_rupees_reads_the_word_rupees():
    assert suno._extract_rupees("it costs 150 rupees each") == 150


def test_extract_rupees_returns_none_when_nothing_is_stated():
    assert suno._extract_rupees("I make handmade jute bags, forty pieces") is None
