"""Niyam — the label-vs-listing safety check, and the packer-label fix.

_age_conflict is the deterministic backstop on the one field that can hurt a
child (a choking-hazard toy labelled for the wrong age); it does not rely on
the model to self-report its own contradiction. _packer_line / the
name-and-address substitution is what stopped the printed label reading
"<Manufacturer Name>, <Full Address>" when her real details were one query
away the whole time.
"""
from agents import niyam


# --------------------------------------------------------------- age conflict
def test_detects_the_real_case_teddy_labelled_older_than_listed():
    c = niyam._age_conflict(
        {"age_group": "0-1.5 Years"},
        "Product: Teddy | Age Grading: 3+ Years | Warning: choking hazard",
    )
    assert c is not None
    assert c["listing_says"] == "0-1.5 Years"
    assert c["label_says"] == "3+ Years"
    assert c["field"] == "age_group"


def test_no_conflict_when_label_and_listing_agree():
    assert niyam._age_conflict(
        {"age_group": "3-5 Years"}, "Age Grading: 3-5 Years"
    ) is None


def test_no_conflict_when_listing_has_no_value_yet():
    # Nothing to contradict — this is a blank she is already being asked for,
    # not a disagreement. Flagging it anyway trains her to ignore the warning
    # that actually matters.
    assert niyam._age_conflict({"age_group": None}, "Age Grading: 3+ Years") is None


def test_no_conflict_when_label_has_no_age_at_all():
    assert niyam._age_conflict({"age_group": "0-1.5 Years"}, "Net Qty: 1 Unit") is None


# ---------------------------------------------------------------- field matching
def test_match_field_normalises_the_models_own_wording():
    attrs = {"age_group": "0-1.5 Years"}
    assert niyam._match_field("age_grading", attrs) == "age_group"
    assert niyam._match_field("Age Grading", attrs) == "age_group"
    assert niyam._match_field("age_group", attrs) == "age_group"


def test_match_field_returns_none_for_something_not_in_the_listing():
    assert niyam._match_field("bis_isi_mark", {"age_group": "0-1.5 Years"}) is None


# ----------------------------------------------------------------- packer label
def test_packer_line_needs_both_name_and_address():
    assert niyam._packer_line({"name": "Lakshmi Ammal", "address": "Madurai"}) == \
        "Lakshmi Ammal, Madurai"
    assert niyam._packer_line({"name": "Lakshmi Ammal", "address": None}) is None
    assert niyam._packer_line(None) is None
    assert niyam._packer_line({}) is None


def test_name_address_field_pattern_matches_every_category_variant():
    for field in ["manufacturer_name_and_address", "fbo_name_and_address",
                  "packer_name_and_address"]:
        assert niyam._NAME_ADDRESS_FIELD.search(field)
    for field in ["bis_isi_mark", "net_quantity", "shelf_life"]:
        assert not niyam._NAME_ADDRESS_FIELD.search(field)


# --------------------------------------------------- deterministic label fallback
def test_fallback_label_uses_real_packer_details_not_a_blank():
    """Simulates a model outage (llm_json raising): the label must still carry
    her real name/address rather than leaving <manufacturer_name_and_address>.
    """
    orig = niyam.llm_json
    niyam.llm_json = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("simulated outage"))
    try:
        r = niyam.run(
            "toys_games", "Crochet Teddy Bear", 4,
            product_attributes={"age_group": "0-1.5 Years"},
            packer_label={"name": "Lakshmi Ammal", "address": "12 Bharathi Street, Madurai"},
        )
    finally:
        niyam.llm_json = orig
    assert "Lakshmi Ammal, 12 Bharathi Street, Madurai" in r["required_label_text"]
    assert "<manufacturer_name_and_address>" not in r["required_label_text"]
    # Everything else genuinely unknown still shows as a placeholder.
    assert "<bis_isi_mark>" in r["required_label_text"]


def test_fallback_label_without_packer_info_still_placeholders_cleanly():
    orig = niyam.llm_json
    niyam.llm_json = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("simulated outage"))
    try:
        r = niyam.run("toys_games", "Crochet Teddy Bear", 4, packer_label=None)
    finally:
        niyam.llm_json = orig
    assert "<manufacturer_name_and_address>" in r["required_label_text"]


# ------------------------------------------------------------- licence surfacing
def test_no_required_labels_means_compliant_immediately():
    r = niyam.run("handloom_textiles_with_no_rules_key_xyz", "thing", 1)
    assert r["compliance_ok"] is True
    assert r["required_label_text"] == ""


def test_required_licence_is_reported_even_though_it_cannot_be_auto_obtained():
    orig = niyam.llm_json
    niyam.llm_json = lambda *a, **k: {"required_label_text": "placeholder", "conflicts": []}
    try:
        r = niyam.run("toys_games", "Teddy", 1)
    finally:
        niyam.llm_json = orig
    assert "BIS_ISI_certification" in r["required_licenses"]
