"""
Approvals & Change Management module.

Kanban-style view of every accepted order grouped by approval stage.
Sports/licensed customers route through 3-party approval (team + league +
sponsor). Corporate customers route through 2-stage internal review.

Cards advance via Approve / Request Change buttons. Full audit log per order.
"""
import streamlit as st
from collections import defaultdict
from datetime import datetime

import customer_repo as repo
from shared import inject_styles, render_page_header, render_antera_handoff, chat_sidebar

st.set_page_config(page_title="Approvals & Changes - HDS", page_icon=":clipboard:", layout="wide")
inject_styles()
chat_sidebar()
render_page_header("📋 Approvals & Change Management", "Order routing, sign-offs, and change requests in one view.")
render_antera_handoff(
    "Sports/licensed orders route through team → league → sponsor sign-off (NFL Properties, MLB, NBA, NHL). "
    "Corporate orders route through customer → production-mgr sign-off. Each Accept advances the order and "
    "appends an audit log entry. When an order reaches Approved, the Antera production work order is locked "
    "and the floor is notified. Replaces email-thread approvals where status hides in someone's inbox."
)

st.markdown("---")

# ---- Load + filter ----
all_orders = repo.list_all_orders_with_stage()
total_orders = len(all_orders)

fcols = st.columns([1, 1, 3])
with fcols[0]:
    category_filter = st.selectbox("Category", ["All", "Sports / Licensed", "Corporate"], index=0)
with fcols[1]:
    # Customer filter
    customer_names = sorted({o["_customer"]["display_name"] for o in all_orders})
    customer_filter = st.selectbox("Customer", ["All customers"] + customer_names)
with fcols[2]:
    st.markdown(f"<div style='padding-top:1.8rem;color:#666;'>Total orders: <strong>{total_orders}</strong></div>", unsafe_allow_html=True)

def keep(o):
    cat = repo.get_customer_category(o["_customer"])
    if category_filter == "Sports / Licensed" and cat != "sports":
        return False
    if category_filter == "Corporate" and cat != "corporate":
        return False
    if customer_filter != "All customers" and o["_customer"]["display_name"] != customer_filter:
        return False
    return True

filtered = [o for o in all_orders if keep(o)]

# Group by stage
by_stage = defaultdict(list)
for o in filtered:
    by_stage[o.get("approval_stage", "draft")].append(o)

# ---- Stage summary ----
st.markdown("---")
sport_stages_used = [s for s in repo.SPORTS_STAGES if by_stage.get(s)]
corp_stages_used = [s for s in repo.CORPORATE_STAGES if by_stage.get(s)]
all_stages_present = list(dict.fromkeys(sport_stages_used + corp_stages_used + ["rejected"]))
all_stages_present = [s for s in all_stages_present if by_stage.get(s)]

# Top metrics — one tile per stage
if all_stages_present:
    mcols = st.columns(len(all_stages_present))
    for col, stage in zip(mcols, all_stages_present):
        cards = by_stage.get(stage, [])
        total_value = sum(float(c.get("total_customer", 0) or 0) for c in cards)
        col.metric(
            f"{repo.STAGE_ICONS.get(stage, '')} {repo.STAGE_LABELS.get(stage, stage)}",
            f"{len(cards)}",
            f"${total_value:,.0f}" if total_value else None,
        )

# ---- Render cards grouped by stage ----
st.markdown("---")

def render_card(o):
    cust = o["_customer"]
    cust_name = cust["display_name"]
    category = repo.get_customer_category(cust)
    cat_badge = "🏟️ Sports" if category == "sports" else "🏢 Corporate"
    order_id = o.get("order_id", "?")
    total = float(o.get("total_customer", 0) or 0)
    units = int(o.get("total_units", 0) or 0)
    method = o.get("method", "—")
    stage = o.get("approval_stage", "draft")
    stage_changed = o.get("stage_changed_at", o.get("created_at", ""))

    # Days in current stage
    days_in_stage = "?"
    try:
        if stage_changed:
            dt = datetime.fromisoformat(stage_changed.replace("Z", ""))
            days_in_stage = (datetime.utcnow() - dt).days
    except (ValueError, TypeError):
        pass

    with st.container(border=True):
        hcols = st.columns([2.5, 1.5])
        with hcols[0]:
            st.markdown(f"**{cust_name}** &nbsp;<span style='font-size:0.7rem;color:#888;'>{cat_badge}</span>", unsafe_allow_html=True)
            st.caption(f"`{order_id}` · {units:,} units · _{method}_")
        with hcols[1]:
            st.markdown(f"<div style='text-align:right;'><strong>${total:,.2f}</strong><br><span style='font-size:0.75rem;color:#888;'>{days_in_stage} day{'s' if days_in_stage != 1 else ''} in stage</span></div>", unsafe_allow_html=True)

        # Action buttons (no buttons for terminal states)
        if stage not in ("completed",):
            acols = st.columns([1, 1, 3])
            cid = cust["customer_id"]
            key_base = f"{cid}_{order_id}"
            with acols[0]:
                advance_label = "✅ Approve →" if stage != "rejected" else "🔄 Revive"
                if st.button(advance_label, key=f"adv_{key_base}", use_container_width=True):
                    if stage == "rejected":
                        repo.advance_order_stage(cid, order_id, actor="Adam Reep (demo)",
                                                 notes="Re-submitted after change request.", to_stage="draft")
                    else:
                        repo.advance_order_stage(cid, order_id, actor="Adam Reep (demo)",
                                                 notes=f"Advanced from {repo.STAGE_LABELS.get(stage, stage)}.")
                    st.rerun()
            with acols[1]:
                if stage not in ("rejected",):
                    if st.button("⚠️ Request Change", key=f"rej_{key_base}", use_container_width=True):
                        repo.reject_order(cid, order_id, actor="Adam Reep (demo)",
                                          notes=f"Change requested from {repo.STAGE_LABELS.get(stage, stage)}.")
                        st.rerun()

        # Latest log entry
        log = o.get("approval_log", [])
        if log:
            last = log[-1]
            st.caption(f"_Last action: {last.get('action','?')} by {last.get('actor','?')} — {last.get('notes', '')}_")

        # Full log in expander
        if len(log) > 1:
            with st.expander(f"Audit log ({len(log)} events)"):
                for entry in log:
                    when = entry.get("at", "")[:16]
                    st.markdown(f"- `{when}` · **{entry.get('action','?')}** by {entry.get('actor','?')} → {entry.get('to_stage', '—')} · _{entry.get('notes','')}_")


# Render each stage section
for stage in all_stages_present:
    cards = by_stage.get(stage, [])
    if not cards:
        continue
    st.markdown(f"### {repo.STAGE_ICONS.get(stage, '')} {repo.STAGE_LABELS.get(stage, stage)} ({len(cards)})")
    # Limit to top 6 per stage to avoid scrolling forever; show all in expander
    visible = cards[:6]
    for o in visible:
        render_card(o)
    if len(cards) > 6:
        with st.expander(f"Show {len(cards) - 6} more in {repo.STAGE_LABELS.get(stage, stage)}"):
            for o in cards[6:]:
                render_card(o)
    st.markdown("&nbsp;")

if not filtered:
    st.info("No orders match the current filter.")
