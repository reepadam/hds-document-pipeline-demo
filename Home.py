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

# ---- The Fourth Floor (unlisted; reach via ?floor=4) ----
if st.query_params.get("floor") == "4":
    import fourth_floor
    fourth_floor.render()
    st.stop()


# ---- Hero ----
st.title("OCR + LLM Document Pipeline")
st.markdown(
    '<div class="hds-tagline">Making the complex, easy. - a proof of concept by Adam J. Reep</div>',
    unsafe_allow_html=True,
)
st.markdown(
    "A modular OCR + LLM pipeline that turns documents and images into clean, structured data. "
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
        "icon": "🧾",
        "chip": "UPLOAD: INVOICE",
        "chip_class": "",
        "name": "Bills & Invoices",
        "desc": "Upload a vendor invoice or freight invoice (UPS, FedEx, R+L, etc.). Extracts vendor, transaction details, line items with SKUs, totals, and payment method. Flags any field where OCR uncertainty needs human review.",
        "page": "pages/2_Bills_and_Invoices.py",
        "handoff": "",
    },
    {
        "icon": "✍️",
        "chip": "UPLOAD: NOTE OR FORM",
        "chip_class": "",
        "name": "Forms & Notes",
        "desc": "Upload handwritten notes, meeting jots, or printed forms with handwritten fields filled in. Extracts dates, author, key fields, action items, and unresolved questions for follow-up.",
        "page": "pages/4_Forms_and_Notes.py",
        "handoff": "",
    },
    {
        "icon": "🔧",
        "chip": "UPLOAD: ANY FILE",
        "chip_class": "universal",
        "name": "Universal Text Extractor",
        "desc": "The Swiss army knife. Drop ANY file - PDF, image, SVG, DOCX, even unusual formats - and get all text in a copyable block plus Claude's contextual notes on what the document is and what it's for.",
        "page": "pages/7_Universal_Text_Extractor.py",
        "handoff": "",
    },
    {
        "icon": "💳",
        "chip": "UPLOAD: RECEIPT",
        "chip_class": "",
        "name": "Receipts & Expenses",
        "desc": "Snap a receipt photo. Extracts merchant, date, total, tax, tip, payment method, and auto-classifies the expense category, filed under the selected customer and job.",
        "page": "pages/8_Receipts_and_Expenses.py",
        "handoff": "",
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