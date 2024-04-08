import streamlit as st

st.set_page_config(
    layout="wide",
    page_title="Accueil",
    page_icon="👋",
)

st.write("# Application")

st.markdown(
    """
    Récupération des comptes annuels des entreprises et extraction
    du tableau des filiales et participations.
    """
)
