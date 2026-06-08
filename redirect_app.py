import streamlit as st
import streamlit.components.v1 as components

NEW_URL = "https://document-pipeline-demo.streamlit.app/"

st.set_page_config(page_title="Demo has moved", initial_sidebar_state="collapsed")

# JS redirect. Guard state lives in the IFRAME's own window (same-origin to
# itself) — reading window.parent properties throws cross-origin and kills
# the script, which is what blocked the previous version.
components.html(
    f"""
    <script>
    if (!window.__redirected) {{
        window.__redirected = true;
        try {{
            window.parent.location.replace("{NEW_URL}");
        }} catch (e) {{
            try {{ window.top.location.href = "{NEW_URL}"; }} catch (e2) {{}}
        }}
    }}
    </script>
    """,
    height=0,
)

st.markdown(
    f"""
### This demo has moved

The new address is **[document-pipeline-demo.streamlit.app]({NEW_URL})** — you should be redirected automatically.

If nothing happens in a second, click the link above.
"""
)
