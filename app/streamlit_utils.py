"""
Streamlit utilities.
"""
import streamlit as st
from s3fs import S3FileSystem
import base64
from utils import get_extract_table_credits


def disable_button():
    """
    Disable button.
    """
    st.session_state["disable"] = True


def display_pdf(fs: S3FileSystem, s3_path: str):
    """
    Display PDF.

    Args:
        fs (S3FileSystem): S3 file system.
        s3_path (str): S3 path.
    """
    with fs.open(s3_path, "rb") as f:
        base64_pdf = base64.b64encode(f.read()).decode("utf-8")

    # Embed PDF in HTML
    pdf_display = f'<embed id="pdfViewer" src="data:application/pdf;base64,{base64_pdf}" width="700" height="1000" type="application/pdf">'

    # Display file
    return st.markdown(pdf_display, unsafe_allow_html=True)


def sidebar_content():
    """
    Add side bar content for ExtractTable authentication.
    """
    if "auth_token" not in st.session_state:
        st.session_state.auth_token = None
    token = st.sidebar.text_input("ExtractTable token", type="password", key="token")
    if st.sidebar.button("Authentification - crédits"):
        if token:
            st.session_state.auth_token = token
            remaining_credits = get_extract_table_credits(token)
            st.sidebar.write(f"Crédits restants: {remaining_credits}")
