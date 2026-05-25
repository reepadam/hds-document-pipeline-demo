"""
Artwork & Order Builder module.
Upload artwork → decoration recommendation → Madeira-style production sheet →
multi-line order builder with placement/size/mockup → save to customer history.
"""
import streamlit as st
import json
import uuid
from io import BytesIO
from pathlib import Path
from PIL import Image

from pipeline import (
    process_document,
    build_quote_line,
    get_order_setup_fee,
    svg_to_pil,
    BASE_GARMENT_COST_USD,
    GARMENT_COLORS,
    GARMENT_SIZES,
    GARMENT_PLACEMENTS,
    METHOD_COSTS,
    GARMENT_METHOD_DEFAULTS,
)
from mockup import render_mockup, color_name_to_hex
import customer_repo as repo
from shared import inject_styles, render_page_header, render_antera_handoff, customer_selector, chat_sidebar

st.set_page_config(page_title="Artwork & Order Builder - HDS", page_icon=":art:", layout="wide")
inject_styles()
chat_sidebar()
render_page_header("🎨 Artwork & Order Builder", "Logo → decoration recommendation → production sheet → quote")

# Customer selector (optional - walk-ins allowed)
st.markdown("---")
active_customer = customer_selector(required=False, label="Customer for this artwork")

# This page is artwork-only - always force the artwork pipeline path.
override_value = "logo"

# Quote-settings popover at the top-right of the page content (next to the
# Streamlit 3-dot toolbar). Keeps markup tweak handy without sidebar clutter.
_settings_col1, _settings_col2 = st.columns([5, 1])
with _settings_col2:
    with st.popover("⚙ Quote settings"):
        markup_pct = st.number_input(
            "Markup % over house cost",
            min_value=0.0, max_value=300.0, value=35.0, step=5.0,
            help="Applied to per-piece house cost AND to one-time setup fees to derive customer pricing.",
        )

# File upload or reload from library
st.markdown("---")
uploaded = st.file_uploader("Drop artwork (PDF / JPG / PNG / SVG)", type=["pdf", "jpg", "jpeg", "png", "svg"])

file_bytes = None
filename = None

# Handle reload-from-library click. The reloaded bytes get cached in session
# so subsequent reruns (from number_input edits, etc.) don't lose the file.
reload_logo_id = st.session_state.pop("reload_logo_id", None)
if reload_logo_id and active_customer:
    fb, fn = repo.get_logo_bytes(active_customer["customer_id"], reload_logo_id)
    if fb:
        st.session_state["_active_file_bytes"] = fb
        st.session_state["_active_filename"] = fn
        st.session_state["_active_source"] = "reload"
        file_bytes = fb
        filename = fn
        st.info(f"Reloaded logo from library: `{filename}`")

# If a fresh upload comes in, it replaces any cached reload
if uploaded is not None:
    fb = uploaded.read()
    if fb:
        st.session_state["_active_file_bytes"] = fb
        st.session_state["_active_filename"] = uploaded.name
        st.session_state["_active_source"] = "upload"
        file_bytes = fb
        filename = uploaded.name

# Otherwise fall back to whatever's cached from a previous rerun
if file_bytes is None:
    file_bytes = st.session_state.get("_active_file_bytes")
    filename = st.session_state.get("_active_filename")

# If this came from a fresh upload, persist to customer library (once per upload)
if (file_bytes is not None
        and st.session_state.get("_active_source") == "upload"
        and active_customer
        and not st.session_state.get(f"_saved_{filename}")):
    existing = repo.list_logos(active_customer["customer_id"])
    is_dup = any(e["original_filename"] == filename for e in existing)
    if not is_dup:
        saved = repo.save_logo(active_customer["customer_id"], file_bytes, filename)
        st.success(f"Saved to **{active_customer['display_name']}**'s artwork library.")
        st.session_state["active_logo_id"] = saved["logo_id"]
    else:
        for e in existing:
            if e["original_filename"] == filename:
                st.session_state["active_logo_id"] = e["logo_id"]
                break
    st.session_state[f"_saved_{filename}"] = True

# If we're using a reloaded logo, set active_logo_id from the repo
if (file_bytes is not None
        and st.session_state.get("_active_source") == "reload"
        and active_customer
        and "active_logo_id" not in st.session_state):
    for lg in repo.list_logos(active_customer["customer_id"]):
        if lg["original_filename"] == filename:
            st.session_state["active_logo_id"] = lg["logo_id"]
            break

# Past artwork panel
if active_customer:
    logos = repo.list_logos(active_customer["customer_id"])
    if logos:
        with st.expander(f"📁 Past artwork ({len(logos)}) for {active_customer['display_name']}"):
            cols = st.columns(min(4, max(1, len(logos))))
            for i, lg in enumerate(logos):
                with cols[i % len(cols)]:
                    try:
                        # Reconstruct path cross-platform - ignore stored Windows paths
                        logo_path = repo.get_logo_path(active_customer["customer_id"], lg["logo_id"])
                        if logo_path and logo_path.exists():
                            if lg["ext"] == ".svg":
                                with open(logo_path, "rb") as f:
                                    img = svg_to_pil(f.read())
                            else:
                                img = Image.open(logo_path)
                            img.thumbnail((140, 140))
                            st.image(img, caption=lg["original_filename"])
                        else:
                            st.caption(f"({lg['original_filename']})")
                    except Exception:
                        st.caption(f"({lg['original_filename']})")
                    if st.button("Reload", key=f"reload_{lg['logo_id']}"):
                        st.session_state["reload_logo_id"] = lg["logo_id"]
                        st.rerun()

if file_bytes is None:
    st.info("Upload artwork or reload from the library above to begin.")
    st.stop()

file_ext = Path(filename).suffix.lower()
# Recommendation engine needs a garment for its cost-basis anchor. We silently
# default to "Polo shirt" - the corporate-standard decoration target. The order
# builder below lets you vary garment per line, so this is just the seed for
# the LLM's per-piece materials/labor estimate.
garment = "Polo shirt (cotton-poly blend)"

# Cached pipeline
cache_key = f"{filename}-{len(file_bytes)}-{override_value}-{garment}"
if st.session_state.get("art_cache_key") != cache_key:
    with st.spinner("Processing..."):
        try:
            result = process_document(file_bytes, file_ext, mode_override=override_value, garment=garment)
        except json.JSONDecodeError as e:
            st.error(f"Claude returned non-JSON: {e}")
            st.stop()
        except Exception as e:
            st.error(f"Pipeline error: {type(e).__name__}: {e}")
            st.stop()
    st.session_state["art_cache_key"] = cache_key
    st.session_state["art_result"] = result
    st.session_state["row_ids"] = [uuid.uuid4().hex[:8]]
    st.session_state["quote_locked"] = False
else:
    result = st.session_state["art_result"]

if result["mode"] != "logo":
    st.warning("This upload looks like a document, not artwork. Use the sidebar override to force artwork mode, or open the appropriate document module from the home page.")
    st.stop()

# Two-col: input + analysis
col_left, col_right = st.columns([1, 1])
with col_left:
    st.subheader("Input")
    st.image(result["input_image"], use_container_width=True)
    st.caption(f"`{filename}` - {len(file_bytes):,} bytes")
with col_right:
    st.subheader("Artwork Analysis")
    logo = result["logo_analysis"]
    if logo["dominant_colors"]:
        st.markdown("**Dominant colors:**")
        cols = st.columns(len(logo["dominant_colors"]))
        for col, c in zip(cols, logo["dominant_colors"]):
            with col:
                st.markdown(f'<div style="background:{c["hex"]};height:60px;border-radius:6px;border:1px solid #ccc;"></div>', unsafe_allow_html=True)
                st.caption(f"{c['hex']}\n{c['score']:.1%}")
    if logo["detected_logos"]:
        st.markdown("**Detected brand logos:**")
        st.json(logo["detected_logos"])
    if logo["embedded_text"]:
        st.markdown("**Embedded text:**")
        st.code(logo["embedded_text"])

    recs = result.get("logo_recommendations")
    if recs:
        st.markdown("---")
        st.subheader(f"Decoration recommendation")
        method = recs.get("recommended_decoration_method", "?")
        st.markdown(f"**Method:** `{method}`")
        st.info(recs.get("method_reasoning", ""))
        st.markdown("**Thread / ink:**")
        st.json(recs.get("thread_or_ink_recommendation", {}))
        st.markdown("**Machine settings:**")
        st.json(recs.get("machine_settings", {}))
        st.markdown("**Complexity estimate:**")
        st.json(recs.get("estimated_complexity", {}))
        if recs.get("quality_flags"):
            st.warning("**Quality flags:** " + " - ".join(recs["quality_flags"]))
        if recs.get("next_steps_for_production"):
            st.markdown("**Next steps for production:**")
            for s in recs["next_steps_for_production"]:
                st.markdown(f"- {s}")
        meta = recs.get("_meta", {})
        st.caption(f"Tokens: {meta.get('tokens_in','?')}→{meta.get('tokens_out','?')} - Cost: ~${meta.get('approx_cost_usd','?')}")

# Madeira production sheet
recs = result.get("logo_recommendations") or {}
prod_sheet = recs.get("production_sheet")
if recs.get("recommended_decoration_method") == "embroidery" and prod_sheet:
    st.markdown("---")
    st.subheader("Production Sheet (Madeira / Tajima DG format)")
    render_antera_handoff("In production, this sheet attaches to the Antera production work order alongside the .DST stitch file.")

    info = prod_sheet.get("design_info", {}) or {}
    head1, head2 = st.columns([1, 1])
    with head1:
        st.markdown('<div class="madeira-header">Design Info</div>', unsafe_allow_html=True)
        st_total = info.get('stitch_count_total')
        st_str = f"{st_total:,}" if isinstance(st_total, int) else str(st_total)
        st.markdown(f"""
- **Size (in):** {info.get('size_inches','?')}
- **Stitches:** {st_str}
- **Trims:** {info.get('trims','?')}
- **Color Changes:** {info.get('color_changes','?')}
- **Total Top Thread:** {info.get('total_top_thread_meters','?')} m
- **Total Bobbin:** {info.get('total_bobbin_meters','?')} m
- **Hoop:** {info.get('hoop','?')}
        """)
    with head2:
        st.markdown('<div class="madeira-header">Company Info</div>', unsafe_allow_html=True)
        st.markdown("**HDS Marketing**\n\nX-Deco Production - Bridgeville, PA")

    st.markdown('<div class="madeira-header">Active Colors (Unique Threads)</div>', unsafe_allow_html=True)
    for c in prod_sheet.get("active_colors") or []:
        cols = st.columns([0.5, 3, 1, 1])
        cols[0].markdown(f'<div class="swatch" style="background:{c.get("hex","#ccc")};"></div>', unsafe_allow_html=True)
        cols[1].markdown(f"**{c.get('thread_code','?')} {c.get('thread_name','?')}**  \n_{c.get('brand_line','?')}_")
        s = c.get('stitches')
        cols[2].markdown(f"{s:,} Stitches" if isinstance(s, int) else f"{s} Stitches")
        cols[3].markdown(f"{c.get('thread_meters','?')} m")

    st.markdown('<div class="madeira-header">Color Sequence (Stitching Order)</div>', unsafe_allow_html=True)
    for c in prod_sheet.get("color_sequence") or []:
        cols = st.columns([0.4, 0.5, 3, 1, 1])
        cols[0].markdown(f"**{c.get('seq','?')}**")
        cols[1].markdown(f'<div class="swatch" style="background:{c.get("hex","#ccc")};"></div>', unsafe_allow_html=True)
        cols[2].markdown(f"**{c.get('thread_code','?')} {c.get('thread_name','?')}**  \n_{c.get('brand_line','?')}_")
        s = c.get('stitches')
        cols[3].markdown(f"{s:,} Stitches" if isinstance(s, int) else f"{s} Stitches")
        cols[4].markdown(f"{c.get('thread_meters','?')} m")

# Order builder
if not recs:
    st.stop()

st.markdown("---")
st.subheader("Order Builder")
render_antera_handoff("Generates a customer quote draft + production handoff. Quote pushes to Antera as a sales order; handoff sheet attaches to the work order.")
st.caption("Each line: garment + color + placement + logo size + size qtys. Decoration cost scales with logo area (a 2x1\" wrist hit costs much less than a 12x14\" back hit).")

def get_logo_pil(fb, ext):
    ext = ext.lower().lstrip(".")
    if ext == "svg":
        return svg_to_pil(fb)
    if ext == "pdf":
        return None
    return Image.open(BytesIO(fb))

logo_pil = None
try:
    logo_pil = get_logo_pil(file_bytes, file_ext)
except Exception:
    pass

if "row_ids" not in st.session_state or not st.session_state["row_ids"]:
    st.session_state["row_ids"] = [uuid.uuid4().hex[:8]]

garment_options = list(BASE_GARMENT_COST_USD.keys())

method_options = list(METHOD_COSTS.keys())
method_labels = {k: METHOD_COSTS[k]["label"] for k in method_options}

for idx, row_id in enumerate(list(st.session_state["row_ids"])):
    with st.container(border=True):
        top_cols = st.columns([0.3, 1.7, 1.2, 1.3, 1.5, 0.5])
        with top_cols[0]:
            st.markdown(f"**Line {idx+1}**")
        with top_cols[1]:
            garment_choice = st.selectbox("Garment", garment_options, key=f"gar_{row_id}")
        with top_cols[2]:
            valid_colors = GARMENT_COLORS.get(garment_choice, ["White"])
            color_key = f"col_{row_id}"
            if color_key in st.session_state and st.session_state[color_key] not in valid_colors:
                del st.session_state[color_key]
            # Dropdown for "what the customer ordered" + hex picker for mockup display
            csub1, csub2 = st.columns([3, 1])
            with csub1:
                st.selectbox("Base color", valid_colors, key=color_key)
            with csub2:
                # When dropdown changes, sync hex picker to that color's default
                named_color = st.session_state.get(color_key, valid_colors[0])
                hex_key = f"hex_{row_id}"
                last_named_key = f"_lastnamed_{row_id}"
                if st.session_state.get(last_named_key) != named_color:
                    st.session_state[hex_key] = color_name_to_hex(named_color)
                    st.session_state[last_named_key] = named_color
                st.color_picker("Exact hex", key=hex_key,
                                help="Exact color the garment is ordered in (PMS-match the blank). Auto-fills from the dropdown's named shade; override for brand-critical orders like '#0159a3' for IKEA blue. Flows to mockup, quote PDF, and production handoff.")
        with top_cols[3]:
            valid_placements = list(GARMENT_PLACEMENTS.get(garment_choice, {"Left Chest": (3.5, 3.0)}).keys())
            plc_key = f"plc_{row_id}"
            if plc_key in st.session_state and st.session_state[plc_key] not in valid_placements:
                del st.session_state[plc_key]
            placement_choice = st.selectbox("Placement", valid_placements, key=plc_key)
        with top_cols[4]:
            # Method dropdown - defaults to garment's smart default when garment changes
            method_key = f"mth_{row_id}"
            last_gar_key = f"_lastgar_{row_id}"
            if st.session_state.get(last_gar_key) != garment_choice:
                st.session_state[method_key] = GARMENT_METHOD_DEFAULTS.get(garment_choice, "embroidery")
                st.session_state[last_gar_key] = garment_choice
            method_choice = st.selectbox(
                "Decoration method",
                method_options,
                format_func=lambda k: method_labels[k],
                key=method_key,
            )
        with top_cols[5]:
            st.markdown("&nbsp;")
            if st.button("Remove", key=f"del_{row_id}"):
                st.session_state["row_ids"].remove(row_id)
                for k in list(st.session_state.keys()):
                    if f"_{row_id}" in k:
                        del st.session_state[k]
                st.rerun()

        default_w, default_h = GARMENT_PLACEMENTS.get(garment_choice, {}).get(placement_choice, (3.5, 3.0))

        # Compute logo aspect ratio from the loaded artwork (w/h, >1 = wider)
        logo_aspect = 1.0
        if logo_pil is not None and logo_pil.height > 0:
            logo_aspect = logo_pil.width / logo_pil.height

        # Aspect-lock callbacks: when one dimension changes, recompute the other
        def _on_w_change(rid=row_id, asp=logo_aspect):
            new_w = st.session_state.get(f"w_{rid}") or 0
            if new_w and asp:
                st.session_state[f"h_{rid}"] = round(new_w / asp, 2)

        def _on_h_change(rid=row_id, asp=logo_aspect):
            new_h = st.session_state.get(f"h_{rid}") or 0
            if new_h and asp:
                st.session_state[f"w_{rid}"] = round(new_h * asp, 2)

        w_key = f"w_{row_id}"
        last_plc_key = f"_lastplc_{row_id}"
        # When placement changes, fit logo into placement box preserving aspect ratio
        if st.session_state.get(last_plc_key) != f"{garment_choice}|{placement_choice}":
            target_aspect = default_w / default_h if default_h else 1.0
            if logo_aspect >= target_aspect:
                fit_w = float(default_w)
                fit_h = round(fit_w / logo_aspect, 2) if logo_aspect else float(default_h)
            else:
                fit_h = float(default_h)
                fit_w = round(fit_h * logo_aspect, 2)
            st.session_state[w_key] = fit_w
            st.session_state[f"h_{row_id}"] = fit_h
            st.session_state[f"xoff_{row_id}"] = 0
            st.session_state[f"yoff_{row_id}"] = 0
            st.session_state[last_plc_key] = f"{garment_choice}|{placement_choice}"

        # Row 1: size inputs (aspect-locked)
        sz_cols = st.columns([1, 1, 1, 1, 0.7])
        with sz_cols[0]:
            st.number_input("Logo width (in)", min_value=0.5, max_value=20.0, step=0.25,
                            key=w_key, format="%.2f", on_change=_on_w_change,
                            help="Aspect ratio locked to the uploaded artwork — changing this auto-adjusts height.")
        with sz_cols[1]:
            st.number_input("Logo height (in)", min_value=0.5, max_value=20.0, step=0.25,
                            key=f"h_{row_id}", format="%.2f", on_change=_on_h_change,
                            help="Aspect ratio locked to the uploaded artwork — changing this auto-adjusts width.")
        with sz_cols[2]:
            st.slider("Nudge X (px)", min_value=-200, max_value=200, value=0, step=2,
                      key=f"xoff_{row_id}",
                      help="Move logo left (−) / right (+) on the mockup preview. Affects display only.")
        with sz_cols[3]:
            st.slider("Nudge Y (px)", min_value=-200, max_value=200, value=0, step=2,
                      key=f"yoff_{row_id}",
                      help="Move logo up (−) / down (+) on the mockup preview. Affects display only.")
        with sz_cols[4]:
            st.markdown("&nbsp;")
            if st.button("Reset nudge", key=f"reset_off_{row_id}"):
                st.session_state[f"xoff_{row_id}"] = 0
                st.session_state[f"yoff_{row_id}"] = 0
                st.rerun()

        w_val = st.session_state.get(w_key, default_w)
        h_val = st.session_state.get(f"h_{row_id}", default_h)
        area = (w_val or 0) * (h_val or 0)
        st.markdown(f"<div style='color:#666;font-size:0.82rem;margin-bottom:0.5rem;'>Logo area: <strong>{area:.1f} sq in</strong> &nbsp;|&nbsp; vs. baseline (10 sq in): <strong>{area/10:.2f}x</strong> &nbsp;|&nbsp; aspect locked at <strong>{logo_aspect:.2f}:1</strong></div>", unsafe_allow_html=True)

        sizes_for_garment = GARMENT_SIZES.get(garment_choice, ["One Size"])
        st.markdown("Sizes / quantities:")
        size_cols = st.columns(len(sizes_for_garment))
        row_qty = 0
        for sc, sz in zip(size_cols, sizes_for_garment):
            with sc:
                v = st.number_input(sz, min_value=0, max_value=10000, value=0, step=1, key=f"sz_{row_id}_{sz}")
                row_qty += int(v or 0)

        preview_cols = st.columns([2, 1])
        with preview_cols[0]:
            if row_qty > 0:
                preview = build_quote_line(
                    garment_choice, st.session_state.get(color_key, ""), row_qty, recs,
                    markup_pct=markup_pct, logo_width_in=w_val, logo_height_in=h_val,
                    placement=placement_choice, method=method_choice,
                    base_color_hex=st.session_state.get(f"hex_{row_id}"),
                )
                st.markdown(
                    f'<div class="row-subtotal">'
                    f'<strong>{row_qty} pcs</strong> &middot; '
                    f'Blank ${preview["blank_cost_per_pc"]:.2f} + Materials ${preview["materials_per_pc"]:.2f} + Labor ${preview["labor_per_pc"]:.2f} '
                    f'= House ${preview["house_cost_per_pc"]:.2f}/pc &middot; '
                    f'Line total <strong>${preview["line_total"]:,.2f}</strong> '
                    f'<span style="color:#888;">(setup fee is one-time, shown in summary)</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.caption("_Enter sizes to see line subtotal_")
        with preview_cols[1]:
            if logo_pil is not None:
                aggressive = st.checkbox(
                    "🪄 Aggressive background strip",
                    key=f"aggbg_{row_id}",
                    value=False,
                    help="ON = also strips a secondary uniform color layer (handles logos like IKEA where the brand color is a backplate inside a white border). OFF = safer, only removes the outermost background.",
                )
                try:
                    x_off = int(st.session_state.get(f"xoff_{row_id}", 0) or 0)
                    y_off = int(st.session_state.get(f"yoff_{row_id}", 0) or 0)
                    # Use hex picker value for mockup display; falls back to dropdown name
                    mockup_color = st.session_state.get(f"hex_{row_id}") or st.session_state.get(color_key, "White")
                    mockup_img = render_mockup(
                        garment_choice, mockup_color, logo_pil,
                        placement_choice, w_val, h_val,
                        x_offset_px=x_off, y_offset_px=y_off,
                        aggressive_bg=aggressive,
                    )
                    st.image(mockup_img, caption=f"{placement_choice} - {w_val:.1f}x{h_val:.1f}\"", use_container_width=True)
                except Exception as e:
                    st.caption(f"_Mockup unavailable: {e}_")
            else:
                st.caption("_(Mockup only for image/SVG)_")

if st.button("+ Add line"):
    st.session_state["row_ids"].append(uuid.uuid4().hex[:8])
    st.session_state["quote_locked"] = False
    st.rerun()

# Collect lines
def collect_lines():
    lines = []
    for row_id in st.session_state["row_ids"]:
        garment_type = st.session_state.get(f"gar_{row_id}")
        if not garment_type:
            continue
        color = st.session_state.get(f"col_{row_id}", "")
        placement = st.session_state.get(f"plc_{row_id}")
        method_picked = st.session_state.get(f"mth_{row_id}") or GARMENT_METHOD_DEFAULTS.get(garment_type, "embroidery")
        w_in = st.session_state.get(f"w_{row_id}") or None
        h_in = st.session_state.get(f"h_{row_id}") or None
        sizes_for_garment = GARMENT_SIZES.get(garment_type, ["One Size"])
        size_qtys = {sz: int(st.session_state.get(f"sz_{row_id}_{sz}", 0) or 0) for sz in sizes_for_garment}
        total_qty = sum(size_qtys.values())
        if total_qty <= 0:
            continue
        q = build_quote_line(
            garment_type, color, total_qty, recs,
            markup_pct=markup_pct, logo_width_in=w_in, logo_height_in=h_in,
            placement=placement, method=method_picked,
            base_color_hex=st.session_state.get(f"hex_{row_id}"),
        )
        q["sizes"] = size_qtys
        q["row_id"] = row_id
        lines.append(q)
    return lines

lines = collect_lines()
if lines:
    st.markdown("---")
    st.subheader("Quote Summary")
    col_widths = [1.5, 0.85, 1.2, 1.2, 0.8, 1.4, 0.55, 0.9, 0.9, 0.95, 1.05]
    col_headers = ["Garment", "Color", "Placement", "Method", "Size (in)", "Size breakdown", "Qty",
                   "Decor/pc", "House/pc", "Customer/pc", "Line total"]
    hcols = st.columns(col_widths)
    for c, h in zip(hcols, col_headers):
        c.markdown(f"**{h}**")
    for ln in lines:
        cols = st.columns(col_widths)
        cols[0].markdown(ln["garment_type"])
        # Color cell: name + chip + hex code if a custom hex was picked
        color_hex_disp = ln.get("base_color_hex") or ""
        if color_hex_disp:
            cols[1].markdown(
                f'<span style="display:inline-block;width:10px;height:10px;background:{color_hex_disp};border:1px solid #888;border-radius:2px;vertical-align:middle;margin-right:4px;"></span>'
                f'{ln["base_color"]}<br><span style="font-size:0.75rem;color:#888;">{color_hex_disp}</span>',
                unsafe_allow_html=True,
            )
        else:
            cols[1].markdown(ln["base_color"])
        cols[2].markdown(ln.get("placement") or "—")
        cols[3].markdown(ln.get("method_label", "—"))
        cols[4].markdown(f"{ln.get('logo_width_in') or 0:.1f}x{ln.get('logo_height_in') or 0:.1f}")
        size_str = ", ".join(f"{sz}:{q}" for sz, q in ln["sizes"].items() if q > 0)
        cols[5].markdown(size_str)
        cols[6].markdown(f"{ln['quantity']}")
        cols[7].markdown(f"${ln['decoration_cost_per_pc']:.2f}")
        cols[8].markdown(f"${ln['house_cost_per_pc']:.2f}")
        cols[9].markdown(f"${ln['customer_price_per_pc']:.2f}")
        cols[10].markdown(f"**${ln['line_total']:,.2f}**")

    total_qty = sum(ln["quantity"] for ln in lines)
    lines_house = sum(ln["house_cost_per_pc"] * ln["quantity"] for ln in lines)
    lines_customer = sum(ln["line_total"] for ln in lines)

    # One-time setup fee for the order - summed across unique methods used
    setup = get_order_setup_fee(lines, markup_pct=markup_pct)
    setup_house = setup["setup_house_usd"]
    setup_customer = setup["setup_customer_usd"]

    total_house = lines_house + setup_house
    total_customer = lines_customer + setup_customer
    total_profit = total_customer - total_house

    # Show setup breakdown per method
    st.markdown("**One-time setup fees** _(one per unique method used; covers digitizing, screen burns, etc.)_:")
    for entry in setup["breakdown"]:
        fcols = st.columns([6, 1.1, 1.1, 1.2])
        fcols[0].markdown(f"_{entry['method_label']}_")
        fcols[1].markdown(f"${entry['setup_house']:.2f} house")
        fcols[2].markdown(f"${entry['setup_customer']:.2f} customer")
        fcols[3].markdown(f"**${entry['setup_customer']:.2f}**")

    st.markdown("---")

    # Breakdown table - rows for each cost category, columns for house vs customer
    per_pc_house = total_house / total_qty if total_qty > 0 else 0
    per_pc_customer = total_customer / total_qty if total_qty > 0 else 0

    bcols = st.columns([2.2, 1.4, 1.4])
    bcols[0].markdown("&nbsp;", unsafe_allow_html=True)
    bcols[1].markdown("**House**")
    bcols[2].markdown("**Customer**")

    bcols = st.columns([2.2, 1.4, 1.4])
    bcols[0].markdown("Lines subtotal _(before setup)_")
    bcols[1].markdown(f"${lines_house:,.2f}")
    bcols[2].markdown(f"${lines_customer:,.2f}")

    bcols = st.columns([2.2, 1.4, 1.4])
    bcols[0].markdown("One-time setup fee")
    bcols[1].markdown(f"${setup_house:,.2f}")
    bcols[2].markdown(f"${setup_customer:,.2f}")

    bcols = st.columns([2.2, 1.4, 1.4])
    bcols[0].markdown("**Grand total** _(lines + setup)_")
    bcols[1].markdown(f"**${total_house:,.2f}**")
    bcols[2].markdown(f"**${total_customer:,.2f}**")

    bcols = st.columns([2.2, 1.4, 1.4])
    bcols[0].markdown(f"Per-piece average _(grand total ÷ {total_qty:,} units)_")
    bcols[1].markdown(f"${per_pc_house:.2f}/pc")
    bcols[2].markdown(f"${per_pc_customer:.2f}/pc")

    st.markdown("---")

    tcol1, tcol2, tcol3, tcol4 = st.columns(4)
    tcol1.metric("Total units", f"{total_qty:,}")
    tcol2.metric("Total house cost", f"${total_house:,.2f}", help=f"Lines ${lines_house:,.2f} + Setup ${setup_house:,.2f}")
    tcol3.metric("Customer quote", f"${total_customer:,.2f}", help=f"Lines ${lines_customer:,.2f} + Setup ${setup_customer:,.2f}")
    tcol4.metric(f"Gross margin (@{markup_pct:.0f}%)", f"${total_profit:,.2f}")

    # Generate Quote action lives at the end of the summary - flow goes
    # build lines → review totals → click generate → handoff sheet/PDF appears.
    st.markdown("&nbsp;")
    gen_cols = st.columns([3, 2, 3])
    with gen_cols[1]:
        if st.button("📑 Generate Quote", type="primary", use_container_width=True, key="gen_quote_btn"):
            st.session_state["quote_locked"] = True
            st.rerun()

    if st.session_state.get("quote_locked"):
        st.markdown("---")
        st.subheader("Production Handoff Sheet")
        render_antera_handoff("Copy into Antera sales order notes or attach as the production work order packet.")
        handoff_lines = [
            "HDS MARKETING - PRODUCTION HANDOFF",
            f"Customer: {active_customer['display_name'] if active_customer else '(walk-in)'}"
            + (f"  [Antera: {active_customer.get('antera_customer_id') or '?'}]" if active_customer else ""),
            f"Artwork file: {filename}",
            f"Decoration method: {recs.get('recommended_decoration_method','?')}",
            f"Thread/ink: {recs.get('thread_or_ink_recommendation',{}).get('brand_product','?')}",
            "",
            "LINE ITEMS:",
        ]
        for ln in lines:
            size_str = ", ".join(f"{sz}={q}" for sz, q in ln["sizes"].items() if q > 0)
            color_str = ln['base_color']
            if ln.get('base_color_hex'):
                color_str = f"{ln['base_color']} {ln['base_color_hex']}"
            handoff_lines.append(
                f"  - {ln['quantity']} x {ln['garment_type']} ({color_str}) "
                f"[{ln.get('method_label','?')}] @ {ln.get('placement','?')} {ln.get('logo_width_in',0):.1f}x{ln.get('logo_height_in',0):.1f}\" "
                f"[{size_str}] @ ${ln['customer_price_per_pc']:.2f}/pc = ${ln['line_total']:,.2f}"
            )
        handoff_lines += [
            "",
            "ONE-TIME SETUP FEES (per unique method):",
        ]
        for entry in setup["breakdown"]:
            handoff_lines.append(f"  - {entry['method_label']}: ${entry['setup_customer']:.2f}")
        handoff_lines += [
            "",
            f"TOTAL UNITS: {total_qty}",
            f"LINES SUBTOTAL: ${lines_customer:,.2f}",
            f"ONE-TIME SETUP: ${setup_customer:,.2f}",
            f"CUSTOMER QUOTE (grand total): ${total_customer:,.2f}",
            f"HOUSE COST (incl. setup): ${total_house:,.2f}",
            f"GROSS MARGIN: ${total_profit:,.2f} ({markup_pct:.0f}% markup)",
            "",
            "PRODUCTION NOTES:",
        ]
        for s in (recs.get("next_steps_for_production") or []):
            handoff_lines.append(f"  - {s}")
        handoff_text = "\n".join(handoff_lines)
        st.code(handoff_text, language="text")

        # Generate the customer-facing PDF quote (no house costs, no markup shown)
        from quote_pdf import build_quote_pdf
        from datetime import datetime
        quote_number = f"HDS-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        try:
            pdf_bytes = build_quote_pdf(
                customer_name=active_customer["display_name"] if active_customer else "(Walk-in customer)",
                antera_customer_id=active_customer.get("antera_customer_id") if active_customer else None,
                quote_number=quote_number,
                lines=lines,
                setup_breakdown=setup.get("breakdown", []),
                lines_customer_total=lines_customer,
                setup_customer_total=setup_customer,
                grand_total=total_customer,
                artwork_filename=filename,
                valid_days=30,
            )
        except Exception as e:
            pdf_bytes = None
            st.warning(f"PDF generation failed: {e}")

        save_cols = st.columns([1, 1, 1])
        with save_cols[0]:
            st.download_button("📄 Internal handoff (.txt)", data=handoff_text,
                file_name=f"handoff_{Path(filename).stem}.txt", mime="text/plain",
                help="Internal-only - shows house costs + markup. For production floor.")
        with save_cols[1]:
            if pdf_bytes:
                st.download_button(
                    "📑 Customer Quote (PDF, HDS-branded)",
                    data=pdf_bytes,
                    file_name=f"HDS_Quote_{quote_number}.pdf",
                    mime="application/pdf",
                    help="Customer-facing only - markup baked into prices, no internal costs shown.",
                    type="primary",
                )
        with save_cols[2]:
            if active_customer and st.session_state.get("active_logo_id"):
                if st.button("Save order to customer history"):
                    order_data = {
                        "filename": filename, "method": recs.get("recommended_decoration_method"),
                        "lines": lines, "total_units": total_qty,
                        "total_house": round(total_house, 2), "total_customer": round(total_customer, 2),
                        "total_profit": round(total_profit, 2), "markup_pct": markup_pct,
                        "handoff_text": handoff_text,
                    }
                    saved_order = repo.save_order(active_customer["customer_id"],
                        st.session_state["active_logo_id"], order_data)
                    st.success(f"Saved order `{saved_order['order_id']}`.")
            else:
                st.caption("_(Select a customer to save orders)_")
else:
    st.info("Enter at least one size quantity above to build a quote.")