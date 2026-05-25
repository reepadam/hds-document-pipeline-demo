# Deploy to Streamlit Community Cloud + CNAME at GoDaddy

This is the runbook for taking the demo from localhost to a public URL at
`demo.adamjreep.com` (or whatever subdomain). End-to-end takes ~30 min.

## 1. Prep the repo (5 min)

```
cd C:\Users\Adam\Documents\Claude\Job\demo_app
git init
git add .
git status     # CONFIRM no creds in the staged list - .gitignore should exclude them
git commit -m "Initial demo for HDS interview"
```

**Double-check before pushing**: run `git ls-files` and confirm there is no
`cloudvision-*.json`, no `Anthropic_API.txt`, no `secrets.toml`. If any appear,
add them to .gitignore and `git rm --cached <file>`.

## 2. Push to GitHub (5 min)

1. Go to github.com and create a new **public** repo (Streamlit Community Cloud
   requires public for free tier). Suggested name: `hds-document-pipeline-demo`.
2. Don't init with README - we already have one.
3. Back in the local repo:
   ```
   git remote add origin https://github.com/adamjreep/hds-document-pipeline-demo.git
   git branch -M main
   git push -u origin main
   ```

## 3. Deploy to Streamlit Community Cloud (10 min)

1. Go to https://share.streamlit.io
2. Sign in with your GitHub account
3. Click **"New app"** → "From existing repo"
4. Repository: `adamjreep/hds-document-pipeline-demo`
5. Branch: `main`
6. Main file path: `Home.py`
7. App URL: pick something memorable like `hds-demo-adamreep` (you'll get
   `hds-demo-adamreep.streamlit.app` automatically)
8. Click **"Deploy"** - it'll build for 2-3 min

## 4. Add secrets (5 min)

While deploying, click **"Manage app"** → **"Settings"** → **"Secrets"**.

Paste the contents of `.streamlit/secrets.toml.example` and fill in real values:

- `anthropic_api_key`: contents of `C:\Users\Adam\Documents\Claude\Job\Anthropic_API.txt`
- `[gcp_service_account]`: every field from
  `C:\Users\Adam\Documents\Claude\Job\cloudvision-497116-3258213b51c0.json`

Save. Streamlit Cloud will redeploy automatically with the secrets injected.

## 5. Verify (2 min)

Open `https://hds-demo-adamreep.streamlit.app` (or whatever URL you got).
Test each module:
- Home loads with 9 module cards
- Customer Library shows 16 customers with logos
- Universal Text Extractor accepts a file
- Receipts shows the Antera Jobs dropdown
- Reporting shows the queue counts (0 each on first run)

If anything errors, click "Manage app" → "View logs" to debug.

## 6. CNAME at GoDaddy (5 min)

In your GoDaddy DNS panel for `adamjreep.com`:

1. Add a **CNAME** record:
   - Name: `demo` (so the final URL is `demo.adamjreep.com`)
   - Value/Target: `hds-demo-adamreep.streamlit.app` (the Streamlit Cloud URL,
     WITHOUT https://)
   - TTL: 600 (10 min - default 1 hour is fine too)

2. Save.

3. Back in Streamlit Cloud → **Settings** → **Custom domain** → enter
   `demo.adamjreep.com`. Streamlit will provision the cert and confirm
   when ready (usually ~5 min after CNAME propagates).

4. Test https://demo.adamjreep.com - should serve the same app.

## 7. After deploy: things to remember

- Edits to Home.py / pages/*.py auto-deploy when you `git push`. No manual
  redeploy needed.
- Secrets edits in Streamlit Cloud dashboard trigger an immediate redeploy.
- `customer_data/` is excluded from git, so the seeded customers WILL NOT
  appear on the deployed site by default. Either:
  - Commit the customer_data directory (remove from .gitignore) so seeded
    data ships with the app. Recommended for the demo.
  - OR run `python seed_demo_data.py` from a Streamlit Cloud "advanced" shell
    (not possible on free tier - so just commit the data).

To commit the customer data:
```
# In .gitignore, change:
#   customer_data/
# to:
#   customer_data/_queues/    # (so accepted queues don't bloat git)
git add customer_data/
git commit -m "Seed demo customer data (16 HDS clients, 160 orders, logos)"
git push
```

## Known gotchas

- **PDF generation**: reportlab works fine on Streamlit Cloud.
- **SVG rasterization**: svglib + reportlab need no system deps.
- **pypdfium2**: ships its own binaries, no system deps needed.
- **Google Cloud Vision**: works as long as secrets are correctly pasted.
  The `private_key` field must include the literal `-----BEGIN PRIVATE KEY-----`
  and `-----END PRIVATE KEY-----` lines plus newlines (use the triple-quoted
  TOML string format in secrets.toml.example).
