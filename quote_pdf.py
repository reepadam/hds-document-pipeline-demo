"""
HDS-branded customer-facing quote PDF generator.

CRITICAL: Only customer-facing fields appear. No house cost, no markup %, no
gross margin, no internal cost basis. Markup is baked into the unit prices.
"""
from io import BytesIO
from datetime import datetime, timedelta
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
)
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT


HDS_NAVY = colors.HexColor("#1a3a5c")
HDS_CORAL = colors.HexColor("#e8743b")
HDS_BG = colors.HexColor("#fafaf6")
LIGHT_GRAY = colors.HexColor("#e8e8e0")


def build_quote_pdf(
    customer_name,
    antera_customer_id,
    quote_number,
    lines,
    setup_breakdown,
    lines_customer_total,
    setup_customer_total,
    grand_total,
    artwork_filename=None,
    valid_days=30,
):
    """Returns PDF bytes ready to st.download_button."""
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        leftMargin=0.6 * inch, rightMargin=0.6 * inch,
        topMargin=0.5 * inch, bottomMargin=0.5 * inch,
        title=f"HDS Marketing Quote {quote_number}",
        author="HDS Marketing",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "Title", parent=styles["Heading1"],
        textColor=HDS_NAVY, fontSize=22, leading=26, spaceAfter=2,
    )
    tagline_style = ParagraphStyle(
        "Tagline", parent=styles["Normal"],
        textColor=HDS_CORAL, fontSize=10, fontName="Helvetica-Oblique",
    )
    h2_style = ParagraphStyle(
        "H2", parent=styles["Heading2"],
        textColor=HDS_NAVY, fontSize=13, spaceBefore=10, spaceAfter=4,
    )
    body_style = ParagraphStyle(
        "Body", parent=styles["Normal"],
        fontSize=9.5, leading=12,
    )
    small_style = ParagraphStyle(
        "Small", parent=styles["Normal"],
        fontSize=8, leading=10, textColor=colors.gray,
    )
    right_style = ParagraphStyle("Right", parent=body_style, alignment=TA_RIGHT)

    story = []
    today = datetime.now()
    valid_until = today + timedelta(days=valid_days)

    # ---- Header ----
    header_data = [[
        Paragraph("<b>HDS Marketing</b>", title_style),
        Paragraph(
            f"<b>QUOTE</b><br/>"
            f"Quote #: <b>{quote_number}</b><br/>"
            f"Date: {today.strftime('%B %d, %Y')}<br/>"
            f"Valid until: {valid_until.strftime('%B %d, %Y')}",
            right_style,
        ),
    ]]
    header_table = Table(header_data, colWidths=[4.0 * inch, 3.4 * inch])
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(header_table)
    story.append(Paragraph("Making the complex, easy.", tagline_style))
    story.append(Spacer(1, 0.15 * inch))

    # Divider
    divider = Table([[""]], colWidths=[7.4 * inch], rowHeights=[2])
    divider.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), HDS_NAVY),
    ]))
    story.append(divider)
    story.append(Spacer(1, 0.18 * inch))

    # ---- Bill To / Customer ----
    bill_data = [[
        Paragraph(
            "<b>PREPARED FOR</b><br/>"
            f"<font size='12'><b>{customer_name}</b></font>"
            + (f"<br/>Customer ID: {antera_customer_id}" if antera_customer_id else ""),
            body_style,
        ),
        Paragraph(
            "<b>FROM</b><br/>"
            "<b>HDS Marketing</b><br/>"
            "2 Penn Center West, Suite 430<br/>"
            "Pittsburgh, PA 15276<br/>"
            "412.279.1600 · contact@hdsbrands.com",
            body_style,
        ),
    ]]
    bill_table = Table(bill_data, colWidths=[3.7 * inch, 3.7 * inch])
    bill_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(bill_table)
    story.append(Spacer(1, 0.2 * inch))

    if artwork_filename:
        story.append(Paragraph(f"<b>Artwork file:</b> {artwork_filename}", body_style))
        story.append(Spacer(1, 0.1 * inch))

    # ---- Line items table ----
    # Each non-zero size becomes its own row for visual clarity. Lines with a
    # single One-Size garment (totes, towels) collapse back to a single row.
    story.append(Paragraph("Line items", h2_style))

    line_headers = ["Garment", "Size", "Color", "Placement", "Decoration", "Logo size", "Qty", "Unit price", "Subtotal"]
    line_rows = [line_headers]
    for ln in lines:
        sizes = ln.get("sizes", {}) or {}
        nonzero = [(sz, q) for sz, q in sizes.items() if q > 0]
        per_pc = ln.get("customer_price_per_pc", 0)
        # If no sizes recorded or only One Size, fall back to single row
        if not nonzero or (len(nonzero) == 1 and nonzero[0][0] in ("One Size", "OSFA")):
            qty = ln.get("quantity", 0) if not nonzero else nonzero[0][1]
            size_label = nonzero[0][0] if nonzero else "—"
            line_rows.append([
                Paragraph(ln.get("garment_type", "—"), body_style),
                Paragraph(size_label, body_style),
                Paragraph(ln.get("base_color", "—"), body_style),
                Paragraph(ln.get("placement", "—") or "—", body_style),
                Paragraph(ln.get("method_label", "—"), body_style),
                Paragraph(f"{ln.get('logo_width_in', 0):.1f}\" × {ln.get('logo_height_in', 0):.1f}\"", body_style),
                Paragraph(str(qty), right_style),
                Paragraph(f"${per_pc:.2f}", right_style),
                Paragraph(f"<b>${per_pc * qty:,.2f}</b>", right_style),
            ])
        else:
            # Expand into one row per size
            for sz, q in nonzero:
                line_rows.append([
                    Paragraph(ln.get("garment_type", "—"), body_style),
                    Paragraph(sz, body_style),
                    Paragraph(ln.get("base_color", "—"), body_style),
                    Paragraph(ln.get("placement", "—") or "—", body_style),
                    Paragraph(ln.get("method_label", "—"), body_style),
                    Paragraph(f"{ln.get('logo_width_in', 0):.1f}\" × {ln.get('logo_height_in', 0):.1f}\"", body_style),
                    Paragraph(str(q), right_style),
                    Paragraph(f"${per_pc:.2f}", right_style),
                    Paragraph(f"<b>${per_pc * q:,.2f}</b>", right_style),
                ])

    line_table = Table(
        line_rows,
        colWidths=[1.15*inch, 0.45*inch, 0.65*inch, 0.95*inch, 0.95*inch, 0.85*inch, 0.4*inch, 0.75*inch, 0.85*inch],
        repeatRows=1,
    )
    line_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HDS_NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, HDS_BG]),
        ("GRID", (0, 0), (-1, -1), 0.3, LIGHT_GRAY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (6, 1), (-1, -1), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(line_table)
    story.append(Spacer(1, 0.2 * inch))

    # (Size breakdown section removed — sizes now appear per-row in the line items table)
    size_lines = []
    if size_lines:
        story.append(Paragraph("<b>Size breakdown</b>", h2_style))
        for sl in size_lines:
            story.append(Paragraph(sl, small_style))
        story.append(Spacer(1, 0.15 * inch))

    # ---- One-time setup ----
    if setup_breakdown:
        story.append(Paragraph("One-time setup", h2_style))
        story.append(Paragraph(
            "Setup fees cover artwork preparation (digitizing, screen burns, etc.) "
            "and are charged once per decoration method, regardless of quantity.",
            small_style,
        ))
        story.append(Spacer(1, 0.05 * inch))
        setup_rows = [["Method", "Setup fee"]]
        for entry in setup_breakdown:
            setup_rows.append([
                Paragraph(entry.get("method_label", "—"), body_style),
                Paragraph(f"${entry.get('setup_customer', 0):,.2f}", right_style),
            ])
        setup_table = Table(setup_rows, colWidths=[5.4*inch, 2.0*inch], repeatRows=1)
        setup_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), HDS_NAVY),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 9),
            ("GRID", (0, 0), (-1, -1), 0.3, LIGHT_GRAY),
            ("ALIGN", (1, 1), (1, -1), "RIGHT"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(setup_table)
        story.append(Spacer(1, 0.2 * inch))

    # ---- Totals ----
    total_rows = [
        ["", "Line items subtotal:", f"${lines_customer_total:,.2f}"],
        ["", "One-time setup:", f"${setup_customer_total:,.2f}"],
        ["", "TOTAL QUOTE:", f"${grand_total:,.2f}"],
    ]
    total_table = Table(total_rows, colWidths=[3.4*inch, 2.4*inch, 1.6*inch])
    total_table.setStyle(TableStyle([
        ("LINEABOVE", (1, -1), (-1, -1), 1.5, HDS_NAVY),
        ("FONTNAME", (1, -1), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (1, -1), (-1, -1), 12),
        ("TEXTCOLOR", (1, -1), (-1, -1), HDS_NAVY),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("ALIGN", (2, 0), (2, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, -1), (-1, -1), 8),
    ]))
    story.append(total_table)
    story.append(Spacer(1, 0.3 * inch))

    # ---- Terms ----
    story.append(Paragraph("Terms & conditions", h2_style))
    terms = (
        "This quote is valid for {} days from issue date. Prices subject to change if "
        "quantities or specifications are modified. Artwork must be approved in writing before "
        "production begins. Standard production time is 7-10 business days after art approval. "
        "Rush production available upon request. All sales subject to HDS Marketing's standard "
        "terms of sale."
    ).format(valid_days)
    story.append(Paragraph(terms, small_style))
    story.append(Spacer(1, 0.15 * inch))

    # ---- Footer ----
    story.append(Paragraph(
        "<b>Questions?</b> Contact your HDS account team or call 412.279.1600.",
        body_style,
    ))
    story.append(Paragraph(
        "PITTSBURGH · CLEVELAND · KANSAS CITY · CINCINNATI · PHOENIX · PORTLAND · HOUSTON · GUANGZHOU",
        small_style,
    ))

    doc.build(story)
    pdf_bytes = buf.getvalue()
    buf.close()
    return pdf_bytes
