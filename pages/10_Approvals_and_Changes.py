"""
Approvals & Change Management module.

Kanban-style view of every accepted order grouped by approval stage.
Sports/licensed customers route through 3-party approval (team + league +
sponsor). Corporate customers route through 2-stage internal review.

Each card is clickable - expand to see full order detail, line items, and
audit log. "Request Change" opens an inline form that creates a numbered
change order (-C001, -C002, ...) and supersedes the original.
"""
import streamlit as st
from collections import defaultdict
from datetime import datetime

import customer_repo as repo
from shared import inject_styles, render_page_header, render_antera_handoff, chat_sidebar

st.set_page_config(page_title="Approvals & Changes - HDS", page_icon=":clipboard:", layout="wide")
inject_styles()
render_page_header("📋 Approvals & Change Management", "Order routing, sign-offs, and change orders in one view.")
render_antera_handoff(
    "Sports/licensed orders route through team → league/properties → sponsor sign-off (NFL Properties, MLB, NBA, NHL). "
    "Corporate orders route through customer → production-mgr. Each Accept advances the order and appends an audit log. "
    "Request Change creates a numbered change order (ORDER-XYZ-C001) that becomes the new system-of-record; original is marked superseded. "
    "When fully approved, the production work order locks and the floor is notified."
)

st.markdown("---")

# ---- Load + filter ----
all_orders = repo.list_all_orders_with_stage()
total_orders = len(all_orders)

fcols = st.columns([1.2, 1.5, 1, 2])
with fcols[0]:
    category_filter = st.selectbox("Category", ["All", "Sports / Licensed", "Corporate"], index=0)
with fcols[1]:
    customer_names = sorted({o["_customer"]["display_name"] for o in all_orders})
    customer_filter = st.selectbox("Customer", ["All customers"] + customer_names)
with fcols[2]:
    show_superseded = st.checkbox("Show superseded", value=False,
                                   help="Show original orders that have been replaced by a change order. Off by default to keep the board clean.")
with fcols[3]:
    st.markdown(f"<div style='padding-top:1.8rem;color:#666;'>Total orders: <strong>{total_orders}</strong></div>", unsafe_allow_html=True)

def keep(o):
    cat = repo.get_customer_category(o["_customer"])
    if category_filter == "Sports / Licensed" and cat != "sports":
        return False
    if category_filter == "Corporate" and cat != "corporate":
        return False
    if customer_filter != "All customers" and o["_customer"]["display_name"] != customer_filter:
        return False
    if not show_superseded and o.get("approval_stage") == "superseded":
        return False
    return True

filtered = [o for o in all_orders if keep(o)]

by_stage = defaultdict(list)
for o in filtered:
    by_stage[o.get("approval_stage", "draft")].append(o)

st.markdown("---")
sport_stages_used = [s for s in repo.SPORTS_STAGES if by_stage.get(s)]
corp_stages_used = [s for s in repo.CORPORATE_STAGES if by_stage.get(s)]
all_stages_present = list(dict.fromkeys(sport_stages_used + corp_stages_used + ["rejected", "superseded"]))
all_stages_present = [s for s in all_stages_present if by_stage.get(s)]

# Top metric tiles
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

st.markdown("---")


def render_card(o):
    """Render one order card with click-to-expand details + advance/change actions."""
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
    is_change_order = o.get("is_change_order", False)
    change_from = o.get("change_from")
    superseded_by = o.get("superseded_by")

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
            badges = [cat_badge]
            if is_change_order:
                badges.append("🔁 Change Order")
            if superseded_by:
                badges.append(f"🚫 Superseded → `{superseded_by}`")
            badge_str = " &nbsp;·&nbsp; ".join(f"<span style='font-size:0.7rem;color:#888;'>{b}</span>" for b in badges)
            st.markdown(f"**{cust_name}** &nbsp;{badge_str}", unsafe_allow_html=True)
            origin_note = f" &nbsp;·&nbsp; from `{change_from}`" if change_from else ""
            st.caption(f"`{order_id}`{origin_note} · {units:,} units · _{method}_")
        with hcols[1]:
            st.markdown(f"<div style='text-align:right;'><strong>${total:,.2f}</strong><br><span style='font-size:0.75rem;color:#888;'>{days_in_stage} day{'s' if days_in_stage != 1 else ''} in stage</span></div>", unsafe_allow_html=True)

        # ---- Order Details expander (line items, totals, lineage)
        cid = cust["customer_id"]
        with st.expander("📋 Order details — line items, lineage, audit"):
            lines = o.get("lines") or []
            if lines:
                st.markdown("**Line items:**")
                for ln in lines:
                    size_str = ", ".join(f"{sz}:{q}" for sz, q in (ln.get("sizes") or {}).items() if q > 0)
                    color = ln.get("base_color", "—")
                    if ln.get("base_color_hex"):
                        color += f" `{ln['base_color_hex']}`"
                    st.markdown(
                        f"- **{ln.get('quantity','?'):,} x {ln.get('garment_type','?')}** "
                        f"({color}) · {ln.get('method_label','?')} @ {ln.get('placement','?')} · "
                        f"{ln.get('logo_width_in',0):.1f}×{ln.get('logo_height_in',0):.1f}\" · "
                        f"[{size_str}] · **${ln.get('line_total',0):,.2f}**"
                    )

            # Change order specifics
            if is_change_order:
                st.markdown("---")
                st.markdown("**Change order details:**")
                st.info(f"**Reason:** {o.get('change_reason', '—')}")
                if o.get("change_details"):
                    st.markdown(f"**What changed:**\n{o['change_details']}")
                st.caption(f"Originated from order: `{change_from}`")

            # Lineage chain
            if change_from or superseded_by:
                st.markdown("---")
                st.markdown("**Lineage:**")
                chain = []
                # walk back through change_from
                cur = o
                while cur.get("change_from"):
                    parent = repo.get_order(cid, cur["change_from"])
                    if not parent:
                        break
                    chain.insert(0, parent)
                    cur = parent
                chain.append(o)
                # walk forward through superseded_by
                cur = o
                while cur.get("superseded_by"):
                    child = repo.get_order(cid, cur["superseded_by"])
                    if not child:
                        break
                    chain.append(child)
                    cur = child
                for i, link in enumerate(chain):
                    is_current = link.get("order_id") == order_id
                    marker = "👉 " if is_current else "    "
                    st.markdown(f"{marker}`{link.get('order_id','?')}` — {repo.STAGE_LABELS.get(link.get('approval_stage',''), link.get('approval_stage',''))}")

            # Audit log
            log = o.get("approval_log", [])
            if log:
                st.markdown("---")
                st.markdown(f"**Audit log ({len(log)} events):**")
                for entry in log:
                    when = entry.get("at", "")[:16]
                    st.markdown(f"- `{when}` · **{entry.get('action','?')}** by {entry.get('actor','?')} → {entry.get('to_stage', '—')} · _{entry.get('notes','')}_")

        # ---- Action buttons (terminal states have none)
        if stage in ("completed", "superseded"):
            return

        key_base = f"{cid}_{order_id}"
        change_open_key = f"_change_open_{key_base}"
        acols = st.columns([1, 1.3, 3])
        with acols[0]:
            advance_label = "✅ Approve →" if stage != "rejected" else "🔄 Revive draft"
            if st.button(advance_label, key=f"adv_{key_base}", use_container_width=True):
                if stage == "rejected":
                    repo.advance_order_stage(cid, order_id, actor="Adam Reep (demo)",
                                             notes="Revived after change request.", to_stage="draft")
                else:
                    repo.advance_order_stage(cid, order_id, actor="Adam Reep (demo)",
                                             notes=f"Advanced from {repo.STAGE_LABELS.get(stage, stage)}.")
                st.rerun()
        with acols[1]:
            if st.button("⚠️ Request Change", key=f"req_{key_base}", use_container_width=True):
                st.session_state[change_open_key] = True
                st.rerun()

        # ---- Change order form (inline, when toggled)
        if st.session_state.get(change_open_key):
            with st.form(f"change_form_{key_base}"):
                st.markdown("**Create change order**")
                reason = st.text_input("Change reason (short)",
                                       placeholder="e.g. Customer requested color change Navy → Royal",
                                       key=f"chg_reason_{key_base}")
                details = st.text_area("What changed (specifics for production)",
                                       placeholder="e.g. Line 1: T-shirt color was Navy #1a3a5c, now Royal Blue #2346a5. Sizes unchanged.",
                                       key=f"chg_details_{key_base}")
                fcols = st.columns([1, 1, 3])
                with fcols[0]:
                    submitted = st.form_submit_button("Create change order", type="primary")
                with fcols[1]:
                    cancelled = st.form_submit_button("Cancel")
                if submitted:
                    if not reason.strip():
                        st.error("Please enter a change reason.")
                    else:
                        new_co = repo.create_change_order(cid, order_id, reason.strip(),
                                                          details.strip() or "(no specifics provided)",
                                                          actor="Adam Reep (demo)")
                        if new_co:
                            st.session_state[change_open_key] = False
                            st.success(f"Created change order `{new_co['order_id']}` — original superseded.")
                            st.rerun()
                if cancelled:
                    st.session_state[change_open_key] = False
                    st.rerun()


# Render each stage section
for stage in all_stages_present:
    cards = by_stage.get(stage, [])
    if not cards:
        continue
    st.markdown(f"### {repo.STAGE_ICONS.get(stage, '')} {repo.STAGE_LABELS.get(stage, stage)} ({len(cards)})")
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
