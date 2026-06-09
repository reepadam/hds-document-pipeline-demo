# Identify & Describe (gated standalone)

Single-image vision tool, brand-free, hidden behind an access key. Deploys as a
SECOND Streamlit app from THIS SAME repo (already connected), so PUSH_STREAMLIT.bat
ships it. Because the main file lives in this subfolder (no pages/ here), it shows
ONLY this tool — no link to the demo's other modules.

Deploy once (separate URL):
1. share.streamlit.io -> New app -> same repo/branch.
2. Main file path: `standalone/identify_app.py`
3. Settings -> Secrets:
       anthropic_api_key = "sk-ant-..."
       access_token = "pick-a-secret"
       # Durable 20-use cap (optional but recommended; without these it
       # falls back to a per-instance counter that resets when the app sleeps):
       cf_account_id  = "your-cloudflare-account-id"
       cf_d1_db_id    = "1c40a5f3-d0b2-4930-981c-054d1b2c74c6"   # idd-usage
       cf_api_token   = "cloudflare-token-with-D1-edit"
4. Deploy. Share the link as  https://<app>.streamlit.app/?key=pick-a-secret
   (no key -> blank page). packages.txt installs Tesseract automatically.

## Durable usage cap (Cloudflare D1)
The hard cap of 20 lifetime uses is enforced against a Cloudflare D1 database
("idd-usage", db id 1c40a5f3-d0b2-4930-981c-054d1b2c74c6, table `counter`,
seeded at n=0). Each new image atomically runs
`UPDATE counter SET n=n+1 WHERE id=1 AND n<20 RETURNING n` — a returned row means
allowed, an empty result means capped. This survives app restarts/redeploys, unlike
the in-memory fallback. To reset the count: run `UPDATE counter SET n=0 WHERE id=1`.
You provide a Cloudflare API token (scoped to D1:Edit) + your account id in Secrets;
the db id is already filled in above.
