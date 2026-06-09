"""
Customer Library module.
Browse-only view of all customers, their saved artwork, and their order history.
Reload any past logo into the Artwork module to re-run the workflow.
"""
import streamlit as st
import json
from pathlib import Path
from PIL import Image

from pipeline import svg_to_pil
import customer_repo as repo
from shared import inject_styles, render_page_header, render_antera_handoff, chat_sidebar

st.set_page_config(page_title="Customer Library - HDS", page_icon=":busts_in_silhouette:", layout="wide")
inject_styles()
render_page_header("👥 Customer Library", "Customers, their artwork, their orders")
render_antera_handoff("Indexed by Customer ID. still owns billing, contacts, and payment terms - this is the artwork + decoration history layer doesn't natively manage. Phase 2 chatbot queries directly against this data.")

customers = repo.list_customers()

if not customers:
    st.info("No customers yet. Create one from the Artwork & Order Builder or Customer Orders module.")
    st.stop()

st.markdown(f"**{len(customers)} customers** in repository.")
st.markdown("---")

# Customer picker
labels = [f"{c['display_name']} [{c['customer_id'][:8]}]" for c in customers]
selected_label = st.selectbox("Browse customer:", labels)
short_id = selected_label.split("[")[-1].rstrip("]")
customer = next((c for c in customers if c["customer_id"].startswith(short_id)), None)
if not customer:
    st.stop()

# Customer card
info_col1, info_col2, info_col3 = st.columns([2, 1, 1])
with info_col1:
    st.markdown(f"### {customer['display_name']}")
    if customer.get("notes"):
        st.caption(customer["notes"])
with info_col2:
    st.metric("ID", customer.get("antera_customer_id") or "—")
with info_col3:
    st.metric("Created", customer.get("created_at", "")[:10] or "—")

logos = repo.list_logos(customer["customer_id"])
orders = repo.list_orders(customer["customer_id"])

st.markdown("---")

# Logos panel
st.subheader(f"📁 Saved artwork ({len(logos)})")
if logos:
    cols = st.columns(min(5, max(1, len(logos))))
    for i, lg in enumerate(logos):
        with cols[i % len(cols)]:
            try:
                # Reconstruct path cross-platform - ignore stored Windows paths
                logo_path = repo.get_logo_path(customer["customer_id"], lg["logo_id"])
                if logo_path and logo_path.exists():
                    if lg["ext"] == ".svg":
                        with open(logo_path, "rb") as f:
                            img = svg_to_pil(f.read())
                    else:
                        img = Image.open(logo_path)
                    img.thumbnail((160, 160))
                    st.image(img, caption=lg["original_filename"])
                else:
                    st.caption(f"({lg['original_filename']})")
            except Exception:
                st.caption(f"({lg['original_filename']})")
            st.caption(f"Saved: {lg.get('uploaded_at','')[:16]}")
            if st.button("Open in Artwork module", key=f"open_{lg['logo_id']}"):
                st.session_state["reload_logo_id"] = lg["logo_id"]
                st.session_state["active_customer_label"] = selected_label
                try:
                    st.switch_page("pages/1_Artwork_and_Order_Builder.py")
                except Exception:
                    st.info("Navigate to Artwork module from the sidebar.")
else:
    st.caption("_No artwork uploaded for this customer yet._")

st.markdown("---")

# Orders panel
st.subheader(f"📦 Order history ({len(orders)})")
if orders:
    for o in orders:
        with st.container(border=True):
            ocol1, ocol2, ocol3 = st.columns([2, 1, 1])
            with ocol1:
                st.markdown(f"**`{o['order_id']}`**")
                st.caption(f"{o.get('filename','—')} · {o.get('method','—')} · {o.get('created_at','')[:16]}")
            with ocol2:
                if "total_units" in o:
                    st.metric("Units", f"{o.get('total_units',0):,}")
            with ocol3:
                if "total_customer" in o:
                    st.metric("Customer total", f"${o.get('total_customer',0):,.2f}")

            lines = o.get("lines") or []
            if lines:
                with st.expander(f"Line items ({len(lines)})"):
                    for ln in lines:
                        size_str = ", ".join(f"{sz}:{q}" for sz, q in (ln.get("sizes") or {}).items() if q > 0)
                        st.markdown(
                            f"- {ln.get('quantity','?')} x **{ln.get('garment_type','?')}** ({ln.get('base_color','?')}) "
                            f"@ {ln.get('placement','?')} · {size_str} · "
                            f"${ln.get('customer_price_per_pc',0):.2f}/pc = **${ln.get('line_total',0):,.2f}**"
                        )

            if o.get("handoff_text"):
                with st.expander("Handoff sheet"):
                    st.code(o["handoff_text"], language="text")
            else:
                with st.expander("Raw order JSON"):
                    st.json(o)
else:
    st.caption("_No orders saved yet._")
