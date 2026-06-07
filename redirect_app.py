import streamlit as st

NEW_URL = "https://document-pipeline-demo.streamlit.app/"

st.set_page_config(page_title="Demo has moved", initial_sidebar_state="collapsed")

# Instant redirect (meta refresh fires as soon as the page renders)
st.markdown(
    f'<meta http-equiv="refresh" content="0; url={NEW_URL}">',
    unsafe_allow_html=True,
)

# Fallback for anything that blocks meta refresh
st.markdown(
    f"""
### This demo has moved

You're being redirected to **[document-pipeline-demo.streamlit.app]({NEW_URL})**.

If nothing happens in a second, click the link above.
"""
)
