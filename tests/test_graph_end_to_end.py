"""The graph, run for real — with every model call forced to fail.

HANDOVER.md item 2 states the resilience promise as a design decision: "Every
LLM agent has a deterministic fallback → a run degrades, never hard-fails."
That is a claim about behaviour, and the only way to actually check a claim
about behaviour is to run the behaviour — asserting a docstring says the right
thing proves nothing. So every test here makes llm_json raise for every
agent, then drives a real orchestrator.run() through langgraph's real state
machine (checkpointed to an in-memory MemorySaver — see conftest.py for why
that patch has to happen before orchestrator is even imported) and checks
what a seller would actually see: the final status, the label text, the price,
and the activity log.

This also proves the three self-correcting loops actually iterate, not just
that they're wired into the graph — asserting the graph *compiles* would miss
an off-by-one in a gate function just as easily as asserting a docstring would.
"""
from io import BytesIO

import pytest
from PIL import Image

import graph_store
import orchestrator
from agents import likho as likho_agent
from agents import niyam as niyam_agent
from agents import suno as suno_agent
from agents import wapsi as wapsi_agent


def _model_unavailable(*args, **kwargs):
    raise RuntimeError("stubbed: no model in tests")


def _good_photo():
    """Bright enough and large enough to clear Suno's deterministic photo gate
    (agents/suno.py's _photo_quality — brightness >= 35, min dimension >= 180),
    without touching disk or the network.
    """
    return Image.new("RGB", (200, 200), (180, 170, 150))


def _tiny_dark_photo():
    """Fails both of _photo_quality's checks at once."""
    return Image.new("RGB", (40, 40), (5, 5, 5))


@pytest.fixture(autouse=True)
def no_real_model_or_database(monkeypatch):
    """Force every agent onto its documented fallback, and keep every
    graph_store call off the real Atlas cluster this repo's .env points at —
    a test suite that quietly queries production on every run is a liability,
    not a safety net.
    """
    for mod in (suno_agent, likho_agent, niyam_agent, wapsi_agent):
        monkeypatch.setattr(mod, "llm_json", _model_unavailable)
    monkeypatch.setattr(graph_store, "load_image", lambda ref: _good_photo())
    monkeypatch.setattr(
        graph_store, "check_and_store_fingerprint",
        lambda *a, **k: {"phash": None, "duplicate": False, "cross_seller": False},
    )
    monkeypatch.setattr(graph_store, "return_stats", lambda category: None)
    monkeypatch.setattr(graph_store, "get_packer_label", lambda seller_id: None)


def _run(voice_text, **kw):
    return orchestrator.run(voice_text, image_ref="fake-ref", **kw)


# ------------------------------------------------------------------- photo gate
def test_bad_photo_is_rejected_before_anything_else_runs(monkeypatch):
    monkeypatch.setattr(graph_store, "load_image", lambda ref: _tiny_dark_photo())
    result = _run("I make wooden toys, four pieces, cost 200 rupees each")
    assert result["status"] == "needs_retake"
    # Nothing downstream should have run — no point pricing a photo buyers
    # can't see.
    agents_that_ran = {name for name, _ in result.get("log", [])}
    assert "Daam" not in agents_that_ran
    assert "Niyam" not in agents_that_ran


# ----------------------------------------------------------------- clarify gate
def test_missing_price_pauses_for_clarification_not_a_guess():
    result = _run("I make wooden toys for children, four pieces")
    assert result["status"] == "needs_clarification"
    fields = {q["field"] for q in result["clarification"]["questions"]}
    assert "cost_price_inr" in fields


def test_unresolvable_category_also_pauses_for_clarification():
    result = _run("I make this thing at home, 30 pieces, 150 rupees each")
    assert result["status"] == "needs_clarification"
    fields = {q["field"] for q in result["clarification"]["questions"]}
    assert "category" in fields


# ------------------------------------------------------------- compliance loop
def test_compliance_loop_fires_and_the_label_carries_her_real_facts():
    """toys_games requires BIS/age-grading/etc labels, so Niyam must demand
    them, Likho must append them, Daam must re-price to absorb the label cost,
    and Niyam must recheck and accept — all via each agent's fallback, since
    the model is stubbed to fail throughout.
    """
    result = _run("I make wooden toys for children, four pieces, cost 200 rupees each")

    assert result["status"] == "ready_for_approval"
    assert result["compliance"]["compliance_ok"] is True

    agent_names = [name for name, _ in result["log"]]
    # The loop actually iterated — not just that compliance ended up true by
    # some other path.
    assert "Niyam" in agent_names
    assert "Niyam (recheck #1)" in agent_names
    assert "Likho (re-run #1)" in agent_names
    assert "Daam (re-price #1)" in agent_names

    # Daam's re-price pass absorbed the label overhead into both the price
    # and the break-even floor (agents/daam.py's whole reason to exist).
    assert result["price"]["breakdown"]["overhead"] == result["compliance"]["label_overhead_inr"]
    assert result["price"]["breakdown"]["overhead"] > 0

    # The label text actually reached the published listing description —
    # Likho's belt-and-braces guarantee, not just Niyam's draft sitting unused.
    assert result["compliance"]["required_label_text"] in result["listing"]["description"]


def test_compliance_loop_generalises_to_a_different_category():
    # Every one of the 13 real categories in data/compliance_rules.json
    # requires at least one label (verified in test_niyam.py) — there is no
    # real seller input that skips this loop, which is itself worth knowing.
    # This proves the mechanism isn't toys_games-specific.
    result = _run("I make handwoven cotton scarves, twenty pieces, cost 150 rupees each")
    agent_names = [name for name, _ in result["log"]]
    assert "Niyam (recheck #1)" in agent_names
    assert result["compliance"]["compliance_ok"] is True


def test_a_required_label_survives_a_later_returns_loop_rewrite():
    """The regression this suite actually caught: once the returns loop asks
    Likho for a size guide AFTER the compliance loop has already appended a
    label, Likho rewrites the description from scratch — and used to drop the
    label entirely, even though compliance_ok stayed True and Daam had
    already priced in the label's overhead. A toy triggers both loops in one
    run (it needs a label AND Wapsi's fallback asks her to confirm colour/
    size), so it exercises the real interaction, not two isolated loops.
    """
    result = _run("I make wooden toys for children, four pieces, cost 200 rupees each")
    agent_names = [name for name, _ in result["log"]]
    assert "Niyam (recheck #1)" in agent_names  # compliance loop ran
    assert "Likho (add size guide)" in agent_names  # returns loop ran too
    assert result["compliance"]["required_label_text"] in result["listing"]["description"]


# --------------------------------------------------------------- the full run
def test_a_clean_run_reaches_ready_for_approval_with_a_real_price():
    result = _run("I make handwoven cotton scarves, twenty pieces, cost 150 rupees each")
    assert result["status"] == "ready_for_approval"
    assert result["price"]["selling_price_inr"] > 0
    assert result["price"]["selling_price_inr"] >= result["price"]["discount_floor_inr"]
    assert result["listing"]["title"]
    assert result["listing"]["description"]


def test_seller_only_field_is_never_fabricated_even_through_the_whole_graph():
    """The exact regression that motivated this suite: a fabricated age_group
    on a toy drove a wrong safety label. End to end, with the model stubbed
    (so any fabrication would have to come from the deterministic fallback
    path, not a model guess), age_group must stay unset and be asked for.
    """
    result = _run("I make wooden toys for children, four pieces, cost 200 rupees each")
    assert result["product_attributes"].get("age_group") is None
    assert "Age Group" in result["missing_attributes"]
