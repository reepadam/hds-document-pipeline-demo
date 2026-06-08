import streamlit as st
import streamlit.components.v1 as components

NEW_URL = "https://document-pipeline-demo.streamlit.app/"

st.set_page_config(page_title="Demo has moved", initial_sidebar_state="collapsed")

# JavaScript redirect — one-shot, guarded so it can never loop
components.html(
    f"""
    <script>
    if (!window.parent.__redirected) {{
        window.parent.__redirected = true;
        window.parent.location.replace("{NEW_URL}");
    }}
    </script>
    """,
    height=0,
)

# Manual fallback
st.markdown(
    f"""
### This demo has moved

The new address is **[document-pipeline-demo.streamlit.app]({NEW_URL})** — you should be redirected automatically.

If nothing happens in a second, click the link above.
"""
)
