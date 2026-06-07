import streamlit as st
import streamlit.components.v1 as components

NEW_URL = "https://document-pipeline-demo.streamlit.app/"

st.set_page_config(page_title="Demo has moved", initial_sidebar_state="collapsed")

# JavaScript redirect — the reliable method in Streamlit (meta tags injected
# into the body after load are ignored by modern browsers)
components.html(
    f'<script>window.parent.location.replace("{NEW_URL}");</script>',
    height=0,
)

# Meta refresh as a backup
st.markdown(
    f'<meta http-equiv="refresh" content="0; url={NEW_URL}">',
    unsafe_allow_html=True,
)

# Manual fallback
st.markdown(
    f"""
### This demo has moved

You're being redirected to **[document-pipeline-demo.streamlit.app]({NEW_URL})**.

If nothing happens in a second, click the link above.
"""
)
