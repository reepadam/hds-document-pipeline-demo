"""
Customer Orders module - browse-only view of accepted orders per customer.
No upload here (intake happens via Artwork module or future email intake).
"""
import streamlit as st
import customer_repo as repo
from shared import inject_styles, render_page_header, render_antera_handoff, chat_sidebar

st.set_page_config(page_title="Customer Orders - HDS", page_icon=":shopping_cart:", layout="wide")
inject_styles()
render_page_header("🛒 Customer Orders", "Active orders per customer, with job context.")
render_antera_handoff(
    "Read-only view of accepted/in-flight customer orders. Mirrors what sales-order module shows, "
    "with the artwork + decoration spec context attached. Order intake itself happens via the Artwork & "
    "Order Builder module (or future Email Intake)."
)

st.markdown("---")
customers = repo.list_customers()
if not customers:
    st.info("No customers in the repo yet. Run `python seed_demo_data.py` to preload HDS-relevant customers + jobs.")
    st.stop()

# Sort customers by display name, group by "active orders" presence
labels = [f"{c['display_name']} [{c['customer_id'][:8]}]" for c in customers]
selected = st.selectbox("Customer:", labels)
short_id = selected.split("[")[-1].rstrip("]")
customer = next((c for c in customers if c["customer_id"].startswith(short_id)), None)
if not customer:
    st.stop()

st.markdown(f"### {customer['display_name']}")
st.caption(f"ID: `{customer.get('antera_customer_id') or '—'}` · {customer.get('notes') or ''}")

orders = repo.list_orders(customer["customer_id"])
jobs = repo.list_antera_jobs(customer["customer_id"])

mcols = st.columns(3)
mcols[0].metric("Active jobs", len(jobs))
mcols[1].metric("Accepted orders", len(orders))
total_units = sum(o.get("total_units", 0) for o in orders) if orders else 0
mcols[2].metric("Total units (across orders)", f"{total_units:,}")

# Active jobs section
st.markdown("---")
st.subheader("Active Jobs")
if jobs:
    for job in jobs:
        with st.container(border=True):
            cols = st.columns([2, 4, 1])
            cols[0].markdown(f"**`{job['job_id']}`**")
            cols[1].markdown(job['description'])
            cols[2].markdown(f"_{job['status']}_")
            # Count orders + expenses against this job
            job_orders = [o for o in orders if o.get("job_number") == job["job_id"]]
            expenses_for_job = repo.list_expenses(customer["customer_id"], job_number=job["job_id"])
            if job_orders or expenses_for_job:
                with st.expander(f"Activity: {len(job_orders)} orders · {len(expenses_for_job)} expenses"):
                    for o in job_orders:
                        st.markdown(f"- Order `{o['order_id']}` · {o.get('total_units','?')} units · ${o.get('total_customer',0):,.2f}")
                    for e in expenses_for_job:
                        st.markdown(f"- Expense `{e.get('expense_id','?')}` · {e.get('merchant_name','?')} · ${e.get('total','—')}")
else:
    st.caption("_No mocked jobs for this customer. Run seed script or add via API in production._")

# Order history section
st.markdown("---")
st.subheader("Accepted Orders")
if orders:
    for o in orders:
        with st.container(border=True):
            ocols = st.columns([1.5, 2, 1, 1, 1])
            ocols[0].markdown(f"**`{o['order_id']}`**")
            ocols[1].markdown(f"{o.get('filename','—')}")
            ocols[2].markdown(f"_{o.get('method','—')}_")
            ocols[3].markdown(f"**{o.get('total_units',0):,} units**")
            ocols[4].markdown(f"**${o.get('total_customer',0):,.2f}**")
            if o.get("created_at"):
                st.caption(f"Created: {o['created_at'][:16]}")
            lines = o.get("lines") or []
            if lines:
                with st.expander(f"Line items ({len(lines)})"):
                    for ln in lines:
                        size_str = ", ".join(f"{sz}:{q}" for sz, q in (ln.get("sizes") or {}).items() if q > 0)
                        st.markdown(
                            f"- {ln.get('quantity','?')} x **{ln.get('garment_type','?')}** ({ln.get('base_color','?')}) "
                            f"[{ln.get('method_label','?')}] @ {ln.get('placement','?')} · {size_str} · "
                            f"**${ln.get('line_total',0):,.2f}**"
                        )
else:
    st.info(f"No orders saved for {customer['display_name']} yet. Use the **Artwork & Order Builder** module to create one.")
