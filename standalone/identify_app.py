"""
Identify & Describe - standalone, brand-free, gated, usage-capped single-image tool.
Easter egg: only visitors with the right ?key= get in. Hard cap of MAX_USES images
(durable, via Cloudflare D1) protects the API account from over-use.
Upload one image -> Tesseract OCR (free) + Claude vision (reads OCR as a hint,
names what/who is depicted) -> listing description.
"""
import base64
import json as _json
from io import BytesIO
from urllib import request as _urlreq

import streamlit as st
from PIL import Image
import anthropic

try:
    import pytesseract
except Exception:
    pytesseract = None

MODEL = "claude-haiku-4-5"
MAX_DIM = 1024
MAX_USES = 20
IN_RATE = 0.000001
OUT_RATE = 0.000005
IMG_EXTS = ["jpg", "jpeg", "png", "webp", "gif", "bmp", "tiff", "tif"]

PROMPT = (
    "You are a cataloging assistant. Identify the item in this photo as specifically as you can, using "
    "your knowledge. For currency, coins, stamps, books, art, or memorabilia: name the country, "
    "denomination, year or series, and especially WHO or WHAT is depicted - the person in a portrait "
    "(monarch, president, historical figure), the building, monument, or scene. Name them when you "
    "recognize them. Then write a 40-60 word description for a marketplace listing that includes those "
    "specifics. Be accurate: if you are not confident about an identification, say so rather than "
    "inventing it. Do NOT state condition, grade, authenticity, or monetary value unless it is printed "
    "on the item. Format: line 1 = a short identification; then a blank line; then the description. No "
    "markdown, no preamble."
)

st.set_page_config(page_title="Identify & Describe", page_icon=":mag:", layout="wide")


def _gate():
    try:
        expected = st.secrets.get("access_token", "")
    except Exception:
        expected = ""
    if not expected:
        return
    if st.query_params.get("key", "") == expected:
        return
    st.stop()


_gate()


@st.cache_resource
def _usage_counter():
    # Per-instance fallback only (resets on sleep/redeploy). Used when D1 isn't configured.
    return {"n": 0}


def _d1_cfg():
    try:
        acct = st.secrets.get("cf_account_id", "")
        db = st.secrets.get("cf_d1_db_id", "")
        tok = st.secrets.get("cf_api_token", "")
    except Exception:
        return None
    return (acct, db, tok) if (acct and db and tok) else None


def _d1_query(sql, params=None):
    cfg = _d1_cfg()
    if not cfg:
        return None
    acct, db, tok = cfg
    url = f"https://api.cloudflare.com/client/v4/accounts/{acct}/d1/database/{db}/query"
    body = _json.dumps({"sql": sql, "params": params or []}).encode()
    req = _urlreq.Request(
        url, data=body, method="POST",
        headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"},
    )
    with _urlreq.urlopen(req, timeout=15) as resp:
        return _json.loads(resp.read().decode())


def _try_consume():
    """Durable cap via Cloudflare D1. Atomically claims one use if under MAX_USES.
    Returns (True, n) if allowed, (False, n) if capped, or (None, None) if D1 not configured."""
    if not _d1_cfg():
        return None, None
    res = _d1_query(
        "UPDATE counter SET n = n + 1 WHERE id = 1 AND n < ? RETURNING n", [MAX_USES]
    )
    rows = (res or {}).get("result", [{}])[0].get("results", [])
    if rows:
        return True, rows[0]["n"]
    cur = _d1_query("SELECT n FROM counter WHERE id = 1")
    n = (cur or {}).get("result", [{}])[0].get("results", [{}])[0].get("n", MAX_USES)
    return False, n


def get_key():
    try:
        return st.secrets["anthropic_api_key"]
    except Exception:
        import os
        return os.environ.get("ANTHROPIC_API_KEY", "")


def run_ocr(image_bytes):
    if not pytesseract:
        return ""
    try:
        return pytesseract.image_to_string(Image.open(BytesIO(image_bytes))).strip()
    except Exception:
        return ""


def describe(image_bytes, ocr_hint):
    img = Image.open(BytesIO(image_bytes))
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    img.thumbnail((MAX_DIM, MAX_DIM))
    buf = BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.standard_b64encode(buf.getvalue()).decode("utf-8")
    text = PROMPT
    if ocr_hint:
        text += "\n\nText detected on the item (OCR, may be imperfect - use as a hint, defer to the image):\n" + ocr_hint[:2000]
    client = anthropic.Anthropic(api_key=get_key())
    msg = client.messages.create(
        model=MODEL,
        max_tokens=500,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b64}},
                {"type": "text", "text": text},
            ],
        }],
    )
    cost = round(msg.usage.input_tokens * IN_RATE + msg.usage.output_tokens * OUT_RATE, 4)
    return msg.content[0].text.strip(), msg.usage.input_tokens, msg.usage.output_tokens, cost


st.title("Identify & Describe")
st.caption(
    "Upload one image. It identifies the item - including who or what is depicted - and writes a listing "
    "description. Raw OCR is shown alongside so you can see why OCR alone can't do this."
)

up = st.file_uploader("Upload an image", type=IMG_EXTS, accept_multiple_files=False)
if not up:
    st.stop()

data = up.read()
sig = f"{up.name}:{len(data)}"

if st.session_state.get("idd_sig") != sig:
    allowed, used = _try_consume()
    if allowed is None:
        # D1 not configured yet - fall back to per-instance counter.
        counter = _usage_counter()
        if counter["n"] >= MAX_USES:
            st.warning("This preview has reached its usage limit. Reach out for full, unlimited access.")
            st.stop()
        counter["n"] += 1
    elif not allowed:
        st.warning("This preview has reached its usage limit. Reach out for full, unlimited access.")
        st.stop()
    with st.spinner("Looking..."):
        ocr = run_ocr(data)
        try:
            desc, tin, tout, cost = describe(data, ocr)
            err = None
        except Exception as e:
            desc, tin, tout, cost, err = "", 0, 0, 0, f"{type(e).__name__}: {e}"
    st.session_state["idd_sig"] = sig
    st.session_state["idd_res"] = (ocr, desc, tin, tout, cost, err)

ocr, desc, tin, tout, cost, err = st.session_state["idd_res"]

img_col, ocr_col, ai_col = st.columns([1, 1, 1.6])
with img_col:
    st.image(Image.open(BytesIO(data)), use_container_width=True)
    st.caption(up.name)
with ocr_col:
    st.markdown("**OCR sees (text only)**")
    st.code(ocr or "(no readable text)", language="text")
with ai_col:
    st.markdown("**Vision identifies + describes**")
    if err:
        st.error(err)
    else:
        st.write(desc)
        st.caption(f"Tokens {tin} to {tout} - ~${cost}")
        st.download_button("Download description (.txt)", data=desc, file_name="description.txt", mime="text/plain")
