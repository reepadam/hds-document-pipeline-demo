# Document → Structured Data Pipeline

**Built for the HDS Marketing AI Workflow Architect interview demo.**

A "Swiss army" pipeline that takes any document (typed, handwritten, mixed) and produces structured JSON ready for ERP ingest.

## Architecture

```
Document (PDF/JPG/PNG)
        ↓
Google Cloud Vision API (DOCUMENT_TEXT_DETECTION)
        ↓
Claude Haiku 4.5 (classify + extract structured data, schema-prompted)
        ↓
Structured JSON output + confidence scoring + flagged uncertainties
```

## Supported document types

The pipeline auto-classifies into one of these and produces type-specific structured output:

- `vendor_invoice` — vendor PDF invoices (line items, totals, payment, reconciliation-ready)
- `handwritten_note` — production-floor notes, sales meeting jots, free-form notes
- `mixed_form` — printed forms with handwritten fields
- `order_request` — customer order intake (decoration spec, sizing, in-hands date)
- `logo` — (separate code path) dominant colors, labels, embedded text — for art-file management

## Running locally

```bash
cd C:\Users\Adam\Documents\Claude\Job\demo_app
pip install -r requirements.txt
streamlit run app.py
```

The app will open at `http://localhost:8501`.

## Credentials

Hardcoded paths in `app.py`:
- `C:\Users\Adam\Documents\Claude\Job\cloudvision-497116-3258213b51c0.json` (GCP service account)
- `C:\Users\Adam\Documents\Claude\Job\Anthropic_API.txt` (Anthropic API key)

**Before deploying to Streamlit Community Cloud**, these will move to Streamlit Secrets (not committed to any repo).

## Cost per document

- Cloud Vision: ~$0.0015 per page (1,000 free per month)
- Claude Haiku 4.5: ~$0.0014 per extraction (typical token usage)
- **Total: ~$0.003 per document**

A demo run with 10 sample documents costs about 3 cents.
