"""
HDS Document Pipeline - HOME splash page.
Directional menu: pick the module by what you want to upload.
Run: python -m streamlit run app.py
"""
import re
import streamlit as st
from shared import inject_styles, chat_sidebar


def page_url(page_path):
    """Convert 'pages/1_Artwork_and_Order_Builder.py' → '/Artwork_and_Order_Builder'."""
    filename = page_path.rsplit("/", 1)[-1]
    name = filename.removesuffix(".py")
    name = re.sub(r"^\d+_", "", name)  # strip leading "1_"
    return f"/{name}"

st.set_page_config(
    page_title="OCR + LLM Document Pipeline - POC",
    page_icon=":page_facing_up:",
    layout="wide",
)
inject_styles()
chat_sidebar()

# ---- Hero ----
st.title("OCR + LLM Document Pipeline")
st.markdown(
    '<div class="hds-tagline">Making the complex, easy. - a proof of concept by Adam J. Reep</div>',
    unsafe_allow_html=True,
)
st.markdown(
    "A modular OCR + LLM pipeline that **augments your existing system of record** - it does not replace it. "
    "Each module below ingests one document or artwork type and hands structured data off to the ERP, MRP, or "
    "operational platform of choice (or to a Sheets review buffer the team approves before ingest)."
)
st.markdown('<span class="hds-badge">PROOF OF CONCEPT</span>', unsafe_allow_html=True)
st.markdown("---")

# ---- Directional menu ----
st.subheader("What do you want to upload?")
st.caption("Pick the module that matches your document type. The sidebar nav also lets you jump between modules at any time.")

MODULES = [
    {
        "icon": "🎨",
        "chip": "UPLOAD: LOGO",
        "chip_class": "",
        "name": "Artwork & Order Builder",
        "desc": "Upload a customer logo. Pipeline analyzes colors, recommends decoration method (embroidery/screen print/DTG/sublimation), generates a Madeira-style production sheet, then builds a multi-line quote with garment, color, placement, logo size, size breakdown, and 2D mockup per line. Saves orders to customer history.",
        "page": "pages/1_Artwork_and_Order_Builder.py",
        "handoff": "→ Antera sales order + production work order",
    },
    {
        "icon": "🧾",
        "chip": "UPLOAD: INVOICE",
        "chip_class": "",
        "name": "Bills & Invoices",
        "desc": "Upload a vendor invoice or freight invoice (UPS, FedEx, R+L, etc.). Extracts vendor, transaction details, line items with SKUs, totals, and payment method. Flags any field where OCR uncertainty needs human review.",
        "page": "pages/2_Bills_and_Invoices.py",
        "handoff": "→ Antera AP queue (via Sheets review buffer)",
    },
    {
        "icon": "💳",
        "chip": "UPLOAD: RECEIPT",
        "chip_class": "",
        "name": "Receipts & Expenses",
        "desc": "Field rep snaps a receipt photo. Pipeline extracts merchant, date, total, tax, tip, payment method, and auto-classifies the expense category. Rep picks customer + job from a dropdown - no email subjects, no remembering job numbers. Files to the customer's expense history under that job.",
        "page": "pages/8_Receipts_and_Expenses.py",
        "handoff": "→ Antera Job Costing (charged to the selected Antera Job ID)",
    },
    {
        "icon": "📋",
        "chip": "UPLOAD: SPEC SHEET",
        "chip_class": "",
        "name": "Spec Sheets",
        "desc": "Upload a product data sheet (Madeira thread, Wilflex ink, blank apparel specs). Extracts manufacturer, product line, composition, test ratings, mechanical properties, care instructions, certifications into a standardized reference table.",
        "page": "pages/3_Spec_Sheets.py",
        "handoff": "→ Antera Item Master import row",
    },
    {
        "icon": "✍️",
        "chip": "UPLOAD: NOTE OR FORM",
        "chip_class": "",
        "name": "Forms & Notes",
        "desc": "Upload handwritten production-floor notes, sales meeting jots, or printed forms with handwritten fields filled in. Extracts dates, author, key fields, action items, and unresolved questions for team follow-up. Phase 2 adds the Zebra 'edit-an-order' workflow.",
        "page": "pages/4_Forms_and_Notes.py",
        "handoff": "→ Antera task / production note attachment",
    },
    {
        "icon": "🛒",
        "chip": "UPLOAD: ORDER REQUEST",
        "chip_class": "",
        "name": "Customer Orders",
        "desc": "Customer emailed you an order request? Drop the PDF or scan here. Extracts customer info, items requested, decoration spec, in-hands date, special instructions. Files the request under the customer profile so it becomes a quoteable request - no data entry.",
        "page": "pages/5_Customer_Orders.py",
        "handoff": "→ Antera quote draft",
    },
    {
        "icon": "👥",
        "chip": "BROWSE: NO UPLOAD",
        "chip_class": "browse",
        "name": "Customer Library",
        "desc": "Browse customers, their saved artwork (with thumbnails), and their full order history. Click any logo to reopen it in the Artwork module for a quick reorder. This is the chatbot-ready data layer for the Phase 2 customer ordering assistant.",
        "page": "pages/6_Customer_Library.py",
        "handoff": "Indexes by Antera Customer ID",
    },
    {
        "icon": "🔧",
        "chip": "UPLOAD: ANY FILE",
        "chip_class": "universal",
        "name": "Universal Text Extractor",
        "desc": "The Swiss army knife. Drop ANY file - PDF, image, SVG, DOCX, AI, even unusual formats - and get all text in a copyable block plus Claude's contextual notes on what the document is and what it's for. No structured schema, no metrics, no JSON wrangling. Proves the pipeline can ingest anything.",
        "page": "pages/7_Universal_Text_Extractor.py",
        "handoff": "Ad-hoc tool — no Antera integration",
    },
    {
        "icon": "📊",
        "chip": "BROWSE: REPORTING",
        "chip_class": "browse",
        "name": "Reporting",
        "desc": "Drill into accepted queues across all modules - receipts by job, expenses by category, invoices by vendor, spec sheets by manufacturer. The information-flow view: every Accept button across the platform lands here, queryable by customer, job, category, and date.",
        "page": "pages/9_Reporting.py",
        "handoff": "Demo skinny: JSON queues. Prod: pushes to Antera + Sheets.",
    },
    {
        "icon": "📋",
        "chip": "BROWSE: APPROVALS",
        "chip_class": "browse",
        "name": "Approvals & Change Mgmt",
        "desc": "Every order, grouped by approval stage. Sports/licensed orders route through team → league/properties → sponsor sign-off (NFL Properties, MLB, NBA, NHL). Corporate orders route through customer → production-mgr. Approve or request change in one click, with audit log. Replaces email-thread approvals where status hides in someone's inbox.",
        "page": "pages/10_Approvals_and_Changes.py",
        "handoff": "→ Locks Antera production work order when fully approved",
    },
]

# Render as 3-up rows. Each card is a clickable <a> wrapping the whole tile.
for row_start in range(0, len(MODULES), 3):
    row_modules = MODULES[row_start:row_start + 3]
    cols = st.columns(3)  # always 3 cols so partial rows don't stretch
    for i, mod in enumerate(row_modules):
        with cols[i]:
            chip_extra = f" {mod['chip_class']}" if mod['chip_class'] else ""
            url = page_url(mod["page"])
            st.markdown(
                f"""<a href="{url}" target="_self" class="module-card-link">
                <div class="module-card">
                  <div class="module-icon">{mod['icon']}</div>
                  <span class="upload-chip{chip_extra}">{mod['chip']}</span>
                  <h3>{mod['name']}</h3>
                  <div class="module-desc">{mod['desc']}</div>
                  <div class="module-handoff">{mod['handoff']}</div>
                </div>
                </a>""",
                unsafe_allow_html=True,
            )

# ---- Footer ----
st.markdown("---")
st.caption(
    "Stack: Google Cloud Vision · Claude Haiku 4.5 · Streamlit + PIL + svglib · pypdfium2 · python-docx · "
    "Built by Adam J. Reep · [adamjreep.com](https://adamjreep.com)"
)