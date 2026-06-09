"""
Bills & Invoices module.
Vendor invoices + freight invoices. Extracts structured data ready for AP review.
"""
import streamlit as st
import json
from pathlib import Path

from pipeline import process_document
from shared import inject_styles, render_page_header, render_antera_handoff, chat_sidebar

st.set_page_config(page_title="Bills & Invoices - HDS", page_icon=":receipt:", layout="wide")
inject_styles()
render_page_header("🧾 Bills & Invoices", "Vendor + freight invoice extraction for AP")
render_antera_handoff("Extracted JSON pushes to a Sheets AP queue (Phase 2) where AP reviews and bulk-approves into AP. Single point of human review, audit-friendly.")

uploaded = st.file_uploader("Drop an invoice (PDF / JPG / PNG)", type=["pdf", "jpg", "jpeg", "png"])
if uploaded is None:
    st.info("Upload a vendor or freight invoice to begin.")
    st.stop()

file_bytes = uploaded.read()
file_ext = Path(uploaded.name).suffix.lower()

cache_key = f"bills-{uploaded.name}-{len(file_bytes)}"
if st.session_state.get("bills_cache_key") != cache_key:
    with st.spinner("Processing..."):
        try:
            result = process_document(file_bytes, file_ext, mode_override="document")
        except Exception as e:
            st.error(f"Pipeline error: {type(e).__name__}: {e}")
            st.stop()
    st.session_state["bills_cache_key"] = cache_key
    st.session_state["bills_result"] = result
else:
    result = st.session_state["bills_result"]

col_left, col_right = st.columns([1, 1])
with col_left:
    st.subheader("Input")
    st.image(result["input_image"], use_container_width=True)
    st.caption(f"`{uploaded.name}` - {len(file_bytes):,} bytes" +
               (f" - {result['page_count']} pages (showing page 1)" if result["page_count"] > 1 else ""))

with col_right:
    st.subheader("Extracted Invoice")
    structured = result.get("structured")
    if not structured:
        st.warning("No text detected.")
        st.stop()

    doc_type = structured.get("document_type", "unknown")
    confidence = structured.get("confidence", "unknown")
    badge = {"high": "🟢 high", "medium": "🟡 medium", "low": "🔴 low"}.get(confidence, "⚪")
    st.markdown(f"**Doc type:** `{doc_type}` &nbsp;·&nbsp; **Confidence:** {badge}")

    if doc_type not in ("vendor_invoice", "freight_invoice"):
        st.warning(f"This was classified as `{doc_type}`, not an invoice. Check the home page for the matching module.")

    flags = structured.get("flags", [])
    if flags:
        st.warning("**Flags for human review:** " + " · ".join(flags))

    data = structured.get("extracted_data", {}) or {}

    # Vendor invoice render
    if doc_type == "vendor_invoice":
        vendor = data.get("vendor") or {}
        txn = data.get("transaction") or {}
        totals = data.get("totals") or {}
        st.markdown(f"**Vendor:** {vendor.get('name','?')}")
        if vendor.get("address"): st.caption(vendor["address"])
        st.markdown(f"**Invoice #:** `{txn.get('invoice_number','?')}` &nbsp;·&nbsp; **Date:** {txn.get('date','?')} &nbsp;·&nbsp; **PO:** `{txn.get('po_number','?')}`")
        items = data.get("line_items") or []
        if items:
            st.markdown("**Line items:**")
            hcols = st.columns([3, 1, 0.7, 1, 1])
            for c, h in zip(hcols, ["Description", "SKU", "Qty", "Unit", "Ext"]):
                c.markdown(f"**{h}**")
            for it in items:
                cols = st.columns([3, 1, 0.7, 1, 1])
                cols[0].markdown(it.get("description", "—"))
                cols[1].markdown(f"`{it.get('sku','—')}`")
                cols[2].markdown(f"{it.get('quantity','—')}")
                cols[3].markdown(f"${it.get('unit_price','—')}")
                cols[4].markdown(f"**${it.get('extended_price','—')}**")
        st.markdown("---")
        tcol1, tcol2, tcol3, tcol4 = st.columns(4)
        tcol1.metric("Subtotal", f"${totals.get('subtotal','—')}")
        tcol2.metric("Tax", f"${totals.get('tax','—')}")
        tcol3.metric("Freight", f"${totals.get('freight','—')}")
        tcol4.metric("Total", f"${totals.get('total','—')}")
        pay = data.get("payment") or {}
        if pay:
            st.caption(f"Payment: {pay.get('method','?')} · last 4: `{pay.get('last_four','—')}`")

    # Freight invoice render
    elif doc_type == "freight_invoice":
        st.markdown(f"**Carrier:** {data.get('carrier','?')}")
        st.markdown(f"**Tracking:** `{data.get('tracking_number','?')}` &nbsp;·&nbsp; **Service:** {data.get('service_level','?')}")
        st.markdown(f"**{data.get('origin','?')}** → **{data.get('destination','?')}**")
        st.markdown(f"Ship date: {data.get('ship_date','?')} · Weight: {data.get('weight','?')}")
        ch = data.get("charges") or {}
        if ch:
            ccols = st.columns(4)
            ccols[0].metric("Base", f"${ch.get('base','—')}")
            ccols[1].metric("Fuel SC", f"${ch.get('fuel_surcharge','—')}")
            ccols[2].metric("Accessorial", f"${ch.get('accessorial','—')}")
            ccols[3].metric("Total", f"${ch.get('total','—')}")
    else:
        st.json(data)

    if structured.get("notes"):
        st.info(f"**Notes:** {structured['notes']}")

    meta = structured.get("_meta", {})
    st.caption(f"Tokens: {meta.get('tokens_in','?')}→{meta.get('tokens_out','?')} · Cost: ~${meta.get('approx_cost_usd','?')}")
    with st.expander("Full JSON"):
        st.json(structured)
    with st.expander(f"Raw OCR text ({len(result.get('raw_ocr','')):,} chars)"):
        st.code(result.get("raw_ocr", "") or "(no text)", language="text")
