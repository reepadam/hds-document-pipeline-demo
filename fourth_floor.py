"""
The Fourth Floor — a private demo suite for Dave.
Reached only via ?floor=4 on the Home page. Not in the sidebar nav.

Six modules for a three-floor restaurant's bookkeeper: invoice intake with
price-creep detection, cash-out reconciliation, inventory counts, family
receipt classification, prep/86 lists, and kitchen-wall schedule capture.

Reuses pipeline.py's OCR + Claude plumbing. All extraction is schema-prompted
JSON — which is the answer to "there's no universal standard format for invoices."
"""
import csv
import io
import json
from datetime import date

import streamlit as st

from pipeline import (
    EXTRACTION_MODEL,
    get_anthropic_client,
    strip_json_fence,
    pdf_to_images,
    image_to_bytes,
    ocr_image_bytes,
)

# ---------------------------------------------------------------- helpers

def _claude_json(prompt_template, text, max_tokens=3000):
    """Run a schema prompt against Claude, return parsed JSON + cost meta."""
    client = get_anthropic_client()
    prompt = prompt_template.replace("<<TEXT>>", text)
    msg = client.messages.create(
        model=EXTRACTION_MODEL, max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    parsed = json.loads(strip_json_fence(msg.content[0].text))
    parsed["_meta"] = {
        "model": msg.model,
        "tokens_in": msg.usage.input_tokens,
        "tokens_out": msg.usage.output_tokens,
        "approx_cost_usd": round(
            (msg.usage.input_tokens * 0.0000008) + (msg.usage.output_tokens * 0.000004), 4
        ),
    }
    return parsed


def _ocr_upload(uploaded):
    """OCR any uploaded file (pdf or image) into raw text."""
    raw = uploaded.read()
    ext = uploaded.name.rsplit(".", 1)[-1].lower()
    if ext == "pdf":
        pages = pdf_to_images(raw)
        return "\n\n".join(ocr_image_bytes(image_to_bytes(p)) for p in pages)
    return ocr_image_bytes(raw)


def _csv_download(rows, fieldnames, label, filename, key):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    w.writeheader()
    for r in rows:
        w.writerow(r)
    st.download_button(label, buf.getvalue(), file_name=filename, mime="text/csv", key=key)


def _json_download(obj, label, filename, key):
    clean = {k: v for k, v in obj.items() if k != "_meta"}
    st.download_button(label, json.dumps(clean, indent=2), file_name=filename,
                       mime="application/json", key=key)


def _cost_caption(parsed):
    m = parsed.get("_meta", {})
    if m:
        st.caption(f"Extraction: {m.get('model','')} · ~${m.get('approx_cost_usd', 0)} · "
                   "compare: the add-on path returns coded line items in up to 24 hours.")


def _intake(key, sample_text, sample_label="Run the sample document"):
    """Standard intake row: upload OR sample. Returns raw text or None."""
    up = st.file_uploader("Upload a photo or PDF", type=["png", "jpg", "jpeg", "pdf"], key=f"{key}_up")
    c1, c2 = st.columns(2)
    go_upload = c1.button("Extract from upload", key=f"{key}_go", disabled=up is None)
    go_sample = c2.button(f"🎬 {sample_label}", key=f"{key}_sample")
    if go_upload and up is not None:
        with st.spinner("OCR + extraction running…"):
            return _ocr_upload(up)
    if go_sample:
        return sample_text
    return None

# ---------------------------------------------------------------- schemas / prompts

INVOICE_PROMPT = """You are an invoice digitization engine for a three-floor restaurant
(floor 1: casual cantina, floor 2: dining room, floor 3: rooftop bar).
Vendors use wildly inconsistent invoice formats — that is exactly why you exist.

Extract the document below into ONLY this JSON (no prose, no fences):
{
  "vendor": {"name": null, "remit_to": null, "phone": null},
  "invoice_number": null,
  "invoice_date": "YYYY-MM-DD or null",
  "terms": null,
  "line_items": [
    {"raw_description": "", "item": "normalized item name", "brand": null,
     "pack_size": "e.g. 6/10lb case", "quantity": 0, "unit": "case/lb/ea",
     "unit_price": 0.0, "extended_price": 0.0,
     "category": "one of: Protein, Produce, Dairy, Dry Goods, Bakery, Liquor, Beer, Wine, NA Beverage, Paper & Disposables, Chemical & Cleaning, Equipment & Smallwares, Services, Other",
     "likely_floor": "1, 2, 3, shared, or null"}
  ],
  "subtotal": null, "tax": null, "delivery_fee": null, "total": null,
  "flags": ["anything ambiguous, illegible, or where math doesn't reconcile"]
}
Rules: never invent numbers. If unit price is missing, derive it from extended/qty and flag it.
If line math doesn't add up to the printed total, flag it — do not 'fix' the total.

DOCUMENT:
<<TEXT>>"""

CASHOUT_PROMPT = """You read end-of-night cash-out sheets (often handwritten) for a
three-floor restaurant. Extract ONLY this JSON (no prose, no fences):
{
  "sheet_date": "YYYY-MM-DD or null",
  "floor": "1, 2, 3, or null",
  "counted_by": null,
  "drawer_count_total": null,
  "tips_declared": null,
  "deposit_prepared": null,
  "float_left_in_till": null,
  "notes": null,
  "flags": ["illegible or suspicious entries"]
}
Never invent numbers; null and flag instead.

DOCUMENT:
<<TEXT>>"""

INVENTORY_PROMPT = """You read handwritten inventory count sheets for a restaurant.
Extract ONLY this JSON (no prose, no fences):
{
  "count_date": "YYYY-MM-DD or null",
  "area": "walk-in / dry storage / bar / etc.",
  "counted_by": null,
  "items": [
    {"item": "", "unit": "case/lb/ea/bottle", "count": 0,
     "par": "number if the sheet shows one, else null",
     "below_par": "true/false/null"}
  ],
  "flags": ["illegible counts, ambiguous units"]
}

DOCUMENT:
<<TEXT>>"""

RECEIPT_PROMPT = """You classify receipts for a family-owned restaurant where the family
covers some personal expenses from the business. Nobody is in trouble — the goal is clean
books and a painless tax season. Extract ONLY this JSON (no prose, no fences):
{
  "merchant": null, "receipt_date": "YYYY-MM-DD or null", "total": null,
  "tax": null, "payment_hint": "card/cash/null",
  "items_summary": "one line describing what was bought",
  "classification": "business_expense | owner_draw | mixed_or_unclear",
  "suggested_category": "e.g. Repairs & Maintenance, Smallwares, Owner Draw, Groceries-personal",
  "rationale": "one plain-English sentence",
  "flags": []
}
Rule of thumb: restaurant supplies/equipment/food for service = business;
personal groceries, household goods, family purchases = owner_draw; genuinely ambiguous = mixed_or_unclear.

DOCUMENT:
<<TEXT>>"""

PREP_PROMPT = """You read handwritten kitchen prep notes and 86 lists.
Extract ONLY this JSON (no prose, no fences):
{
  "note_date": "YYYY-MM-DD or null",
  "station_or_author": null,
  "prep_tasks": [{"item": "", "quantity": null, "needed_by": null}],
  "eighty_sixed": ["items marked 86'd / out"],
  "needs_ordering": ["items the note says to order or that being 86'd implies"],
  "flags": []
}

DOCUMENT:
<<TEXT>>"""

SCHEDULE_PROMPT = """You read a paper staff schedule photographed off a kitchen wall.
Grids vary; names may be first-name-only; times may be shorthand ("4-cl" = 4pm to close).
Extract ONLY this JSON (no prose, no fences):
{
  "week_of": "YYYY-MM-DD of the Monday if determinable, else null",
  "floor_or_station": null,
  "shifts": [
    {"employee": "", "day": "Mon/Tue/...", "start": "HH:MM 24h or shorthand as written",
     "end": "HH:MM 24h or 'close'", "position": "cook/prep/dish/etc or null"}
  ],
  "flags": ["illegible cells, ambiguous times"]
}
Transcribe shorthand faithfully and flag it rather than guessing exact times.

DOCUMENT:
<<TEXT>>"""

# ---------------------------------------------------------------- sample documents

SAMPLE_INVOICE_JAN = """KEYSTONE FOOD DISTRIBUTORS  INV# KFD-88121  01/12/2026  NET 14
SOLD TO: SIENNA MERCADO 412 SMITHFIELD ST PGH PA
CHIX BRST BNLS 4/10LB CS   3 CS @ 68.40   205.20
GRD BEEF 80/20 10LB        6 EA @ 31.90   191.40
TOMATO 6X6 25LB CS         2 CS @ 24.75    49.50
QUESO FRESCO 12/14OZ       1 CS @ 41.25    41.25
FRYER OIL 35LB JIB         2 EA @ 38.60    77.20
LIME 200CT                 1 CS @ 52.00    52.00
TO-GO CLAMSHELL 9" 200CT   1 CS @ 47.80    47.80
SUBTOTAL 664.35  DELIVERY 15.00  TOTAL 679.35"""

SAMPLE_INVOICE_MAY = """KEYSTONE FOOD DIST.   Invoice KFD-91408   May 11 2026   Terms: Net 14
Ship to: Sienna Mercado, 412 Smithfield
3 cs Chicken Breast bnls 4/10# ........ 74.95/cs ... 224.85
6 ea Ground Beef 80/20 10# ............ 33.10 ...... 198.60
2 cs Tomato 6x6 25# ................... 26.90 ....... 53.80
1 cs Queso Fresco 12/14oz ............. 47.50 ....... 47.50
2 ea Fryer Oil 35# JIB ................ 41.20 ....... 82.40
1 cs Limes 175ct ...................... 54.00 ....... 54.00
1 cs 9in To-Go Clamshell 200ct ........ 47.80 ....... 47.80
Sub 708.95   Fuel/Delivery 18.00   Invoice Total 726.95"""

SAMPLE_CASHOUT = """cash out  Fri 5/29  floor 3 (roof)
counted by: Marisol
drawer: 1,184.50
tips declared: 312
deposit bag: 1184.50  <- ALL of it
float left: 0 !!
note - Tony said take everything to the bank again. tills empty for tmrw open AGAIN"""

SAMPLE_INVENTORY = """WALK-IN count  Sun 5/31  - Hector
chix brst   3.5 cs   (par 5)
grd beef    2 cs     par 4
queso fresco  8 ea  par 12
tomatoes 6x6   1.5 cs  par 3
limes  ~80 ea
crema   6 ea   par 6
fryer oil  1 jib  PAR 3  ORDER!!
tortilla 6in  9 sleeve  par 10"""

SAMPLE_RECEIPT = """COSTCO WHOLESALE #1023  PITTSBURGH PA
05/27/2026  17:42
KS PAPER TOWEL 12PK      19.99
DOG FOOD 40LB            46.99
KIDS SOCCER CLEATS       34.99
FOLDING TABLE 6FT        59.99
KS TRASH BAGS 200CT      21.49
SUBTOTAL 183.45  TAX 12.84  TOTAL 196.29  VISA ****8841"""

SAMPLE_PREP = """prep - weds
- dice 2 lugs tomato for pico
- 4 qts crema lime
- portion chix 40 x 6oz
- 86 queso fundido (no fresco till thurs)
- 86 rooftop frozen marg - machine down AGAIN call guy
order: fresco, fryer oil x2, limes"""

SAMPLE_SCHEDULE = """KITCHEN WK 6/8   (taped on wall by Tony)
           MON    TUE    WED    THU    FRI    SAT    SUN
HECTOR     10-6   10-6   off    10-6   10-cl  10-cl  off
MARISOL    4-cl   off    4-cl   4-cl   4-cl   4-cl   off
DANNY      off    11-7   11-7   off    11-cl  11-cl  11-5
LUZ(prep)  8-2    8-2    8-2    8-2    8-2    off    off
SAM(dish)  5-cl   off    5-cl   5-cl   5-cl   5-cl   off"""

# Seeded purchase history so the price-creep report has depth on first run.
SEED_HISTORY = [
    {"invoice_date": "2026-01-12", "vendor": "Keystone Food Distributors", "item": "Chicken Breast bnls 4/10lb", "pack_size": "4/10lb cs", "unit": "case", "unit_price": 68.40},
    {"invoice_date": "2026-03-09", "vendor": "Keystone Food Distributors", "item": "Chicken Breast bnls 4/10lb", "pack_size": "4/10lb cs", "unit": "case", "unit_price": 71.20},
    {"invoice_date": "2026-01-12", "vendor": "Keystone Food Distributors", "item": "Ground Beef 80/20 10lb", "pack_size": "10lb", "unit": "ea", "unit_price": 31.90},
    {"invoice_date": "2026-03-09", "vendor": "Keystone Food Distributors", "item": "Ground Beef 80/20 10lb", "pack_size": "10lb", "unit": "ea", "unit_price": 32.40},
    {"invoice_date": "2026-01-12", "vendor": "Keystone Food Distributors", "item": "Queso Fresco 12/14oz", "pack_size": "12/14oz cs", "unit": "case", "unit_price": 41.25},
    {"invoice_date": "2026-03-09", "vendor": "Keystone Food Distributors", "item": "Queso Fresco 12/14oz", "pack_size": "12/14oz cs", "unit": "case", "unit_price": 43.80},
    {"invoice_date": "2026-01-12", "vendor": "Keystone Food Distributors", "item": "Limes", "pack_size": "200ct cs", "unit": "case", "unit_price": 52.00},
    {"invoice_date": "2026-03-09", "vendor": "Keystone Food Distributors", "item": "Limes", "pack_size": "200ct cs", "unit": "case", "unit_price": 52.00},
]

# ---------------------------------------------------------------- price creep

def _norm_item(name):
    return "".join(ch for ch in (name or "").lower() if ch.isalnum() or ch == " ").strip()


def _record_invoice(parsed):
    hist = st.session_state.setdefault("ff_history", list(SEED_HISTORY))
    for li in parsed.get("line_items", []):
        hist.append({
            "invoice_date": parsed.get("invoice_date") or "",
            "vendor": (parsed.get("vendor") or {}).get("name") or "",
            "item": li.get("item") or li.get("raw_description") or "",
            "pack_size": li.get("pack_size") or "",
            "unit": li.get("unit") or "",
            "unit_price": li.get("unit_price"),
        })


def _creep_report():
    hist = st.session_state.get("ff_history", list(SEED_HISTORY))
    by_item = {}
    for row in hist:
        if row.get("unit_price") in (None, ""):
            continue
        by_item.setdefault(_norm_item(row["item"]), []).append(row)
    out = []
    for _, rows in sorted(by_item.items()):
        rows = sorted(rows, key=lambda r: r.get("invoice_date") or "")
        if len(rows) < 2:
            continue
        first, last = rows[0], rows[-1]
        try:
            p0, p1 = float(first["unit_price"]), float(last["unit_price"])
        except (TypeError, ValueError):
            continue
        if p0 <= 0:
            continue
        pct = (p1 - p0) / p0 * 100
        pack_changed = _norm_item(first.get("pack_size", "")) != _norm_item(last.get("pack_size", ""))
        out.append({
            "item": last["item"], "vendor": last["vendor"],
            "first seen": f"{first['invoice_date']} @ ${p0:.2f}",
            "latest": f"{last['invoice_date']} @ ${p1:.2f}",
            "change": f"{pct:+.1f}%",
            "pack size": ("⚠️ CHANGED: " + f"{first.get('pack_size','?')} → {last.get('pack_size','?')}") if pack_changed else (last.get("pack_size") or "—"),
            "_pct": pct,
        })
    return sorted(out, key=lambda r: -abs(r["_pct"]))

# ---------------------------------------------------------------- modules

def _module_invoices():
    st.markdown("**The complaint this answers:** no two vendors format an invoice the same way, "
                "so line items get keyed by hand. Schema-prompted extraction doesn't care about layout — "
                "it returns the same JSON shape from any of them, in seconds, for ~$0.003.")
    text = _intake("inv", SAMPLE_INVOICE_JAN, "Run sample invoice (January)")
    c3, _ = st.columns(2)
    if c3.button("🎬 Run sample invoice (May — same vendor, 4 months later)", key="inv_sample2"):
        text = SAMPLE_INVOICE_MAY
    if text:
        with st.spinner("Extracting line items…"):
            parsed = _claude_json(INVOICE_PROMPT, text)
        st.session_state["ff_last_invoice"] = parsed
        _record_invoice(parsed)
    parsed = st.session_state.get("ff_last_invoice")
    if parsed:
        v = parsed.get("vendor") or {}
        st.success(f"**{v.get('name','?')}** · inv {parsed.get('invoice_number','?')} · "
                   f"{parsed.get('invoice_date','?')} · total ${parsed.get('total','?')}")
        st.dataframe(parsed.get("line_items", []), use_container_width=True)
        if parsed.get("flags"):
            st.warning("Flags for human review: " + " · ".join(parsed["flags"]))
        _cost_caption(parsed)
        c1, c2 = st.columns(2)
        with c1:
            _csv_download(parsed.get("line_items", []),
                          ["raw_description", "item", "brand", "pack_size", "quantity", "unit",
                           "unit_price", "extended_price", "category", "likely_floor"],
                          "⬇️ Line items CSV (books-ready)", "invoice_line_items.csv", "inv_csv")
        with c2:
            _json_download(parsed, "⬇️ Canonical JSON (xtraCHEF-shaped)", "invoice.json", "inv_json")

    st.markdown("---")
    st.markdown("#### 📈 Price-creep watch")
    st.caption("Every extracted invoice feeds this table (demo seeds it with two months of history). "
               "Unit prices tracked per item across invoices — increases and pack-size shrinkage get flagged. "
               "Run the January sample, then the May sample, and watch the chicken.")
    report = _creep_report()
    if report:
        st.dataframe([{k: v for k, v in r.items() if k != "_pct"} for r in report],
                     use_container_width=True)
        worst = report[0]
        if abs(worst["_pct"]) >= 5:
            st.error(f"Biggest mover: **{worst['item']}** — {worst['change']} "
                     f"({worst['first seen']} → {worst['latest']}). "
                     "This is the sentence that changes what the restaurant pays for food.")
    else:
        st.info("Extract an invoice to start the history.")


def _module_cashout():
    st.markdown("**The complaint this answers:** tills emptied into the deposit bag, payroll account "
                "left unfunded, nobody notices until the morning scramble. The cash-out sheet already "
                "exists on paper — this reads it and reconciles it against what Toast says.")
    text = _intake("cash", SAMPLE_CASHOUT, "Run sample cash-out sheet (handwriting transcript)")
    st.caption("Enter the Toast end-of-day numbers to reconcile against (sample values preloaded):")
    c1, c2, c3 = st.columns(3)
    toast_cash = c1.number_input("Toast: cash sales ($)", value=1112.00, key="cash_t1")
    expected_float = c2.number_input("House rule: float per till ($)", value=300.00, key="cash_t2")
    payroll_due = c3.number_input("Payroll needs by Friday ($)", value=9400.00, key="cash_t3")
    if text:
        with st.spinner("Reading the sheet…"):
            parsed = _claude_json(CASHOUT_PROMPT, text)
        st.session_state["ff_last_cashout"] = parsed
    parsed = st.session_state.get("ff_last_cashout")
    if parsed:
        st.dataframe([{k: v for k, v in parsed.items() if k not in ("_meta", "flags")}],
                     use_container_width=True)
        counted = parsed.get("drawer_count_total") or 0
        deposited = parsed.get("deposit_prepared") or 0
        float_left = parsed.get("float_left_in_till")
        rows = [
            {"check": "Counted vs Toast cash sales",
             "result": f"counted ${counted:,.2f} vs Toast ${toast_cash:,.2f} → variance ${counted - toast_cash:+,.2f}"},
            {"check": "Float rule",
             "result": (f"❌ ${float_left or 0:,.2f} left in till — house rule is ${expected_float:,.2f}. "
                        "Tomorrow opens with no change again.") if (float_left or 0) < expected_float
                       else f"✅ ${float_left:,.2f} float left, rule is ${expected_float:,.2f}"},
            {"check": "Deposit sanity",
             "result": f"deposit bag ${deposited:,.2f}; payroll needs ${payroll_due:,.2f} in the payroll account by Friday — "
                       "auto-funding rule would move this before anyone can 'help.'"},
        ]
        st.dataframe(rows, use_container_width=True)
        if parsed.get("flags"):
            st.warning("Flags: " + " · ".join(parsed["flags"]))
        _cost_caption(parsed)
        _json_download(parsed, "⬇️ Cash-out JSON", "cashout.json", "cash_json")


def _module_inventory():
    st.markdown("**The complaint this answers:** counts live on a clipboard, so ordering is a gut call. "
                "Photograph the count sheet and the pars do the arguing.")
    text = _intake("invcount", SAMPLE_INVENTORY, "Run sample walk-in count (handwriting transcript)")
    if text:
        with st.spinner("Reading the count…"):
            parsed = _claude_json(INVENTORY_PROMPT, text)
        st.session_state["ff_last_count"] = parsed
    parsed = st.session_state.get("ff_last_count")
    if parsed:
        items = parsed.get("items", [])
        st.success(f"{parsed.get('area','?')} · {parsed.get('count_date','?')} · counted by {parsed.get('counted_by','?')}")
        st.dataframe(items, use_container_width=True)
        order_now = [i for i in items if str(i.get("below_par")).lower() == "true"]
        if order_now:
            st.error("**Order list, derived automatically:** " +
                     " · ".join(f"{i['item']} (at {i['count']}, par {i['par']})" for i in order_now))
        if parsed.get("flags"):
            st.warning("Flags: " + " · ".join(parsed["flags"]))
        _cost_caption(parsed)
        _csv_download(items, ["item", "unit", "count", "par", "below_par"],
                      "⬇️ Counts CSV", "inventory_count.csv", "cnt_csv")


def _module_receipts():
    st.markdown("**The complaint this answers:** the family's personal spending and the restaurant's "
                "spending share a wallet. Nobody's in trouble — but the books need to know which is which, "
                "and tax season shouldn't be archaeology.")
    text = _intake("rcpt", SAMPLE_RECEIPT, "Run sample receipt (Costco run)")
    if text:
        with st.spinner("Classifying…"):
            parsed = _claude_json(RECEIPT_PROMPT, text)
        st.session_state["ff_last_receipt"] = parsed
    parsed = st.session_state.get("ff_last_receipt")
    if parsed:
        cls = parsed.get("classification", "?")
        badge = {"business_expense": "🟢 BUSINESS", "owner_draw": "🟠 OWNER DRAW",
                 "mixed_or_unclear": "🟡 MIXED — needs a human"}.get(cls, cls)
        st.success(f"{badge} · {parsed.get('merchant','?')} · ${parsed.get('total','?')} · "
                   f"{parsed.get('suggested_category','')}")
        st.markdown(f"*{parsed.get('rationale','')}*")
        st.markdown(f"**Items:** {parsed.get('items_summary','')}")
        _cost_caption(parsed)
        _json_download(parsed, "⬇️ Receipt JSON", "receipt.json", "rcpt_json")
        st.caption("In production this lands in a draw-vs-business ledger; a fixed monthly owner-draw "
                    "account makes this whole category boring — which is the goal.")


def _module_prep():
    st.markdown("**The complaint this answers:** the kitchen already writes down what's prepped, "
                "what's 86'd, and what to order — on paper that nobody upstream ever sees.")
    text = _intake("prep", SAMPLE_PREP, "Run sample prep note (handwriting transcript)")
    if text:
        with st.spinner("Reading the note…"):
            parsed = _claude_json(PREP_PROMPT, text)
        st.session_state["ff_last_prep"] = parsed
    parsed = st.session_state.get("ff_last_prep")
    if parsed:
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("**Prep tasks**")
            st.dataframe(parsed.get("prep_tasks", []), use_container_width=True)
        with c2:
            st.markdown("**86'd**")
            for x in parsed.get("eighty_sixed", []):
                st.markdown(f"- 🚫 {x}")
        with c3:
            st.markdown("**Needs ordering**")
            for x in parsed.get("needs_ordering", []):
                st.markdown(f"- 🛒 {x}")
        if parsed.get("flags"):
            st.warning("Flags: " + " · ".join(parsed["flags"]))
        _cost_caption(parsed)
        _json_download(parsed, "⬇️ Prep JSON", "prep_note.json", "prep_json")
        st.caption("86 lists are a leading indicator of ordering failures — every 86'd item here "
                    "cross-references the inventory module's order list.")


def _module_schedule():
    st.markdown("**The complaint this answers:** the head cook writes the schedule on paper and tapes it "
                "to the wall. He's not changing. He doesn't have to — photograph the wall and the schedule "
                "becomes data anyway. (Honest limits: Sling has no public write API, so entry into "
                "Toast/Sling stays a 2-minute transcription — but the *visibility* arrives instantly.)")
    text = _intake("sched", SAMPLE_SCHEDULE, "Run sample wall schedule (transcript)")
    if text:
        with st.spinner("Reading the grid…"):
            parsed = _claude_json(SCHEDULE_PROMPT, text, max_tokens=4000)
        st.session_state["ff_last_sched"] = parsed
    parsed = st.session_state.get("ff_last_sched")
    if parsed:
        shifts = parsed.get("shifts", [])
        st.success(f"Week of {parsed.get('week_of','?')} · {parsed.get('floor_or_station','kitchen')} · "
                   f"{len(shifts)} shifts captured")
        st.dataframe(shifts, use_container_width=True)
        # rough scheduled-hours summary (skips shorthand it can't parse)
        def _hrs(s, e):
            try:
                sh = int(str(s).split(":")[0]); eh = 23 if str(e).lower() in ("close", "cl") else int(str(e).split(":")[0])
                if eh <= sh:
                    eh += 12 if eh + 12 <= 24 else 0
                return max(eh - sh, 0)
            except (ValueError, AttributeError):
                return None
        per_day = {}
        for sft in shifts:
            h = _hrs(sft.get("start"), sft.get("end"))
            if h:
                per_day[sft.get("day", "?")] = per_day.get(sft.get("day", "?"), 0) + h
        if per_day:
            st.markdown("**Scheduled hours per day (estimated):** " +
                        " · ".join(f"{d}: {h}h" for d, h in per_day.items()))
            st.caption("Cross this with Toast sales-by-day and the lever board's slow-shift slider "
                        "stops being an estimate — it becomes a measurement.")
        if parsed.get("flags"):
            st.warning("Flags: " + " · ".join(parsed["flags"]))
        _cost_caption(parsed)
        _csv_download(shifts, ["employee", "day", "start", "end", "position"],
                      "⬇️ Shifts CSV (Sling-ready)", "wall_schedule.csv", "sched_csv")

# ---------------------------------------------------------------- page

def render():
    st.title("🌶️ The Fourth Floor")
    st.markdown(
        '<div class="hds-tagline">A private demo for Dave — the floor the customers never see.</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        "Same OCR + LLM pipeline as the rest of this site, pointed at a three-floor restaurant's "
        "actual paper problem. Every module: **photo or PDF in → structured, books-ready data out** "
        "in seconds, at ~$0.003 per document. Each one has a preloaded sample — press play before "
        "you upload anything real."
    )
    st.markdown('<span class="hds-badge">UNLISTED — YOU FOUND THE EASTER EGG</span>',
                unsafe_allow_html=True)
    st.caption(f"Session date: {date.today().isoformat()} · demo data is invented · "
               "extractions in this session are not stored anywhere")
    st.markdown("---")

    tabs = st.tabs([
        "🧾 Invoices & Price Creep",
        "💵 Cash-Out Reconciliation",
        "📦 Inventory Counts",
        "🧍 Family Receipts",
        "📝 Prep & 86 Lists",
        "📅 Kitchen Wall Schedule",
    ])
    with tabs[0]:
        _module_invoices()
    with tabs[1]:
        _module_cashout()
    with tabs[2]:
        _module_inventory()
    with tabs[3]:
        _module_receipts()
    with tabs[4]:
        _module_prep()
    with tabs[5]:
        _module_schedule()

    st.markdown("---")
    st.caption("Built by Adam (and Claude) in an evening. The lever board is the argument; "
               "this floor is the plumbing. · [adamjreep.com](https://adamjreep.com)")
