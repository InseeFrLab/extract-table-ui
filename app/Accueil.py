import os
import streamlit as st


st.set_page_config(
    layout="wide",
    page_title="Accueil",
    page_icon="👋",
)
st.write("# Application")

version_number = os.getenv("DEPLOYMENT_VERSION", "latest")

st.markdown(
    f"""
    Récupération des comptes annuels des entreprises et extraction
    du tableau des filiales et participations. Version {version_number} de l'application
    """
)
