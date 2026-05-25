"""
Receipts & Expenses module - batch upload, edit, accept to local queue.
Mocked Antera Job ID dropdown per customer.
"""
import streamlit as st
import json
from pathlib import Path

from pipeline import process_document, fmt_money
import customer_repo as repo
from shared import inject_styles, render_page_header, render_antera_handoff, customer_selector, expand_uploads, chat_sidebar

st.set_page_config(page_title="Receipts & Expenses - HDS", page_icon=":receipt:", layout="wide")
inject_styles()
chat_sidebar()
render_page_header("💳 Receipts & Expenses", "Batch-snap receipts, edit, file against a job.")
render_antera_handoff(
    "Replaces the email-photo-with-job-number-in-subject workflow. Job dropdown is pulled from the "
    "customer's active Antera Jobs - rep picks from list, no remembering or fat-fingering. Accepted "
    "expenses queue locally for the Reporting module; in production they push to Antera Job Costing."
)

st.markdown("---")
active_customer = customer_selector(required=False, label="Customer this expense belongs to")

# Antera Job dropdown (mocked from antera_jobs.json per customer)
job_number = ""
job_description = ""
if active_customer:
    jobs = repo.list_antera_jobs(active_customer["customer_id"])
    if jobs:
        job_labels = [f"{j['job_id']}  —  {j['description']}" for j in jobs]
        job_labels = ["(no job)"] + job_labels
        picked = st.selectbox(
            "Antera Job ID",
            job_labels,
            help="Mocked from the customer's active Antera jobs. In production this is a live API call to Antera.",
        )
        if picked != "(no job)":
            idx = job_labels.index(picked) - 1
            job_number = jobs[idx]["job_id"]
            job_description = jobs[idx]["description"]
    else:
        st.caption(f"_No mocked Antera jobs for {active_customer['display_name']} yet. Use the seed script or add via API in production._")
else:
    st.caption("_Select a customer to see their Antera Jobs._")

uploaded_files = st.file_uploader(
    "Drop one or more receipts (JPG / PNG / PDF) or a ZIP of receipts",
    type=["jpg", "jpeg", "png", "pdf", "zip"],
    accept_multiple_files=True,
)
if not uploaded_files:
    st.info("Upload receipt photos to begin. Batch + ZIP supported - drop a whole week's worth or a zipped folder.")
    st.markdown("---")
    # Show queue status even when no upload
    queue_count = len(repo.list_queue("receipts"))
    st.markdown(f"**Receipts queue:** {queue_count} accepted entries waiting in the Reporting module.")
    st.stop()

# Expand any zip files into their contents
ALLOWED = {".jpg", ".jpeg", ".png", ".pdf"}
expanded = expand_uploads(uploaded_files, allowed_exts=list(ALLOWED))
if not expanded:
    st.warning("No usable receipts found in upload (zip may be empty or contain only non-receipt types).")
    st.stop()

# Process each uploaded receipt
st.markdown(f"### Processing {len(expanded)} receipt(s)")
st.caption("Each tile shows the extracted data + lets you edit any field before clicking Accept. Accepted entries flow to the Reporting module's Receipts queue.")

CATEGORIES = [
    "meals_dining", "fuel", "supplies", "materials", "parking",
    "lodging", "shipping", "software_subscriptions", "equipment",
    "repairs_maintenance", "other",
]

for upload_idx, (display_name, file_bytes, file_ext) in enumerate(expanded):
    with st.container(border=True):
        cache_key = f"receipt-{display_name}-{len(file_bytes)}"

        if st.session_state.get(f"_rec_cache_{cache_key}") != cache_key:
            with st.spinner(f"Reading {display_name}..."):
                try:
                    result = process_document(file_bytes, file_ext, mode_override="document")
                except Exception as e:
                    st.error(f"{display_name}: Pipeline error: {type(e).__name__}: {e}")
                    continue
            st.session_state[f"_rec_cache_{cache_key}"] = cache_key
            st.session_state[f"_rec_result_{cache_key}"] = result
        else:
            result = st.session_state[f"_rec_result_{cache_key}"]

        structured = result.get("structured")
        if not structured:
            st.warning(f"{display_name}: no text detected.")
            continue

        data = structured.get("extracted_data", {}) or {}
        merchant = data.get("merchant") or {}
        doc_type = structured.get("document_type", "unknown")
        confidence = structured.get("confidence", "unknown")
        badge = {"high": "🟢", "medium": "🟡", "low": "🔴"}.get(confidence, "⚪")

        # Two columns: preview on left, editable fields on right
        prev_col, edit_col = st.columns([1, 2])
        with prev_col:
            st.image(result["input_image"], use_container_width=True)
            st.caption(f"`{display_name}` · {len(file_bytes):,} bytes")
            st.caption(f"{badge} `{doc_type}` confidence: {confidence}")

        with edit_col:
            st.markdown(f"#### Receipt {upload_idx + 1}")

            # Pre-fill editable widgets from extracted values
            kp = f"rec_{upload_idx}"  # key prefix unique per upload in this batch
            merch_default = merchant.get("name") if isinstance(merchant, dict) else (merchant or "")
            edit_merchant = st.text_input("Merchant", value=str(merch_default or ""), key=f"{kp}_merchant")
            edit_date = st.text_input("Date", value=str(data.get("date") or ""), key=f"{kp}_date")

            ecols1 = st.columns(4)
            edit_subtotal = ecols1[0].text_input("Subtotal", value=str(data.get("subtotal") or ""), key=f"{kp}_subtotal")
            edit_tax = ecols1[1].text_input("Tax", value=str(data.get("tax") or ""), key=f"{kp}_tax")
            edit_tip = ecols1[2].text_input("Tip", value=str(data.get("tip") or ""), key=f"{kp}_tip")
            edit_total = ecols1[3].text_input("Total", value=str(data.get("total") or ""), key=f"{kp}_total")

            ecols2 = st.columns(3)
            edit_payment = ecols2[0].text_input("Payment method", value=str(data.get("payment_method") or ""), key=f"{kp}_pay")
            edit_last4 = ecols2[1].text_input("Card last 4", value=str(data.get("card_last_four") or ""), key=f"{kp}_last4")

            # Category dropdown - Claude-suggested pre-selected
            suggested_cat = data.get("suggested_expense_category", "other")
            if suggested_cat not in CATEGORIES:
                suggested_cat = "other"
            edit_category = ecols2[2].selectbox(
                "Category",
                CATEGORIES,
                index=CATEGORIES.index(suggested_cat),
                key=f"{kp}_cat",
            )

            edit_notes = st.text_input("Notes", placeholder="e.g. Client lunch with Acme marketing team", key=f"{kp}_notes")

            flags = structured.get("flags", [])
            if flags:
                st.warning("Flags for review: " + " · ".join(flags))

            # Accept button
            ac1, ac2 = st.columns([1, 3])
            with ac1:
                accept_disabled = active_customer is None
                accept_btn = st.button(
                    "✅ Accept" if active_customer else "✅ Accept (pick customer first)",
                    key=f"{kp}_accept",
                    type="primary",
                    disabled=accept_disabled,
                )
            with ac2:
                if st.session_state.get(f"{kp}_accepted"):
                    st.success(f"Filed as `{st.session_state[f'{kp}_accepted']}`")

            if accept_btn and active_customer:
                queue_entry = {
                    "filename": display_name,
                    "customer_id": active_customer["customer_id"],
                    "customer_name": active_customer["display_name"],
                    "antera_customer_id": active_customer.get("antera_customer_id"),
                    "job_number": job_number or None,
                    "job_description": job_description or None,
                    "merchant_name": edit_merchant,
                    "date": edit_date,
                    "subtotal": edit_subtotal,
                    "tax": edit_tax,
                    "tip": edit_tip,
                    "total": edit_total,
                    "payment_method": edit_payment,
                    "card_last_four": edit_last4,
                    "category": edit_category,
                    "notes": edit_notes,
                    "doc_confidence": confidence,
                    "ocr_flags": flags,
                }
                saved = repo.append_to_queue("receipts", queue_entry)
                # Also persist under customer expense history
                repo.save_expense(active_customer["customer_id"], queue_entry)
                st.session_state[f"{kp}_accepted"] = saved["entry_id"]
                st.rerun()

# Footer queue counter
st.markdown("---")
st.markdown(f"**Receipts queue:** {len(repo.list_queue('receipts'))} accepted entries. View in **Reporting** module.")