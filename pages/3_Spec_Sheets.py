"""
Spec Sheets module.
Product data sheet extraction - Madeira thread, Wilflex ink, blank apparel specs.
"""
import streamlit as st
from pathlib import Path

from pipeline import process_document
from shared import inject_styles, render_page_header, render_antera_handoff, chat_sidebar

st.set_page_config(page_title="Spec Sheets - HDS", page_icon=":clipboard:", layout="wide")
inject_styles()
render_page_header("📋 Spec Sheets", "Product data sheet → standardized reference table")
render_antera_handoff("Outputs an Item Master import row - manufacturer, product line, composition, key specs - so spec data goes from PDF to product catalog without manual re-entry.")

uploaded = st.file_uploader("Drop a product data sheet (PDF / JPG / PNG)", type=["pdf", "jpg", "jpeg", "png"])
if uploaded is None:
    st.info("Upload a spec sheet (e.g. Madeira thread datasheet) to begin.")
    st.stop()

file_bytes = uploaded.read()
file_ext = Path(uploaded.name).suffix.lower()

cache_key = f"spec-{uploaded.name}-{len(file_bytes)}"
if st.session_state.get("spec_cache_key") != cache_key:
    with st.spinner("Processing..."):
        try:
            result = process_document(file_bytes, file_ext, mode_override="document")
        except Exception as e:
            st.error(f"Pipeline error: {type(e).__name__}: {e}")
            st.stop()
    st.session_state["spec_cache_key"] = cache_key
    st.session_state["spec_result"] = result
else:
    result = st.session_state["spec_result"]

col_left, col_right = st.columns([1, 1])
with col_left:
    st.subheader("Input")
    st.image(result["input_image"], use_container_width=True)
    st.caption(f"`{uploaded.name}`" + (f" - {result['page_count']} pages (showing page 1)" if result["page_count"] > 1 else ""))

with col_right:
    st.subheader("Standardized Spec Reference")
    structured = result.get("structured")
    if not structured:
        st.warning("No text detected.")
        st.stop()

    doc_type = structured.get("document_type", "unknown")
    confidence = structured.get("confidence", "unknown")
    badge = {"high": "🟢 high", "medium": "🟡 medium", "low": "🔴 low"}.get(confidence, "⚪")
    st.markdown(f"**Doc type:** `{doc_type}` &nbsp;·&nbsp; **Confidence:** {badge}")
    if doc_type != "product_data_sheet":
        st.warning(f"This was classified as `{doc_type}`, not a spec sheet.")

    data = structured.get("extracted_data", {}) or {}

    # Render as a standardized two-column table
    def row(label, value):
        if value is None or value == "" or value == {}:
            return
        c1, c2 = st.columns([1, 2])
        c1.markdown(f"**{label}**")
        if isinstance(value, (dict, list)):
            c2.json(value)
        else:
            c2.markdown(str(value))

    row("Manufacturer", data.get("manufacturer"))
    row("Product name", data.get("product_name"))
    row("Product line", data.get("product_line"))
    row("Product type", data.get("product_type"))
    row("Composition", data.get("composition"))
    row("Key specs", data.get("key_specs"))
    row("Test ratings", data.get("test_ratings"))
    row("Mechanical properties", data.get("mechanical_properties"))
    row("Care instructions", data.get("care_instructions"))
    row("Certifications", data.get("certifications"))
    row("Document date", data.get("document_date"))
    row("Manufacturer contact", data.get("manufacturer_contact"))

    flags = structured.get("flags", [])
    if flags:
        st.warning("**Flags:** " + " · ".join(flags))

    if structured.get("notes"):
        st.info(f"**Notes:** {structured['notes']}")

    meta = structured.get("_meta", {})
    st.caption(f"Tokens: {meta.get('tokens_in','?')}→{meta.get('tokens_out','?')} · Cost: ~${meta.get('approx_cost_usd','?')}")
    with st.expander("Full JSON"):
        st.json(structured)
