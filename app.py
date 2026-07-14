"""Aarambhini — Streamlit UI.

From a voice note to a live listing. The middle column is the whole point: it
shows the agent crew rejecting and re-doing each other's work, then pausing for
the seller's approval.
"""
import io
import os

import streamlit as st
from PIL import Image

import orchestrator
from llm import transcribe_audio
from utils.trust_qr import build_trust_qr

st.set_page_config(page_title="Aarambhini", page_icon="🪡", layout="wide")

HINDI_EXAMPLE = "मैं हाथ से बने जूट बैग बनाती हूँ, 40 पीस, ₹200 लागत।"

st.title("🪡 Aarambhini")
st.caption("From a voice note to a live listing — an AI co-founder for rural women sellers.")

# --- session state ---
if "result" not in st.session_state:
    st.session_state.result = None
if "published" not in st.session_state:
    st.session_state.published = False
if "voice_text" not in st.session_state:
    st.session_state.voice_text = HINDI_EXAMPLE
if "transcription_status" not in st.session_state:
    st.session_state.transcription_status = None

col_in, col_log, col_out = st.columns([1, 1.3, 1.3], gap="large")

# ------------------------------------------------------------------ INPUT
with col_in:
    st.subheader("1 · Speak / type")
    voice_note = st.audio_input("Record a voice note")
    if voice_note is not None:
        if st.button("Transcribe voice note", use_container_width=True):
            with st.spinner("Transcribing voice note..."):
                try:
                    st.session_state.voice_text = transcribe_audio(
                        voice_note.getvalue(), voice_note.type or "audio/wav"
                    )
                    st.session_state.result = None
                    st.session_state.published = False
                    st.session_state.transcription_status = ("success", "Transcript added below.")
                except Exception as e:  # noqa: BLE001
                    st.session_state.transcription_status = (
                        "error",
                        f"Could not transcribe audio: {e}",
                    )
            st.rerun()

    if st.session_state.transcription_status:
        status, message = st.session_state.transcription_status
        if status == "success":
            st.success(message)
        else:
            st.error(message)

    voice_text = st.text_area(
        "In your own language",
        key="voice_text",
        height=120,
        help="Hindi, Tamil, Bengali, English… Suno detects the language.",
    )
    margin = st.slider("Desired margin %", 5, 60, 20, 5)
    use_sample = st.checkbox("Use sample jute-bag photo", value=True)
    uploaded = st.file_uploader("Upload one product photo", type=["png", "jpg", "jpeg", "webp"])

    image = None
    if use_sample:
        image = Image.open(os.path.join(os.path.dirname(__file__), "jute_bag.webp"))
        st.image(image, caption="Sample product photo", use_container_width=True)
    elif uploaded is not None:
        image = Image.open(io.BytesIO(uploaded.read()))
        st.image(image, caption="Your photo", use_container_width=True)

    if st.button("Run Aarambhini", type="primary", use_container_width=True):
        st.session_state.published = False
        with st.spinner("The crew is working…"):
            try:
                st.session_state.result = orchestrator.run(
                    voice_text, image=image, desired_margin_pct=margin
                )
            except Exception as e:  # noqa: BLE001
                st.session_state.result = {"status": "error", "error": str(e)}

result = st.session_state.result

# --------------------------------------------------------------- ACTIVITY LOG
with col_log:
    st.subheader("2 · Agent Activity Log")
    if not result:
        st.info("Run Aarambhini to watch the crew work.")
    elif result.get("status") == "error":
        st.error(f"Something went wrong: {result['error']}")
        st.caption("If this mentions GEMINI_API_KEY, add your key to the .env file.")
    else:
        for name, out in result["log"]:
            is_rerun = "re-run" in name or "re-price" in name or "recheck" in name
            icon = "🔁" if is_rerun else "✅"
            with st.status(f"{icon} {name}", state="complete", expanded=is_rerun):
                st.json(out)
        if result.get("status") == "needs_retake":
            st.warning(f"📸 Photo rejected: {result['reason']}")

# ------------------------------------------------------------------- RESULTS
with col_out:
    st.subheader("3 · Results")
    if not result or result.get("status") == "error":
        st.empty()
    elif result.get("status") == "needs_retake":
        st.warning(
            "The pipeline stopped at the photo gate — nothing else ran. "
            f"Reason: **{result['reason']}**. Please upload a clearer photo and run again."
        )
    else:
        listing = result["listing"]
        price = result["price"]
        comp = result["compliance"]
        ret = result["returns"]

        st.markdown(f"### {listing.get('title', '')}")
        st.write(listing.get("description", ""))
        if listing.get("maker_story"):
            st.caption("👩‍🌾 " + listing["maker_story"])
        st.write("**Keywords:** " + ", ".join(listing.get("keywords", [])))

        c1, c2 = st.columns(2)
        with c1:
            st.metric("Selling price", f"₹{price['selling_price_inr']}", f"{price['margin_pct']}% margin")
            st.caption(f"Discount floor (break-even): ₹{price['discount_floor_inr']}")
            rng = price.get("typical_range_inr")
            if rng:
                ok = "within" if price["within_typical_range"] else "outside"
                st.caption(f"Typical ₹{rng[0]}–₹{rng[1]} · {ok} range")
        with c2:
            if comp.get("compliance_ok"):
                st.success("Compliance ✅")
            else:
                st.warning("Compliance ⚠️")
            if comp.get("required_labels"):
                st.caption("Labels: " + ", ".join(comp["required_labels"]))
            if comp.get("required_licenses"):
                st.caption("⚠️ Licenses needed: " + ", ".join(comp["required_licenses"]))
            st.caption(comp.get("gst_note", ""))

        risk = ret.get("risk_level", "?")
        risk_icon = {"low": "🟢", "medium": "🟡", "high": "🔴"}.get(risk, "⚪")
        st.markdown(f"**Returns risk:** {risk_icon} {risk.title()} — {ret.get('top_return_reason','')}")
        if ret.get("mitigations"):
            st.write("Mitigations: " + "; ".join(ret["mitigations"]))

        pack = result.get("packaging_plan", {})
        if pack:
            st.markdown("**Packaging plan:**")
            st.write(f"{pack.get('primary_pack', '')} → {pack.get('outer_pack', '')}")
            st.caption(pack.get("handling_note", ""))

        checklist = result.get("action_checklist", [])
        if checklist:
            st.markdown("**Action checklist:**")
            for item in checklist:
                st.checkbox(item, value=True, disabled=True)

        st.markdown(
            f"---\n**Ready to list ✅ · Price ₹{price['selling_price_inr']} · "
            f"Returns risk: {risk.title()}**"
        )

# --------------------------------------------------------------- APPROVAL GATE
if result and result.get("status") == "ready_for_approval":
    st.divider()
    st.subheader("4 · Seller approval — nothing goes live without your tap")
    cols = st.columns(len(result["approvals"]))
    for i, ap in enumerate(result["approvals"]):
        cols[i].info(ap["summary"])

    if not st.session_state.published:
        if st.button("✅ Approve & publish", type="primary"):
            st.session_state.published = True
            st.rerun()
    else:
        st.success("Published ✅ — your listing is live.")
        qr_path, payload = build_trust_qr(
            result["listing"], result["price"], result["compliance"]
        )
        qc1, qc2 = st.columns([1, 2])
        with qc1:
            st.image(qr_path, caption="Trust QR (provenance)", width=200)
        with qc2:
            st.json(payload)
