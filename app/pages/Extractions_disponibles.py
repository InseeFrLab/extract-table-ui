import streamlit as st
import numpy as np
from constants import TABLE_TRANSFORMER_CONFIDENCES_PATH, TABLE_TRANSFORMER_EXTRACTIONS_PATH, \
    EXTRACT_TABLE_CONFIDENCES_PATH, EXTRACT_TABLE_EXTRACTIONS_PATH
import pandas as pd
from utils import list_files, disable_button, get_file_system, read_excel_from_s3
from pathlib import Path


st.set_page_config(
    layout="wide",
    page_title="Extractions disponibles",
    page_icon="📊"
)

st.markdown("# Extractions disponibles")
st.sidebar.header("Extractions disponibles")
st.write(
    """
    Liste des extractions disponibles.
    """
)

fs = get_file_system()
table_transformer_tab, extract_table_tab = st.tabs(
    ["Table transformer", "Site ExtractTable"]
)

with table_transformer_tab:
    pass


with extract_table_tab:
    # List available table transformer extractions
    files = list_files(fs=fs, s3_path=EXTRACT_TABLE_EXTRACTIONS_PATH)
    selected_table = st.selectbox(
        label="Tableaux", options=files, on_change=disable_button
    )

    if selected_table:
        # Load pandas DataFrames from xlsx files stored in S3
        extraction_path = Path(EXTRACT_TABLE_EXTRACTIONS_PATH) / selected_table
        confidence_path = Path(EXTRACT_TABLE_CONFIDENCES_PATH) / selected_table

        extraction = read_excel_from_s3(fs, extraction_path)
        extraction.fillna("", inplace=True)
        extraction = extraction.values.tolist()
        extraction = pd.DataFrame(extraction)
        if not fs.exists(confidence_path):
            st.write(
                "No confidence available for this table."
            )
        else:
            confidence = read_excel_from_s3(fs, confidence_path)
            confidence = confidence.values.tolist()
            confidence = pd.DataFrame(confidence).replace(0.0, np.nan)
            extraction = extraction.style.background_gradient(
                axis=None, gmap=confidence, cmap="Reds"
            )
        print(extraction)
        print(type(extraction))
        # Display
        st.dataframe(
            extraction
        )

        # Export button
        st.download_button(
            label="Export",
            data=extraction.to_csv(sep=";").encode("utf_8_sig"),
            file_name=Path(selected_table).with_suffix(".csv"),
            mime="text/csv",
        )
