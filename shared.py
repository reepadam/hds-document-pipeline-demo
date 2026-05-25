"""
Shared helpers used by every page: styling, customer selector, common widgets.
"""
import zipfile
from io import BytesIO
from pathlib import Path
import streamlit as st
import customer_repo as repo


def expand_uploads(uploaded_files, allowed_exts=None):
    """Walk uploaded files. Expand any zip in-memory.

    Returns list of (display_name, bytes, ext) tuples.
    allowed_exts: optional list like [".pdf", ".jpg"] to filter zip contents.
    """
    out = []
    for f in uploaded_files:
        name = f.name
        ext = Path(name).suffix.lower()
        data = f.read()
        if ext == ".zip":
            try:
                with zipfile.ZipFile(BytesIO(data)) as zf:
                    for member in zf.namelist():
                        if member.endswith("/") or "__MACOSX" in member or Path(member).name.startswith("._"):
                            continue
                        m_ext = Path(member).suffix.lower()
                        if allowed_exts and m_ext not in allowed_exts:
                            continue
                        inner_bytes = zf.read(member)
                        if not inner_bytes:
                            continue
                        out.append((f"{name}::{Path(member).name}", inner_bytes, m_ext))
            except zipfile.BadZipFile:
                st.error(f"`{name}` is not a valid zip file - skipping.")
        else:
            out.append((name, data, ext))
    return out


def inject_styles():
    """Inject HDS-inspired CSS. Call at top of every page."""
    st.markdown(
        """
        <style>
        :root {
          --hds-navy: #1a3a5c;
          --hds-coral: #e8743b;
          --hds-warm-bg: #fafaf6;
        }
        .main { background-color: var(--hds-warm-bg); }
        h1, h2, h3 { color: var(--hds-navy) !important; }
        .stButton > button {
          background-color: var(--hds-navy);
          color: white;
          border: none;
        }
        .stButton > button:hover {
          background-color: var(--hds-coral);
          color: white;
        }
        .hds-tagline {
          color: var(--hds-coral);
          font-style: italic;
          font-weight: 600;
          margin-top: -0.5rem;
          margin-bottom: 1rem;
        }
        .hds-badge {
          display: inline-block;
          background: var(--hds-navy);
          color: white;
          padding: 0.15rem 0.6rem;
          border-radius: 12px;
          font-size: 0.75rem;
          font-weight: 600;
          letter-spacing: 0.04em;
        }
        .antera-handoff {
          background: #fff5ee;
          border-left: 3px solid var(--hds-coral);
          padding: 0.4rem 0.7rem;
          font-size: 0.8rem;
          border-radius: 4px;
          margin: 0.4rem 0;
        }
        .auto-flag {
          background: #eef5ee;
          border-left: 3px solid #4a8d4a;
          padding: 0.4rem 0.8rem;
          border-radius: 4px;
          font-size: 0.85rem;
          margin-bottom: 0.5rem;
        }
        .madeira-header {
          background: var(--hds-navy);
          color: white;
          padding: 0.4rem 0.8rem;
          font-weight: 600;
          letter-spacing: 0.04em;
          font-size: 0.8rem;
          margin-top: 0.5rem;
        }
        .swatch {
          width: 22px; height: 22px; border: 1px solid #888;
          border-radius: 3px; display: inline-block;
          vertical-align: middle; margin-right: 8px;
        }
        .row-subtotal {
          background: #f1f4f8;
          border-left: 3px solid var(--hds-coral);
          padding: 0.3rem 0.6rem;
          font-size: 0.82rem;
          margin-top: 0.3rem;
          border-radius: 4px;
        }
        .module-card-link {
          text-decoration: none !important;
          color: inherit !important;
          display: flex;
          height: 100%;
          cursor: pointer;
          transition: transform 0.12s ease, box-shadow 0.12s ease;
        }
        .module-card-link:hover {
          transform: translateY(-2px);
          text-decoration: none !important;
        }
        .module-card-link:hover .module-card {
          border-color: var(--hds-coral);
          box-shadow: 0 6px 16px rgba(26, 58, 92, 0.12);
        }
        .module-card {
          border: 1px solid #d8d4c8;
          background: white;
          border-radius: 10px;
          padding: 1.2rem;
          width: 100%;
          min-height: 380px;
          display: flex;
          flex-direction: column;
          transition: border-color 0.12s ease, box-shadow 0.12s ease;
        }
        .module-card .module-desc {
          flex: 1 1 auto;
        }
        .module-card .module-handoff {
          margin-top: auto;
          padding-top: 0.5rem;
        }
        /* Force Streamlit column children to stretch equally in a row */
        div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {
          display: flex;
        }
        div[data-testid="stColumn"] > div[data-testid="stVerticalBlock"] {
          width: 100%;
        }
        .module-card h3 {
          margin-top: 0 !important;
          margin-bottom: 0.3rem !important;
        }
        .module-icon {
          font-size: 2rem;
          margin-bottom: 0.4rem;
        }
        .module-desc {
          color: #555;
          font-size: 0.88rem;
          margin-bottom: 0.8rem;
          line-height: 1.4;
        }
        .module-handoff {
          font-size: 0.75rem;
          color: var(--hds-coral);
          font-weight: 600;
          margin-top: 0.4rem;
          letter-spacing: 0.03em;
          text-transform: uppercase;
        }
        .coming-next {
          background: #f4f1eb;
          border: 1px dashed #b8b0a0;
          border-radius: 8px;
          padding: 0.8rem 1rem;
          margin-bottom: 0.6rem;
        }
        .upload-chip {
          display: inline-block;
          background: #e8f0ff;
          color: var(--hds-navy);
          padding: 0.2rem 0.55rem;
          border-radius: 4px;
          font-size: 0.7rem;
          font-weight: 700;
          letter-spacing: 0.05em;
          text-transform: uppercase;
          margin-bottom: 0.5rem;
        }
        .upload-chip.browse {
          background: #f1eee5;
          color: #8a6f3a;
        }
        .upload-chip.universal {
          background: #fff0e6;
          color: var(--hds-coral);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_page_header(title, tagline=None):
    """Standard page header with HDS branding and back-to-home link."""
    head_col1, head_col2 = st.columns([4, 1])
    with head_col1:
        st.title(title)
        if tagline:
            st.markdown(f'<div class="hds-tagline">{tagline}</div>', unsafe_allow_html=True)
    with head_col2:
        st.markdown("&nbsp;")
        try:
            st.page_link("Home.py", label="← Back to home")
        except Exception:
            st.caption("(home)")


def render_antera_handoff(text):
    """Coral-bordered Antera handoff callout."""
    st.markdown(
        f'<div class="antera-handoff"><strong>Antera handoff:</strong> {text}</div>',
        unsafe_allow_html=True,
    )


def customer_selector(required=False, label="Active customer"):
    """Render the shared customer picker. Persists across pages via session_state.
    Returns the active customer dict or None.

    No walk-in option - every transaction belongs to a customer. Default is
    '+ Add new customer' which surfaces the add-new form so first-time users
    can't accidentally proceed without a customer attached.
    """
    customers = repo.list_customers()
    ADD_NEW = "+ Add new customer"
    options = [ADD_NEW] + [f"{c['display_name']} [{c['customer_id'][:8]}]" for c in customers]

    # Default to last-selected if it still exists, otherwise ADD_NEW
    last_label = st.session_state.get("active_customer_label", ADD_NEW)
    if last_label not in options:
        last_label = ADD_NEW
    default_idx = options.index(last_label)

    selected = st.selectbox(label + ":", options, index=default_idx, key="customer_picker_widget")
    st.session_state["active_customer_label"] = selected

    if selected == ADD_NEW:
        with st.form("new_customer_form"):
            nc1, nc2 = st.columns([2, 1])
            with nc1:
                new_name = st.text_input("Display name", placeholder="e.g. Acme Corporation")
            with nc2:
                new_antera = st.text_input("Antera Customer ID", placeholder="e.g. CUS-1234")
            new_notes = st.text_input("Notes (optional)", placeholder="e.g. Net 30, embroidery preferred")
            if st.form_submit_button("Create customer"):
                if new_name.strip():
                    created = repo.create_customer(new_name, antera_customer_id=new_antera, notes=new_notes)
                    new_label = f"{created['display_name']} [{created['customer_id'][:8]}]"
                    # Update BOTH the persistent state AND the widget's state key.
                    # Streamlit prefers session_state[widget_key] over the index= param,
                    # so without this the dropdown sticks on "+ Add new customer".
                    st.session_state["active_customer_label"] = new_label
                    st.session_state["customer_picker_widget"] = new_label
                    st.success(f"Created: {created['display_name']}")
                    st.rerun()
                else:
                    st.error("Display name required.")
        if required:
            st.stop()
        return None

    short_id = selected.split("[")[-1].rstrip("]")
    for c in customers:
        if c["customer_id"].startswith(short_id):
            return c
    return None


def render_customer_panel(customer):
    """Compact customer info panel — Antera ID + notes."""
    if not customer:
        return
    antera_id = customer.get("antera_customer_id") or "—"
    st.markdown(f"**{customer['display_name']}** &middot; Antera ID: `{antera_id}`", unsafe_allow_html=True)
    if customer.get("notes"):
        st.caption(customer["notes"])


# ============================================================
# EMBEDDED CLAUDE CHAT (sidebar, every page)
# ============================================================

DEMO_SYSTEM_PROMPT = """You are the HDS Document Pipeline demo assistant - an embedded Claude chat that helps the user (likely Ryan Niggel, Martin Bohinski, Howard Schwartz, or Ned West of HDS Marketing) understand what this demo platform does.

This is a proof-of-concept demo built by Adam J. Reep for his interview with HDS Marketing for the AI Workflow Architect & Implementation Lead role. The demo augments HDS's existing Antera ERP - it does not replace it.

MODULES IN THIS DEMO:
1. Home - landing page with module cards
2. Artwork & Order Builder - upload a logo, get a decoration recommendation (embroidery/screen print/DTG/sublimation), see a Madeira-style production sheet, build a multi-line quote with per-line garment/color/placement/logo size/method/2D mockup. Generates HDS-branded customer PDF quote.
3. Bills & Invoices - upload vendor or freight invoice, extract vendor/lines/totals/payment
4. Spec Sheets - upload a product data sheet (Madeira thread, Wilflex ink, blank apparel), extract into standardized reference
5. Forms & Notes - handwritten production-floor notes, mixed printed/handwritten forms
6. Customer Orders - browse-only view of active orders per customer, with Antera jobs context
7. Customer Library - all customers (18 HDS-real customers seeded: Steelers, Cavs, Cardinals, Broncos, Patriots, NFL, Highmark, AHN, 84 Lumber, Vitamix, Fujifilm, Siemens, Skanska, Big Lots, Peloton, Rolling Stones, Star Wars/Disney). Their artwork + order history.
8. Universal Text Extractor - the Swiss army knife. Drop ANY file (PDF, image, SVG, DOCX, AI, even zip) and get text + Claude's contextual notes. If multiple files relate, cross-file summary.
9. Receipts & Expenses - batch-snap receipts, pick customer + Antera job from dropdown, edit fields, accept. Replaces email-photo-with-job-number workflow.
10. Reporting - drill into accepted queues across all modules. Filter by customer, job, category, date.

STACK: Google Cloud Vision for OCR + Claude Haiku 4.5 for structured extraction. Streamlit UI. PIL for mockups. svglib for SVG. python-docx for DOCX. reportlab for PDF generation.

ANTERA HANDOFF FRAMING: Every module annotates how its output feeds Antera (AP queue, Item Master, Job Costing, sales order, production work order). The demo is positioned as augmenting Antera, not replacing it.

DEMO SCOPE: This is a proof of concept. Some elements are mocked (Antera jobs are local JSON; in production they'd be live API calls). The Reporting "queues" are JSON files; in production they'd push to Antera and/or Google Sheets.

ABOUT ADAM: Adam Reep, 20 years operations/IT experience, Pittsburgh-based (Millvale). Built this demo Sunday-Monday for an interview Tuesday May 26, 2026.

You answer questions about the demo, what each module does, why decisions were made, the Antera integration story, etc. Keep responses concise (under 150 words usually). You can also be playful and acknowledge that you (the chat) are part of the demo - meta is allowed.

Don't oversell. Be honest about what's mocked vs real. Don't make up features that don't exist."""


def chat_sidebar():
    """Render the embedded Claude chat in the sidebar. Call from every page after inject_styles()."""
    with st.sidebar:
        st.markdown("---")
        st.markdown("### 💬 Ask the demo")
        st.caption("Embedded Claude — knows about this app's modules and context.")

        if "_chat_history" not in st.session_state:
            st.session_state["_chat_history"] = []

        # Render existing history (compact)
        for msg in st.session_state["_chat_history"][-6:]:  # show last 6 turns
            role_emoji = "🧑" if msg["role"] == "user" else "🤖"
            st.markdown(f"**{role_emoji}** {msg['content']}")

        # Chat input
        prompt = st.chat_input("Ask about any module...")
        if prompt:
            st.session_state["_chat_history"].append({"role": "user", "content": prompt})
            try:
                # Lazy import to keep startup fast
                from pipeline import get_anthropic_client, EXTRACTION_MODEL
                client = get_anthropic_client()
                # Build messages from history
                msgs = [{"role": m["role"], "content": m["content"]} for m in st.session_state["_chat_history"]]
                resp = client.messages.create(
                    model=EXTRACTION_MODEL,
                    max_tokens=400,
                    system=DEMO_SYSTEM_PROMPT,
                    messages=msgs,
                )
                reply = resp.content[0].text.strip()
                st.session_state["_chat_history"].append({"role": "assistant", "content": reply})
            except Exception as e:
                st.session_state["_chat_history"].append({"role": "assistant", "content": f"_(Chat error: {e})_"})
            st.rerun()

        if st.session_state["_chat_history"]:
            if st.button("Clear chat", key="_clear_chat"):
                st.session_state["_chat_history"] = []
                st.rerun()
