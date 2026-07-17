"""Mukhiya — the orchestrator, as a LangGraph state machine.

The crew is a graph, not a line. It runs THREE self-correcting loops, each a real
cycle in the graph:

  1. Quality loop   — Mukhiya reviews Likho's listing; if thin, sends it back
                      to be rewritten.            (review ⟲ likho)
  2. Compliance loop— Niyam rejects; Likho appends the required label AND Daam
                      re-prices to absorb it.     (niyam ⟲ likho → daam)
  3. Return loop    — Wapsi flags high return risk; Likho adds a size/colour
                      guide; the listing is held for the seller's confirm.
                                                  (return_review ⟲ likho)

Two reject gates (photo quality / image authenticity, both in Suno) stop bad
input early; one interrupt (Finalize) holds everything for the seller.
"""
import operator
import uuid
from typing import Annotated, TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt, Command

import graph_store
from agents import suno as suno_agent
from agents import likho as likho_agent
from agents import daam as daam_agent
from agents import niyam as niyam_agent
from agents import wapsi as wapsi_agent
from agents import packaging as packaging_agent

MAX_COMPLIANCE_TRIES = 3
MAX_QUALITY_TRIES = 2


class AarambhiniState(TypedDict, total=False):
    voice_text: str
    image_ref: str  # GridFS id — NOT a live PIL.Image (which can't be checkpointed)
    seller_id: str
    desired_margin_pct: int
    # agent outputs
    suno: dict
    product_attributes: dict
    missing_attributes: list
    authenticity: dict
    listing: dict
    price: dict
    compliance: dict
    returns: dict
    packaging_plan: dict
    review: dict
    # loop counters / flags
    tries: int
    quality_tries: int
    return_needs_mitigation: bool
    return_mitigated: bool
    size_guide_text: str
    # outputs
    status: str
    reason: str
    approvals: list
    action_checklist: list
    seller_notes: str
    log: Annotated[list, operator.add]


# ---------------------------------------------------------------- helpers
def _in_compliance_loop(state) -> bool:
    c = state.get("compliance")
    return bool(c) and not c.get("compliance_ok", False)


def _in_quality_loop(state) -> bool:
    r = state.get("review")
    return bool(r) and not r.get("quality_ok", True)


def _in_return_loop(state) -> bool:
    return bool(state.get("return_needs_mitigation")) and not state.get("return_mitigated")


def _size_guide_text(state) -> str:
    cat = state.get("suno", {}).get("category", "")
    if cat in ("handloom_textiles", "apparel_readymade", "home_furnishing"):
        return ("Size & colour note: exact measurements are listed above; being handmade, "
                "colours may vary slightly on different screens.")
    if cat in ("jewellery_precious", "imitation_jewellery"):
        return ("Size note: please check the listed dimensions and message us to confirm "
                "fit before ordering.")
    return ("Please review the listed size and colour details, and message us with any "
            "questions before ordering.")


# ------------------------------------------------------------------ nodes
def _authenticity(image, suno, state) -> dict:
    """Combine pHash duplicate detection + Gemini's visual authenticity read.

    Verdict: 'blocked' only for a high-confidence steal (same photo, different
    seller); 'review' for softer signals (watermark / stock / AI look, or a
    duplicate we can't pin to another seller); else 'ok'. We never hard-reject a
    real seller on a soft signal.
    """
    if image is None:
        return {"verdict": "ok", "flags": []}

    fp = {"phash": None, "duplicate": False, "cross_seller": False}
    try:
        fp = graph_store.check_and_store_fingerprint(
            image, state.get("seller_id"), state.get("image_ref")
        )
    except Exception:  # noqa: BLE001 - fingerprinting must never crash intake
        pass

    gem = suno.get("photo_authenticity") or "original"
    flags = []
    if fp["cross_seller"]:
        flags.append("This exact photo is already used by another seller.")
    elif fp["duplicate"]:
        flags.append("This photo matches one already uploaded to Aarambhini.")
    if gem == "watermarked":
        flags.append("The photo appears to carry a watermark or logo.")
    elif gem == "stock_or_catalogue":
        flags.append("The photo looks like a stock or catalogue image, not an original phone photo.")
    elif gem == "likely_ai":
        flags.append("The photo may be AI-generated.")

    verdict = "blocked" if fp["cross_seller"] else ("review" if flags else "ok")
    return {
        "verdict": verdict,
        "flags": flags,
        "phash": fp["phash"],
        "photo_authenticity": gem,
        "note": suno.get("authenticity_note"),
    }


def suno_node(state) -> dict:
    image = graph_store.load_image(state.get("image_ref"))
    s = suno_agent.run(state["voice_text"], image)
    # Attributes are produced by the same call; lift them to top-level state,
    # keep state["suno"] to the intake facts downstream agents read.
    pa = s.pop("product_attributes", {}) or {}
    ma = s.pop("missing_attributes", []) or []
    auth = _authenticity(image, s, state)
    logged = {**s, "product_attributes": pa, "missing_attributes": ma, "authenticity": auth}
    return {
        "suno": s,
        "product_attributes": pa,
        "missing_attributes": ma,
        "authenticity": auth,
        "tries": 0,
        "quality_tries": 0,
        "log": [("Suno", logged)],
    }


def reject_node(state) -> dict:
    s = state["suno"]
    if state.get("authenticity", {}).get("verdict") == "blocked":
        reason = (
            "This photo appears to already be used by another seller. Please upload "
            "your own original photo of the product you made."
        )
    else:
        reason = s.get("photo_issue") or "photo unclear"
    return {"status": "needs_retake", "reason": reason}


def _blocking_gaps(state) -> list:
    """Only information without which we can't build a valid listing at all.

    Everything else (size, packer, mfg date, optional licences) has a safe default
    or stays on the post-listing checklist — we do NOT interrogate the seller.
    """
    suno = state.get("suno", {}) or {}
    gaps = []
    if not suno.get("cost_price_inr"):  # None or 0 → pricing would be nonsense
        gaps.append({
            "field": "cost_price_inr",
            "type": "number",
            "prompt": "We couldn't hear a price. How much does one piece cost you to "
                      "make, or what price do you want to sell at? Enter the amount in ₹.",
        })
    # An unknown category is a blocking gap because it decides which law applies.
    # Guessing here is how food ends up filed as a handicraft and never gets
    # asked for an FSSAI licence — the seller would publish believing she is
    # compliant. This is the one extra question worth breaking "speak once" for.
    if not suno.get("category"):
        gaps.append({
            "field": "category",
            "type": "choice",
            "options": suno_agent.known_categories(),
            "prompt": "Which of these best describes what you make? The labels and "
                      "licences the law requires depend on this, so I'd rather ask "
                      "than guess.",
        })
    return gaps


def clarify_node(state) -> dict:
    """Ask the seller ONLY for blocking gaps, then resume the same run.

    If nothing is blocking (the common case), this passes straight through with no
    interrupt. Otherwise it pauses (checkpointed) until /clarify resumes it with
    the seller's answers.
    """
    gaps = _blocking_gaps(state)
    if not gaps:
        return {}

    answers = interrupt({"kind": "clarification", "questions": gaps}) or {}

    out = {}
    suno = dict(state.get("suno") or {})
    if answers.get("cost_price_inr"):
        try:
            suno["cost_price_inr"] = int(answers["cost_price_inr"])
            out["suno"] = suno
        except (TypeError, ValueError):
            pass

    # She told us the category, so rebuild the attribute set — it is
    # category-specific and Suno had nothing to build it from.
    chosen = answers.get("category")
    if chosen and chosen in {c["key"] for c in suno_agent.known_categories()}:
        suno["category"] = chosen
        out["suno"] = suno
        attrs, missing = suno_agent.attributes_for(
            chosen, state.get("product_attributes"), suno.get("material")
        )
        out["product_attributes"] = attrs
        out["missing_attributes"] = missing

    out["log"] = [("Seller clarification", {"answers": answers})]
    return out


def likho_node(state) -> dict:
    append_disclaimer = None
    revision_note = None
    size_guide = None

    if _in_return_loop(state):
        size_guide = state.get("size_guide_text")
        label = "Likho (add size guide)"
    elif _in_compliance_loop(state):
        append_disclaimer = state["compliance"].get("required_label_text")
        label = f"Likho (re-run #{state.get('tries', 0) + 1})"
    elif _in_quality_loop(state):
        revision_note = state["review"].get("revision_note")
        label = f"Likho (revise #{state.get('quality_tries', 0)})"
    else:
        label = "Likho"

    lk = likho_agent.run(
        state["suno"], append_disclaimer=append_disclaimer,
        revision_note=revision_note, size_guide=size_guide,
    )
    out = {"listing": lk, "log": [(label, lk)]}
    if size_guide is not None:
        out["return_mitigated"] = True
    return out


def review_node(state) -> dict:
    """Mukhiya's quality rubric over Likho's listing (deterministic)."""
    listing = state["listing"]
    title = listing.get("title", "") or ""
    desc = listing.get("description", "") or ""
    kws = listing.get("keywords", []) or []
    story = (listing.get("maker_story", "") or "").strip()

    gaps = []
    if not (8 <= len(title) <= 120):
        gaps.append("title should be a clear 8–120 characters")
    if len(desc) < 60:
        gaps.append("description is too thin — write 2–4 full sentences")
    if len(kws) < 4:
        gaps.append("add more search keywords (at least 4)")
    if not story:
        gaps.append("add a one-line maker story")

    qtries = state.get("quality_tries", 0) + 1
    quality_ok = (not gaps) or (qtries >= MAX_QUALITY_TRIES)
    review = {
        "quality_ok": quality_ok,
        "gaps": gaps,
        "revision_note": "; ".join(gaps) if gaps else "",
        "tries": qtries,
    }
    label = "Mukhiya (review)" if qtries == 1 else f"Mukhiya (re-review #{qtries})"
    return {"review": review, "quality_tries": qtries, "log": [(label, review)]}


def daam_node(state) -> dict:
    overhead = 0
    label = "Daam"
    if _in_compliance_loop(state):
        overhead = state["compliance"].get("label_overhead_inr", 0)
        label = f"Daam (re-price #{state.get('tries', 0) + 1})"
    s = state["suno"]
    dm = daam_agent.run(
        s.get("cost_price_inr"), s.get("category"),
        desired_margin_pct=state.get("desired_margin_pct", 20),
        extra_overhead_inr=overhead,
    )
    return {"price": dm, "log": [(label, dm)]}


def niyam_node(state) -> dict:
    s = state["suno"]
    # The listing's own facts. Without these Niyam drafts the label blind and
    # invents values that contradict the listing it is labelling.
    attrs = state.get("product_attributes") or {}
    if _in_compliance_loop(state):
        tries = state.get("tries", 0) + 1
        ny = niyam_agent.run(
            s.get("category"), s.get("product_name"), s.get("quantity"),
            label_applied=True, label_text=state["compliance"].get("required_label_text"),
            product_attributes=attrs,
        )
        # The recheck echoes the existing label instead of redrafting, so it never
        # re-derives conflicts — carry forward what the first pass found rather
        # than letting a safety flag vanish on the second lap of the loop.
        if not ny.get("conflicts"):
            ny["conflicts"] = (state.get("compliance") or {}).get("conflicts", [])
        return {"compliance": ny, "tries": tries, "log": [(f"Niyam (recheck #{tries})", ny)]}
    ny = niyam_agent.run(
        s.get("category"), s.get("product_name"), s.get("quantity"),
        product_attributes=attrs,
    )
    return {"compliance": ny, "log": [("Niyam", ny)]}


def packaging_node(state) -> dict:
    s = state["suno"]
    plan = packaging_agent.run(s.get("category"), s.get("material"))
    return {"packaging_plan": plan, "log": [("Packaging", plan)]}


def wapsi_node(state) -> dict:
    s = state["suno"]
    # Wapsi learns from this category's real return history.
    try:
        history = graph_store.return_stats(s.get("category"))
    except Exception:  # noqa: BLE001 - never block the forecast on a stats read
        history = None
    w = wapsi_agent.run(s.get("product_name"), s.get("category"), s.get("attributes", {}), history)
    return {"returns": w, "log": [("Wapsi", w)]}


def return_review_node(state) -> dict:
    """Mukhiya decides whether the return risk warrants a listing fix + hold."""
    w = state["returns"]
    high = w.get("risk_level") == "high" or w.get("needs_seller_confirmation")
    if high and not state.get("return_mitigated"):
        guide = _size_guide_text(state)
        review = {"return_action": "mitigate", "reason": w.get("top_return_reason"), "size_guide": guide}
        return {"return_needs_mitigation": True, "size_guide_text": guide,
                "log": [("Mukhiya (return review)", review)]}
    review = {"return_action": "none", "reason": w.get("top_return_reason")}
    return {"return_needs_mitigation": False, "log": [("Mukhiya (return review)", review)]}


def _build_checklist(state) -> list:
    items = []
    c = state.get("compliance", {}) or {}
    if c.get("required_label_text"):
        items.append(f"Print & attach the label: {c['required_label_text']}")
    for lic in c.get("required_licenses", []) or []:
        items.append(f"Keep ready: {lic.replace('_', ' ')}")
    pack = state.get("packaging_plan", {}) or {}
    if pack:
        items.append(f"Pack it: {pack.get('primary_pack')} → {pack.get('outer_pack')}")
    if state.get("return_mitigated"):
        items.append("Review the size/colour guide added to your listing")
    missing = state.get("missing_attributes") or []
    if missing:
        items.append("Add these product details buyers expect: " + ", ".join(missing))
    w = state.get("returns", {}) or {}
    if w.get("needs_seller_confirmation") and w.get("confirmation_prompt"):
        items.append(w["confirmation_prompt"])
    items.append(f"Approve to publish at ₹{state['price']['selling_price_inr']}")
    return items


def finalize_node(state) -> dict:
    price = state["price"]
    w = state["returns"]
    approvals = [
        {"type": "go_live", "summary": "Publish this listing?"},
        {"type": "price", "summary": f"Set price ₹{price['selling_price_inr']}?"},
    ]
    # A label that contradicts the listing goes to the top of the gate, not into
    # a checklist she scrolls past — on a toy this is a child-safety statement.
    for c in (state.get("compliance") or {}).get("conflicts", []) or []:
        approvals.insert(0, {
            "type": "conflict",
            "summary": (
                f"Your listing says {c['field'].replace('_', ' ')} is "
                f"\"{c.get('listing_says')}\", but the label needs "
                f"\"{c.get('label_says')}\". {c.get('why', '')}".strip()
            ),
        })
    if w.get("needs_seller_confirmation"):
        approvals.append({"type": "confirm_attr",
                          "summary": w.get("confirmation_prompt") or "Confirm product detail?"})
    return {"status": "ready_for_approval", "approvals": approvals,
            "action_checklist": _build_checklist(state)}


def approval_node(state) -> dict:
    """The human gate, as a real LangGraph interrupt.

    The graph PAUSES here (state checkpointed to Mongo) until the seller resumes
    it via /approve with Command(resume=decision). decision is:
      {"approved": bool, "notes": str|None, "edits": {price?, title?,
        description?, attributes?{...}}|None}
    The seller can approve, reject, or edit-then-publish in one step.
    """
    decision = interrupt({
        "kind": "seller_approval",
        "listing": state.get("listing"),
        "price": state.get("price"),
        "product_attributes": state.get("product_attributes"),
        "missing_attributes": state.get("missing_attributes"),
        "compliance": state.get("compliance"),
        "returns": state.get("returns"),
        "packaging_plan": state.get("packaging_plan"),
        "approvals": state.get("approvals"),
        "action_checklist": state.get("action_checklist"),
    })

    decision = decision or {}
    approved = bool(decision.get("approved"))
    edits = decision.get("edits") or {}
    out = {}

    # Apply any seller edits before publishing.
    if edits.get("price"):
        price = dict(state.get("price") or {})
        price["selling_price_inr"] = int(edits["price"])
        price["seller_overridden"] = True
        out["price"] = price
    if edits.get("title") or edits.get("description"):
        listing = dict(state.get("listing") or {})
        if edits.get("title"):
            listing["title"] = edits["title"]
        if edits.get("description"):
            listing["description"] = edits["description"]
        out["listing"] = listing
    if edits.get("attributes"):
        merged = {**(state.get("product_attributes") or {}), **edits["attributes"]}
        out["product_attributes"] = merged
        # Recompute what's still missing — she just answered some of it, and
        # leaving the old list would publish a listing that still asks her for
        # a detail she has already given.
        category = (state.get("suno") or {}).get("category")
        out["missing_attributes"] = suno_agent.missing_for(category, merged)

    out["status"] = "published" if approved else "rejected_by_seller"
    out["seller_notes"] = decision.get("notes")
    out["log"] = [("Seller decision", {
        "approved": approved, "edits": edits, "notes": decision.get("notes"),
    })]
    return out


# ----------------------------------------------------------------- routing
def photo_gate(state) -> str:
    if not state["suno"].get("photo_ok"):
        return "reject"
    if state.get("authenticity", {}).get("verdict") == "blocked":
        return "reject"  # high-confidence stolen photo
    return "continue"


def after_likho(state) -> str:
    """Likho serves three loops — route by which one we're in."""
    if state.get("return_needs_mitigation"):
        return "finalize"
    if _in_compliance_loop(state):
        return "daam"
    return "review"


def quality_gate(state) -> str:
    return "revise" if not state["review"].get("quality_ok", True) else "pass"


def compliance_gate(state) -> str:
    c = state["compliance"]
    if c.get("compliance_ok") or state.get("tries", 0) >= MAX_COMPLIANCE_TRIES:
        return "done"
    return "loop"


def return_gate(state) -> str:
    return "mitigate" if state.get("return_needs_mitigation") else "done"


# ------------------------------------------------------------------- graph
def build_graph():
    g = StateGraph(AarambhiniState)
    g.add_node("suno", suno_node)
    g.add_node("reject", reject_node)
    g.add_node("clarify", clarify_node)
    g.add_node("likho", likho_node)
    g.add_node("review", review_node)
    g.add_node("daam", daam_node)
    g.add_node("niyam", niyam_node)
    g.add_node("packaging", packaging_node)
    g.add_node("wapsi", wapsi_node)
    g.add_node("return_review", return_review_node)
    g.add_node("finalize", finalize_node)
    g.add_node("approval", approval_node)

    g.add_edge(START, "suno")
    # Suno also fills structured attributes in the same call. Then clarify asks the
    # seller only for blocking gaps (e.g. a missing price) before Likho writes.
    g.add_conditional_edges("suno", photo_gate, {"reject": "reject", "continue": "clarify"})
    g.add_edge("reject", END)
    g.add_edge("clarify", "likho")

    # Likho fans out to whichever loop it is serving.
    g.add_conditional_edges("likho", after_likho,
                            {"review": "review", "daam": "daam", "finalize": "finalize"})

    # Quality loop.
    g.add_conditional_edges("review", quality_gate, {"revise": "likho", "pass": "daam"})

    # Compliance loop.
    g.add_edge("daam", "niyam")
    g.add_conditional_edges("niyam", compliance_gate, {"loop": "likho", "done": "packaging"})

    # Packaging → returns → return loop.
    g.add_edge("packaging", "wapsi")
    g.add_edge("wapsi", "return_review")
    g.add_conditional_edges("return_review", return_gate,
                            {"mitigate": "likho", "done": "finalize"})

    # finalize prepares the preview; approval is the real human interrupt.
    g.add_edge("finalize", "approval")
    g.add_edge("approval", END)
    # Durable checkpointing: every node's state is persisted to MongoDB, so a run
    # can pause (human interrupt), resume, or recover from a failure by thread_id.
    return g.compile(checkpointer=graph_store.checkpointer())


_GRAPH = build_graph()


def _annotate(out: dict, tid: str) -> dict:
    """Surface a pending interrupt: if the graph paused for clarification, mark it."""
    out["thread_id"] = tid
    intr = out.pop("__interrupt__", None)
    if intr:
        first = intr[0]
        payload = getattr(first, "value", first)
        if isinstance(payload, dict) and payload.get("kind") == "clarification":
            out["status"] = "needs_clarification"
            out["clarification"] = payload
    return out


def _initial_state(voice_text, image_ref, seller_id, desired_margin_pct):
    return {
        "voice_text": voice_text,
        "image_ref": image_ref,
        "seller_id": seller_id,
        "desired_margin_pct": desired_margin_pct,
        "tries": 0,
        "quality_tries": 0,
        "log": [],
    }


def run(voice_text, image_ref=None, desired_margin_pct=20, thread_id=None, seller_id=None) -> dict:
    """Run the crew. image_ref is a GridFS id (or None); the graph loads the photo
    from it so no live PIL.Image ever enters checkpointed state.

    thread_id keys the checkpoint; pass the listing/run id to make the run
    resumable. Returns the final state dict (may pause at clarification or approval).
    """
    tid = thread_id or str(uuid.uuid4())
    final = _GRAPH.invoke(
        _initial_state(voice_text, image_ref, seller_id, desired_margin_pct),
        config={"configurable": {"thread_id": tid}},
    )
    return _annotate(dict(final), tid)


def resume(thread_id, value) -> dict:
    """Resume a paused run. value is the seller's clarification answers OR approval
    decision, depending on which interrupt the run is paused at.
    """
    final = _GRAPH.invoke(
        Command(resume=value),
        config={"configurable": {"thread_id": thread_id}},
    )
    return _annotate(dict(final), thread_id)


def stream_run(voice_text, image_ref=None, desired_margin_pct=20, thread_id=None, seller_id=None):
    """Yield per-node updates as the crew runs, for live streaming to the UI.

    Each item is a dict {node_name: state_delta} (LangGraph stream_mode=updates).
    The stream ends when the run pauses at an interrupt (clarify / approval) or
    finishes; call final_state(thread_id) afterwards for the full state to persist.
    """
    tid = thread_id or str(uuid.uuid4())
    yield from _GRAPH.stream(
        _initial_state(voice_text, image_ref, seller_id, desired_margin_pct),
        config={"configurable": {"thread_id": tid}},
        stream_mode="updates",
    )


def final_state(thread_id) -> dict:
    """The full state after a (possibly paused) streamed run, annotated like run()."""
    config = {"configurable": {"thread_id": thread_id}}
    snap = _GRAPH.get_state(config)
    out = dict(snap.values)
    out["thread_id"] = thread_id
    if snap.next == ("clarify",):
        out["status"] = "needs_clarification"
        out["clarification"] = {"kind": "clarification", "questions": _blocking_gaps(snap.values)}
    return out


if __name__ == "__main__":
    import json

    result = run("मैं हाथ से बने जूट बैग बनाती हूँ, 40 पीस, ₹200 लागत।")
    print("STATUS:", result["status"])
    print("\n--- ACTIVITY LOG (all three loops) ---")
    for name, out in result["log"]:
        print(f"  · {name}")
    print("\n--- CHECKLIST ---")
    for item in result.get("action_checklist", []):
        print("  □", item)
