import streamlit as st
import numpy as np
from constants import (
    TABLE_TRANSFORMER_EXTRACTIONS_PATH,
    PDF_SAMPLES_PATH,
    EXTRACT_TABLE_CONFIDENCES_PATH,
    EXTRACT_TABLE_EXTRACTIONS_PATH,
)
import pandas as pd
from utils import (
    list_files,
    disable_button,
    get_file_system,
    read_excel_from_s3,
    display_pdf,
    format_extraction_name,
)
from pathlib import Path


st.set_page_config(layout="wide", page_title="Extractions disponibles", page_icon="📊")

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
    file_paths = list_files(fs=fs, s3_path=TABLE_TRANSFORMER_EXTRACTIONS_PATH)
    selected_transformed_table = st.selectbox(
        label="Documents",
        options=file_paths,
        format_func=format_extraction_name,
        on_change=disable_button,
    )
    if selected_transformed_table:
        # Load pandas DataFrames from xlsx files stored in S3
        pdf_sample_path = (
            str(Path(PDF_SAMPLES_PATH) / selected_transformed_table.split("/")[-2])
            + ".pdf"
        )
        with fs.open(selected_transformed_table, "rb") as f:
            extraction = pd.read_csv(f)

        # Export button
        st.download_button(
            label="Exporter l'extraction en .csv",
            data=extraction.to_csv(sep=";").encode("utf_8_sig"),
            file_name=Path(format_extraction_name(selected_transformed_table))
            .with_suffix(".csv")
            .name,
            mime="text/csv",
            key="table_transformer_export_button",
        )

        col1, col2 = st.columns(2)
        with col1:
            # Display extraction
            st.dataframe(
                extraction, height=800, use_container_width=True, hide_index=False
            )
        with col2:
            # Display PDF
            display_pdf(fs=fs, s3_path=pdf_sample_path)


with extract_table_tab:
    # List available table transformer extractions
    extract_table_files = list_files(fs=fs, s3_path=EXTRACT_TABLE_EXTRACTIONS_PATH)
    selected_extracted_table = st.selectbox(
        label="Tableaux",
        options=extract_table_files,
        format_func=format_extraction_name,
        on_change=disable_button,
    )

    if selected_extracted_table:
        # Load pandas DataFrames from xlsx files stored in S3
        path_suffix = "/".join((selected_extracted_table.split("/"))[-2:])
        confidence_path = str(Path(EXTRACT_TABLE_CONFIDENCES_PATH) / path_suffix)
        pdf_sample_path = (
            str(Path(PDF_SAMPLES_PATH) / selected_extracted_table.split("/")[-2])
            + ".pdf"
        )

        extraction = read_excel_from_s3(fs, selected_extracted_table)
        extraction.fillna("", inplace=True)
        extraction = extraction.values.tolist()
        extraction = pd.DataFrame(extraction)
        if not fs.exists(confidence_path):
            styled_extraction = extraction
            st.write("No confidence available for this table.")
        else:
            confidence = read_excel_from_s3(fs, confidence_path)
            confidence = confidence.values.tolist()
            confidence = pd.DataFrame(confidence).replace(0.0, np.nan)
            styled_extraction = extraction.style.background_gradient(
                axis=None, gmap=confidence, cmap="Reds"
            )
            st.write(
                f"Valeurs de confiance = [{confidence.min(axis=None)} - {confidence.max(axis=None)}]"
            )

        # Export button
        st.download_button(
            label="Exporter l'extraction en .csv",
            data=extraction.to_csv(sep=";").encode("utf_8_sig"),
            file_name=Path(format_extraction_name(selected_transformed_table))
            .with_suffix(".csv")
            .name,
            mime="text/csv",
            key="extract_table_export_button",
        )

        col1, col2 = st.columns(2)
        with col1:
            # Display extraction
            st.dataframe(
                styled_extraction,
                height=800,
                use_container_width=True,
                hide_index=False,
            )
        with col2:
            # Display PDF
            display_pdf(fs=fs, s3_path=pdf_sample_path)
