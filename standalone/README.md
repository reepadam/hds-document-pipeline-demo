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
4. Deploy. Share the link as  https://<app>.streamlit.app/?key=pick-a-secret
   (no key -> blank page). packages.txt installs Tesseract automatically.
