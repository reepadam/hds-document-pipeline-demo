"""
Reporting module - drills into accepted queues (receipts, invoices, spec sheets, etc.)
with dropdowns/filters. JSON-backed for the demo; in production this view sits over
Antera + the Sheets review buffer.
"""
import streamlit as st
from collections import defaultdict
import customer_repo as repo
from pipeline import fmt_money
from shared import inject_styles, render_page_header, render_antera_handoff, chat_sidebar

st.set_page_config(page_title="Reporting - HDS", page_icon=":bar_chart:", layout="wide")
inject_styles()
chat_sidebar()
render_page_header("📊 Reporting", "Drill into accepted queues. Information flow you can see.")
render_antera_handoff(
    "Demo skinny: queues are JSON files locally. In production each queue pushes to Antera "
    "(AP, Job Costing, Item Master) and/or a Sheets review buffer. The reporting view here "
    "is the same shape regardless of backend."
)

# Queue selector
queues = list(repo.queue_counts().items())
queue_labels = {
    "receipts": "💳 Receipts / Expenses",
    "invoices": "🧾 Bills & Invoices",
    "spec_sheets": "📋 Spec Sheets",
    "orders": "🛒 Customer Orders",
    "notes": "✍️ Forms & Notes",
}

# Top metrics - one card per queue showing count
st.markdown("---")
mcols = st.columns(len(queues))
for col, (qname, count) in zip(mcols, queues):
    col.metric(queue_labels.get(qname, qname), f"{count}")

st.markdown("---")

# Pick which queue to drill into
qpick = st.selectbox(
    "Drill into queue:",
    [q[0] for q in queues],
    format_func=lambda q: queue_labels.get(q, q),
)

entries = repo.list_queue(qpick)
if not entries:
    st.info(f"No entries in the **{queue_labels.get(qpick, qpick)}** queue yet. "
            f"Use the relevant module's Accept button to push entries here.")
    st.stop()

# Filters
st.markdown("### Filters")
fcols = st.columns(4)

# Build filter options dynamically from entry data
customer_names = sorted({e.get("customer_name") for e in entries if e.get("customer_name")})
all_customers = ["(all customers)"] + customer_names
sel_customer = fcols[0].selectbox("Customer", all_customers)

# Job filter (only meaningful for receipts)
if qpick == "receipts":
    job_numbers = sorted({e.get("job_number") for e in entries if e.get("job_number")})
    all_jobs = ["(all jobs)"] + job_numbers
    sel_job = fcols[1].selectbox("Antera Job", all_jobs)
else:
    sel_job = "(all jobs)"

# Category filter (only meaningful for receipts)
if qpick == "receipts":
    cats = sorted({e.get("category") for e in entries if e.get("category")})
    all_cats = ["(all categories)"] + cats
    sel_cat = fcols[2].selectbox("Category", all_cats)
else:
    sel_cat = "(all categories)"

# Date range filter (text-based for simplicity)
dates = sorted({e.get("date") or e.get("accepted_at", "")[:10] for e in entries if e.get("date") or e.get("accepted_at")})
all_dates = ["(all dates)"] + dates
sel_date = fcols[3].selectbox("Date", all_dates)

# Apply filters
def matches(e):
    if sel_customer != "(all customers)" and e.get("customer_name") != sel_customer:
        return False
    if sel_job != "(all jobs)" and e.get("job_number") != sel_job:
        return False
    if sel_cat != "(all categories)" and e.get("category") != sel_cat:
        return False
    if sel_date != "(all dates)":
        d = e.get("date") or e.get("accepted_at", "")[:10]
        if d != sel_date:
            return False
    return True

filtered = [e for e in entries if matches(e)]
st.caption(f"Showing {len(filtered)} of {len(entries)} entries.")

# Summary stats
if qpick == "receipts":
    total = 0.0
    for e in filtered:
        try:
            total += float(str(e.get("total", "0")).replace("$", "").replace(",", "") or 0)
        except ValueError:
            pass
    by_cat = defaultdict(float)
    for e in filtered:
        try:
            by_cat[e.get("category", "other")] += float(str(e.get("total", "0")).replace("$", "").replace(",", "") or 0)
        except ValueError:
            pass

    st.markdown("### Summary")
    scols = st.columns(2)
    with scols[0]:
        st.metric("Total filtered receipts", f"{len(filtered)}")
        st.metric("Total expense amount", f"${total:,.2f}")
    with scols[1]:
        st.markdown("**Breakdown by category:**")
        if by_cat:
            for cat, amt in sorted(by_cat.items(), key=lambda x: -x[1]):
                st.markdown(f"- _{cat.replace('_', ' ')}_: **${amt:,.2f}**")

# Entry table
st.markdown("---")
st.markdown("### Entries")

if qpick == "receipts":
    hcols = st.columns([1.6, 1.2, 1.6, 1.4, 1.0, 1.0, 1.5])
    for c, h in zip(hcols, ["Customer", "Date", "Merchant", "Job", "Category", "Total", "Notes"]):
        c.markdown(f"**{h}**")
    for e in filtered:
        cols = st.columns([1.6, 1.2, 1.6, 1.4, 1.0, 1.0, 1.5])
        cols[0].markdown(e.get("customer_name", "—"))
        cols[1].markdown(e.get("date", "—"))
        cols[2].markdown(e.get("merchant_name", "—"))
        cols[3].markdown(f"`{e.get('job_number','—')}`")
        cols[4].markdown(f"_{e.get('category','—').replace('_',' ')}_")
        cols[5].markdown(f"**{fmt_money(e.get('total'))}**")
        cols[6].caption(e.get("notes") or "")
elif qpick == "orders":
    hcols = st.columns([1.6, 1.5, 1.2, 0.7, 1.1, 1.3])
    for c, h in zip(hcols, ["Customer", "Order ID", "Method", "Units", "Total", "Accepted"]):
        c.markdown(f"**{h}**")
    for e in filtered:
        cols = st.columns([1.6, 1.5, 1.2, 0.7, 1.1, 1.3])
        cols[0].markdown(e.get("customer_name", "—"))
        cols[1].markdown(f"`{e.get('order_id','—')}`")
        cols[2].markdown(f"_{e.get('method','—')}_")
        cols[3].markdown(f"{e.get('total_units',0):,}")
        cols[4].markdown(f"**${e.get('total_customer',0):,.2f}**")
        cols[5].caption(e.get("accepted_at","")[:16])

    # Summary metrics for orders
    if filtered:
        total_units = sum(int(e.get("total_units", 0) or 0) for e in filtered)
        total_revenue = sum(float(e.get("total_customer", 0) or 0) for e in filtered)
        total_margin = sum(float(e.get("total_profit", 0) or 0) for e in filtered)
        st.markdown("---")
        scols = st.columns(3)
        scols[0].metric("Total units (filtered)", f"{total_units:,}")
        scols[1].metric("Total customer revenue", f"${total_revenue:,.2f}")
        scols[2].metric("Total gross margin", f"${total_margin:,.2f}")
else:
    # Generic table for other queues (spec_sheets, notes — phase 2)
    for e in filtered:
        with st.container(border=True):
            st.markdown(f"**`{e.get('entry_id','?')}`** · {e.get('accepted_at','')[:16]}")
            st.json(e)