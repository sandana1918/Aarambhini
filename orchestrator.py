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
from typing import Annotated, Any, TypedDict

from langgraph.graph import StateGraph, START, END

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
    image: Any
    desired_margin_pct: int
    # agent outputs
    suno: dict
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
    if cat in ("handloom_textiles", "apparel", "home_furnishing"):
        return ("Size & colour note: exact measurements are listed above; being handmade, "
                "colours may vary slightly on different screens.")
    if cat in ("jewellery_precious", "imitation_jewellery"):
        return ("Size note: please check the listed dimensions and message us to confirm "
                "fit before ordering.")
    return ("Please review the listed size and colour details, and message us with any "
            "questions before ordering.")


# ------------------------------------------------------------------ nodes
def suno_node(state) -> dict:
    s = suno_agent.run(state["voice_text"], state.get("image"))
    return {"suno": s, "tries": 0, "quality_tries": 0, "log": [("Suno", s)]}


def reject_node(state) -> dict:
    s = state["suno"]
    return {"status": "needs_retake", "reason": s.get("photo_issue") or "photo unclear"}


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
    if _in_compliance_loop(state):
        tries = state.get("tries", 0) + 1
        ny = niyam_agent.run(
            s.get("category"), s.get("product_name"), s.get("quantity"),
            label_applied=True, label_text=state["compliance"].get("required_label_text"),
        )
        return {"compliance": ny, "tries": tries, "log": [(f"Niyam (recheck #{tries})", ny)]}
    ny = niyam_agent.run(s.get("category"), s.get("product_name"), s.get("quantity"))
    return {"compliance": ny, "log": [("Niyam", ny)]}


def packaging_node(state) -> dict:
    s = state["suno"]
    plan = packaging_agent.run(s.get("category"), s.get("material"))
    return {"packaging_plan": plan, "log": [("Packaging", plan)]}


def wapsi_node(state) -> dict:
    s = state["suno"]
    w = wapsi_agent.run(s.get("product_name"), s.get("category"), s.get("attributes", {}))
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
    if w.get("needs_seller_confirmation"):
        approvals.append({"type": "confirm_attr",
                          "summary": w.get("confirmation_prompt") or "Confirm product detail?"})
    return {"status": "ready_for_approval", "approvals": approvals,
            "action_checklist": _build_checklist(state)}


# ----------------------------------------------------------------- routing
def photo_gate(state) -> str:
    return "continue" if state["suno"].get("photo_ok") else "reject"


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
    g.add_node("likho", likho_node)
    g.add_node("review", review_node)
    g.add_node("daam", daam_node)
    g.add_node("niyam", niyam_node)
    g.add_node("packaging", packaging_node)
    g.add_node("wapsi", wapsi_node)
    g.add_node("return_review", return_review_node)
    g.add_node("finalize", finalize_node)

    g.add_edge(START, "suno")
    g.add_conditional_edges("suno", photo_gate, {"reject": "reject", "continue": "likho"})
    g.add_edge("reject", END)

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

    g.add_edge("finalize", END)
    return g.compile()


_GRAPH = build_graph()


def run(voice_text, image=None, desired_margin_pct=20) -> dict:
    """Same interface as before — app.py is unchanged. Returns the final state dict."""
    final = _GRAPH.invoke({
        "voice_text": voice_text,
        "image": image,
        "desired_margin_pct": desired_margin_pct,
        "tries": 0,
        "quality_tries": 0,
        "log": [],
    })
    return dict(final)


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
