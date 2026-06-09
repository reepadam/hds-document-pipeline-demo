"""
Universal Text Extractor - the Swiss army knife.
Now supports: single file, bulk file upload, AND zip file extraction.
Each file gets its own extraction + per-file Claude commentary.
If multiple files are uploaded together, a cross-file "context" summary
runs Claude over the combined output to surface any relationships.
"""
import streamlit as st
import zipfile
from io import BytesIO
from pathlib import Path
from PIL import Image

from pipeline import extract_text_universal, get_universal_context, get_anthropic_client, EXTRACTION_MODEL, svg_to_pil, pdf_to_images
from shared import inject_styles, render_page_header, render_antera_handoff, chat_sidebar

st.set_page_config(page_title="Universal Text Extractor", page_icon=":wrench:", layout="wide")
inject_styles()
render_page_header("🔧 Universal Text Extractor", "Get text from anything. Bulk + zip supported.")
render_antera_handoff(
    "No structured schema, no metrics. Raw 'Swiss army' tool that ingests ANYTHING. "
    "Bulk mode: drop many files OR a zip — each gets its own extraction. If files relate, a cross-file "
    "summary surfaces what they have in common."
)

st.caption(
    "**Accepted:** PDF, JPG, JPEG, PNG, WEBP, GIF, BMP, TIFF, SVG, DOCX, TXT, MD, CSV, JSON, XML, HTML, AI, "
    "or a ZIP containing any combination."
)

uploaded_files = st.file_uploader(
    "Drop one or many files, or a ZIP",
    type=None,
    accept_multiple_files=True,
)

if not uploaded_files:
    st.info("Drop files above. Drag multiple at once, or upload a single ZIP of files.")
    st.stop()


def expand_uploads(files):
    """Walk uploaded files. If any is a zip, extract its contents in-memory.
    Returns list of (display_name, bytes, ext) tuples."""
    out = []
    for f in files:
        name = f.name
        ext = Path(name).suffix.lower()
        data = f.read()
        if ext == ".zip":
            try:
                with zipfile.ZipFile(BytesIO(data)) as zf:
                    for member in zf.namelist():
                        # Skip directories + macOS metadata
                        if member.endswith("/") or "__MACOSX" in member or Path(member).name.startswith("._"):
                            continue
                        inner_bytes = zf.read(member)
                        if not inner_bytes:
                            continue
                        out.append((f"{name}::{Path(member).name}", inner_bytes, Path(member).suffix.lower()))
            except zipfile.BadZipFile:
                st.error(f"`{name}` is not a valid zip file - skipping.")
        else:
            out.append((name, data, ext))
    return out


expanded = expand_uploads(uploaded_files)

if not expanded:
    st.warning("No files found inside the upload (zip may be empty).")
    st.stop()

# Cache key derived from full set
batch_key = "|".join(f"{n}:{len(b)}" for n, b, _ in expanded)
batch_id = str(hash(batch_key))

# Process all files
if st.session_state.get("univ_batch_id") != batch_id:
    st.session_state["univ_batch_id"] = batch_id
    extracted_results = []
    progress = st.progress(0.0, text=f"Processing 0/{len(expanded)}...")
    for i, (name, data, ext) in enumerate(expanded):
        progress.progress((i + 0.5) / len(expanded), text=f"Processing {i+1}/{len(expanded)}: {name}")
        try:
            text, method = extract_text_universal(data, ext)
        except Exception as e:
            text, method = "", f"Error: {type(e).__name__}: {e}"
        ctx = None
        if text.strip():
            try:
                ctx = get_universal_context(text, name, method)
            except Exception as e:
                ctx = {"analysis": f"_(Claude analysis failed: {e})_", "_meta": {}}
        extracted_results.append({
            "name": name, "bytes": data, "ext": ext,
            "text": text, "method": method, "context": ctx,
        })
        progress.progress((i + 1) / len(expanded), text=f"Processing {i+1}/{len(expanded)}: {name}")
    progress.empty()
    st.session_state["univ_extracted"] = extracted_results
else:
    extracted_results = st.session_state["univ_extracted"]

# Top metrics
total_chars = sum(len(r["text"]) for r in extracted_results)
ok_count = sum(1 for r in extracted_results if r["text"].strip())
mcols = st.columns(4)
mcols[0].metric("Files processed", len(extracted_results))
mcols[1].metric("Successful extractions", ok_count)
mcols[2].metric("Failed / empty", len(extracted_results) - ok_count)
mcols[3].metric("Total chars extracted", f"{total_chars:,}")

# Cross-file context summary if multiple
if len(extracted_results) > 1 and ok_count > 1:
    st.markdown("---")
    st.subheader("🤖 Cross-file context")
    st.caption("Claude reviews ALL files together and surfaces what they have in common (if anything).")

    cross_key = f"_cross_{batch_id}"
    if cross_key not in st.session_state:
        with st.spinner("Looking for relationships across files..."):
            try:
                client = get_anthropic_client()
                # Build a compact summary of each file's content
                snippets = []
                for r in extracted_results:
                    if not r["text"].strip():
                        continue
                    snippet = r["text"][:1500]
                    snippets.append(f"=== {r['name']} ({r['method']}) ===\n{snippet}")
                combined = "\n\n".join(snippets)[:30000]
                cross_prompt = f"""You are reviewing {ok_count} files that a user uploaded together.

Each file's text appears below. Determine:

1. Are these files related? (yes/no/partially - explain in one sentence)
2. If related: what is the common context, topic, or workflow? (1-2 sentences)
3. If related: list 3-5 cross-file observations or patterns (specific to THIS content, not generic).
4. If not related: just say "These files appear unrelated - {ok_count} independent documents."

Plain prose, no markdown headers, under 200 words total.

FILES:
{combined}"""
                msg = client.messages.create(
                    model=EXTRACTION_MODEL, max_tokens=600,
                    messages=[{"role": "user", "content": cross_prompt}],
                )
                st.session_state[cross_key] = {
                    "analysis": msg.content[0].text.strip(),
                    "tokens_in": msg.usage.input_tokens,
                    "tokens_out": msg.usage.output_tokens,
                    "cost": round(msg.usage.input_tokens * 0.0000008 + msg.usage.output_tokens * 0.000004, 4),
                }
            except Exception as e:
                st.session_state[cross_key] = {"analysis": f"_(Cross-file analysis failed: {e})_", "tokens_in": 0, "tokens_out": 0, "cost": 0}

    cross = st.session_state[cross_key]
    st.markdown(cross["analysis"])
    st.caption(f"Tokens: {cross.get('tokens_in','?')}→{cross.get('tokens_out','?')} · Cost: ~${cross.get('cost','?')}")

# Per-file expandable sections
st.markdown("---")
st.subheader("Per-file details")
st.caption("Click any file to see its extracted text + Claude's contextual notes.")

for i, r in enumerate(extracted_results):
    label = f"📄 {r['name']} · {len(r['text']):,} chars · `{r['method']}`"
    with st.expander(label, expanded=(len(extracted_results) <= 3)):
        if not r["text"].strip():
            st.warning(f"No text extracted. Method tried: {r['method']}")
            continue

        # Preview thumbnail if possible
        preview = None
        try:
            if r["ext"] in (".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff", ".tif"):
                preview = Image.open(BytesIO(r["bytes"]))
            elif r["ext"] == ".svg":
                preview = svg_to_pil(r["bytes"])
            elif r["ext"] in (".pdf", ".ai"):
                pages = pdf_to_images(r["bytes"])
                if pages:
                    preview = pages[0]
        except Exception:
            preview = None

        text_col, ai_col = st.columns([1.2, 1])
        with text_col:
            if preview is not None:
                pcol, _ = st.columns([1, 3])
                with pcol:
                    st.image(preview, use_container_width=True)
            st.code(r["text"], language="text")
        with ai_col:
            ctx = r["context"] or {}
            analysis = ctx.get("analysis", "")
            if analysis:
                st.markdown(analysis)
            meta = ctx.get("_meta", {})
            if meta:
                st.caption(f"Tokens: {meta.get('tokens_in','?')}→{meta.get('tokens_out','?')} · ~${meta.get('approx_cost_usd','?')}")
            st.download_button(
                f"Download extracted text",
                data=r["text"],
                file_name=f"{Path(r['name'].replace('::', '_')).stem}_extracted.txt",
                mime="text/plain",
                key=f"dl_{i}",
            )

# Combined batch download
st.markdown("---")
combined_parts = []
for r in extracted_results:
    combined_parts.append(f"========= FILE: {r['name']} =========")
    combined_parts.append(f"Method: {r['method']}")
    combined_parts.append(f"Chars: {len(r['text']):,}")
    if r["context"] and r["context"].get("analysis"):
        combined_parts.append("\n--- Claude notes ---")
        combined_parts.append(r["context"]["analysis"])
    combined_parts.append("\n--- Extracted text ---")
    combined_parts.append(r["text"] or "(empty)")
    combined_parts.append("")
batch_report = "\n".join(combined_parts)

st.download_button(
    "📥 Download batch report (all files combined .txt)",
    data=batch_report,
    file_name=f"batch_extraction_{ok_count}_files.txt",
    mime="text/plain",
)
