"""
Forms & Notes module.
Handwritten production-floor notes, sales meeting jots, mixed printed/handwritten forms.
Phase 2 will add the Zebra "edit-an-order" workflow.
"""
import streamlit as st
from pathlib import Path

from pipeline import process_document
from shared import inject_styles, render_page_header, render_antera_handoff, chat_sidebar

st.set_page_config(page_title="Forms & Notes", page_icon=":pencil2:", layout="wide")
inject_styles()
render_page_header("✍️ Forms & Notes", "Handwritten notes + mixed printed/handwritten forms")
render_antera_handoff("Action items and unresolved questions attach as tasks or production-note comments. Coming next: Zebra edit-an-order - snap a marked-up work order, system applies the handwritten changes before production locks.")

uploaded = st.file_uploader("Drop a handwritten note, sales jot, or mixed form (PDF / JPG / PNG)", type=["pdf", "jpg", "jpeg", "png"])
if uploaded is None:
    st.info("Upload a handwritten note or filled form to begin.")
    st.stop()

file_bytes = uploaded.read()
file_ext = Path(uploaded.name).suffix.lower()

cache_key = f"forms-{uploaded.name}-{len(file_bytes)}"
if st.session_state.get("forms_cache_key") != cache_key:
    with st.spinner("Processing..."):
        try:
            result = process_document(file_bytes, file_ext, mode_override="document")
        except Exception as e:
            st.error(f"Pipeline error: {type(e).__name__}: {e}")
            st.stop()
    st.session_state["forms_cache_key"] = cache_key
    st.session_state["forms_result"] = result
else:
    result = st.session_state["forms_result"]

col_left, col_right = st.columns([1, 1])
with col_left:
    st.subheader("Input")
    st.image(result["input_image"], use_container_width=True)
    st.caption(f"`{uploaded.name}`" + (f" - {result['page_count']} pages (showing page 1)" if result["page_count"] > 1 else ""))

with col_right:
    st.subheader("Extracted Note / Form")
    structured = result.get("structured")
    if not structured:
        st.warning("No text detected.")
        st.stop()

    doc_type = structured.get("document_type", "unknown")
    confidence = structured.get("confidence", "unknown")
    badge = {"high": "🟢 high", "medium": "🟡 medium", "low": "🔴 low"}.get(confidence, "⚪")
    st.markdown(f"**Doc type:** `{doc_type}` &nbsp;·&nbsp; **Confidence:** {badge}")
    if doc_type not in ("handwritten_note", "mixed_form"):
        st.warning(f"Classified as `{doc_type}` - check the matching module on home.")

    data = structured.get("extracted_data", {}) or {}

    if doc_type == "handwritten_note":
        if data.get("date"): st.markdown(f"**Date:** {data['date']}")
        if data.get("author"): st.markdown(f"**Author:** {data['author']}")
        if data.get("subject"): st.markdown(f"**Subject:** {data['subject']}")
        if data.get("key_fields"):
            st.markdown("**Key fields:**")
            st.json(data["key_fields"])
        if data.get("action_items"):
            st.markdown("**Action items:**")
            for item in data["action_items"]:
                st.markdown(f"- {item}")
        if data.get("unresolved"):
            st.warning("**Unresolved:** " + str(data["unresolved"]))

    elif doc_type == "mixed_form":
        if data.get("form_type"): st.markdown(f"**Form type:** {data['form_type']}")
        if data.get("printed_fields"):
            st.markdown("**Printed fields:**")
            st.json(data["printed_fields"])
        if data.get("handwritten_fields"):
            st.markdown("**Handwritten fields:**")
            st.json(data["handwritten_fields"])
        if data.get("unfilled_fields"):
            st.markdown("**Unfilled fields:**")
            for f in data["unfilled_fields"]:
                st.markdown(f"- {f}")
    else:
        st.json(data)

    flags = structured.get("flags", [])
    if flags:
        st.warning("**Flags:** " + " · ".join(flags))
    if structured.get("notes"):
        st.info(f"**Notes:** {structured['notes']}")

    meta = structured.get("_meta", {})
    st.caption(f"Tokens: {meta.get('tokens_in','?')}→{meta.get('tokens_out','?')} · Cost: ~${meta.get('approx_cost_usd','?')}")
    with st.expander("Full JSON"):
        st.json(structured)
    with st.expander(f"Raw OCR text ({len(result.get('raw_ocr','')):,} chars)"):
        st.code(result.get("raw_ocr", "") or "(no text)", language="text")
