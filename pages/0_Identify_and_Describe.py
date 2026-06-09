"""
Identify & Describe — vision-first showcase module.

Give it any image and Claude *looks at the picture* (not just text on it):
1. identifies the item, 2. writes a marketplace-ready description.
Raw OCR is shown beside each result to make the point that OCR alone can't
describe an image — vision can. Built general (antiques, products, parts,
anything); rate-limited per session to protect the API key on the public demo.
"""
import base64
import csv
import io
from io import BytesIO
from pathlib import Path

import streamlit as st
from PIL import Image

from pipeline import get_anthropic_client, EXTRACTION_MODEL, ocr_image_bytes
from shared import inject_styles, render_page_header, chat_sidebar

MAX_PER_SESSION = 8          # cap on the public demo (protects the API key)
MAX_DIM = 1024               # downscale long edge before the vision call (cost lever)
IN_RATE = 0.000001           # Claude Haiku 4.5 input  $/token ($1 / 1M, Jun 2026)
OUT_RATE = 0.000005          # Claude Haiku 4.5 output $/token ($5 / 1M, Jun 2026)
IMG_EXTS = ("jpg", "jpeg", "png", "webp", "gif", "bmp", "tiff", "tif")

st.set_page_config(page_title="Identify & Describe", page_icon=":mag:", layout="wide")
inject_styles()
chat_sidebar()
render_page_header(
    "🔎 Identify & Describe",
    "Give it any image — it sees the item, names it, and writes a description.",
)

st.caption(
    "Vision-first: Claude **looks at the picture**, not just any text on it. Built general — point it "
    "at antiques, coins, postcards, products, parts, anything. Raw OCR is shown beside each result so "
    f"you can see why OCR alone can't describe an image. Capped at {MAX_PER_SESSION} images/session on this public demo."
)

PROMPT = (
    "You are looking at a photo of an item someone wants to sell or catalog. "
    "Line 1: a short, specific identification of what the item is (as specific as the image allows). "
    "Then a blank line, then a 40-60 word description suitable for a marketplace listing. "
    "Base everything ONLY on what is visibly present in the image. Do NOT state condition, grade, "
    "authenticity, or monetary value unless it is unambiguously printed on the item. If you are unsure "
    "of a detail, say so rather than guessing. No preamble, no markdown headers."
)


def downscale_png(image_bytes):
    img = Image.open(BytesIO(image_bytes))
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    img.thumbnail((MAX_DIM, MAX_DIM))
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def describe_image(image_bytes):
    png_bytes = downscale_png(image_bytes)
    b64 = base64.standard_b64encode(png_bytes).decode("utf-8")
    client = get_anthropic_client()
    msg = client.messages.create(
        model=EXTRACTION_MODEL,
        max_tokens=400,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b64}},
                {"type": "text", "text": PROMPT},
            ],
        }],
    )
    cost = round(msg.usage.input_tokens * IN_RATE + msg.usage.output_tokens * OUT_RATE, 4)
    return msg.content[0].text.strip(), msg.usage.input_tokens, msg.usage.output_tokens, cost


uploaded = st.file_uploader("Drop image(s)", type=list(IMG_EXTS), accept_multiple_files=True)

if not uploaded:
    st.info("Drop one or more images above. Coins, banknotes, postcards, products — anything.")
    st.stop()

used = st.session_state.get("idd_used", 0)
remaining = max(0, MAX_PER_SESSION - used)
if remaining <= 0:
    st.warning(
        f"Demo limit reached ({MAX_PER_SESSION} images this session). The full tool runs unlimited "
        "batches locally. Refresh the page to reset the demo."
    )
    st.stop()

to_process = uploaded[:remaining]
if len(uploaded) > remaining:
    st.warning(f"Showing the first {remaining} of {len(uploaded)} (demo cap {MAX_PER_SESSION}/session).")

batch_key = "|".join(f"{f.name}:{f.size}" for f in to_process)
cache_id = str(hash(batch_key))

if st.session_state.get("idd_batch") != cache_id:
    results = []
    prog = st.progress(0.0, text="Looking...")
    for i, f in enumerate(to_process):
        data = f.read()
        try:
            ocr = (ocr_image_bytes(data) or "").strip()
        except Exception:
            ocr = ""
        try:
            desc, tin, tout, cost = describe_image(data)
            err = None
        except Exception as e:
            desc, tin, tout, cost, err = "", 0, 0, 0, f"{type(e).__name__}: {e}"
        results.append({
            "name": f.name, "bytes": data, "ocr": ocr,
            "desc": desc, "tin": tin, "tout": tout, "cost": cost, "err": err,
        })
        prog.progress((i + 1) / len(to_process), text=f"Processed {i + 1}/{len(to_process)}")
    prog.empty()
    st.session_state["idd_batch"] = cache_id
    st.session_state["idd_results"] = results
    st.session_state["idd_used"] = used + len(to_process)
else:
    results = st.session_state["idd_results"]

ok = sum(1 for r in results if r["desc"])
total_cost = round(sum(r["cost"] for r in results), 4)
m = st.columns(3)
m[0].metric("Images described", f"{ok}/{len(results)}")
m[1].metric("Total cost", f"${total_cost}")
m[2].metric("Avg / image", f"${round(total_cost / len(results), 4) if results else 0}")

st.markdown("---")
for r in results:
    img_col, ocr_col, ai_col = st.columns([1, 1, 1.6])
    with img_col:
        try:
            st.image(Image.open(BytesIO(r["bytes"])), use_container_width=True)
        except Exception:
            st.write(r["name"])
        st.caption(r["name"])
    with ocr_col:
        st.markdown("**OCR sees (text only)**")
        st.code(r["ocr"] or "(no readable text)", language="text")
    with ai_col:
        st.markdown("**Vision identifies + describes**")
        if r["err"]:
            st.error(r["err"])
        else:
            st.write(r["desc"])
            st.caption(f"Tokens {r['tin']}→{r['tout']} · ~${r['cost']}")
    st.markdown("---")

buf = io.StringIO()
w = csv.writer(buf)
w.writerow(["SKU", "Description"])
for r in results:
    if r["desc"]:
        parts = r["desc"].split("\n\n", 1)
        desc_only = parts[1].strip() if len(parts) == 2 else r["desc"]
        w.writerow([Path(r["name"]).stem, desc_only])
st.download_button(
    "📥 Download SKU + description CSV (demo batch)",
    data=buf.getvalue(),
    file_name="identify_describe_sample.csv",
    mime="text/csv",
)
