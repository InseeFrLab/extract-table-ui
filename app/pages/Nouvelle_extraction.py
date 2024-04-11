"""
Page for new extractions.
"""

import streamlit as st
from ca_query.querier import DocumentQuerier
import os
from utils import (
    get_detector,
    get_page_selector,
    get_file_system,
    check_siren_length,
    check_availability,
    download_pdf,
    upload_pdf_to_s3,
    read_pdf_from_s3,
    get_extractor,
    extract_table,
    sidebar_content,
)
from constants import PDF_SAMPLES_PATH, TABLE_TRANSFORMER_EXTRACTIONS_PATH, EXTRACT_TABLE_EXTRACTIONS_PATH, EXTRACT_TABLE_CONFIDENCES_PATH
import fitz
from ca_extract.extraction.table_transformer.utils import format_df_for_comparison


st.set_page_config(layout="wide", page_title="Nouvelle extraction", page_icon="📊")

st.markdown("# Nouvelle extraction")
st.sidebar.header("Nouvelle extraction")
sidebar_content()
st.write(
    """
    Page de lancement d'une nouvelle extraction.
    """
)

# Initialize cached resources
fs = get_file_system()
# Document querier - requires user name and password
# TODO: let user input their credentials
document_querier = DocumentQuerier(
    os.environ["TEST_INPI_USERNAME"], os.environ["TEST_INPI_PASSWORD"]
)
page_selector = get_page_selector()
# Table transformer extraction
detector = get_detector()
extractor = get_extractor()

# Allow users to input year
year = st.text_area(
    label="Entrez l'année pour laquelle vous souhaitez vérifier "
    "la disponibilité du document",
    value="2021",
    max_chars=4,
)

# Allow users to input multiple document IDs
company_ids = st.text_area("Entrez les numéros Siren (séparés d'un espace):")
# Split the user input into a list of document IDs
company_ids = company_ids.split()

# Add a button to check availability for all specified documents
dispo_button = st.button("Vérifier la disponibilité")
if not st.session_state.get("button"):
    st.session_state["button"] = dispo_button

if st.session_state["button"]:
    try:
        year = int(year)
    except ValueError:
        st.error("Année non valide.")

    if isinstance(year, int):
        for company_id in company_ids:
            if not check_siren_length(company_id):
                st.error(
                    f"Le numéro Siren {company_id} ne contient " f"pas 9 caractères."
                )
            else:
                availability, document_id = check_availability(
                    document_querier, company_id, year
                )

                if availability:
                    file_name = f"CA_{company_id}_{year}.pdf"
                    # Display the availability status for each document
                    st.write(f"Document disponible pour le " f"Siren {company_id}.")

                    PDFbyte = download_pdf(document_querier, document_id)
                    st.download_button(
                        label="Comptes annuels",
                        data=PDFbyte,
                        file_name=file_name,
                        mime="application/octet-stream",
                    )

                    selection_button = st.button(
                        "Identification de la page d'intérêt",
                        key=f"page_selection_btn_{company_id}_{year}",
                    )
                    if not st.session_state.get(f"selection_button_{company_id}_{year}"):
                        st.session_state[f"selection_button_{company_id}_{year}"] = selection_button
                    if st.session_state[f"selection_button_{company_id}_{year}"]:
                        try:
                            s3_path = os.path.join(
                                PDF_SAMPLES_PATH, f"{company_id}_{year}.pdf"
                            )
                            # Check if selected page file is already persisted
                            if fs.exists(s3_path):
                                document = read_pdf_from_s3(fs, s3_path)
                            # Else run page selection and persist the selected page
                            else:
                                document = fitz.open(stream=PDFbyte, filetype="pdf")
                                # TODO: There can be multiple pages sometimes
                                # TODO: implement this possibility
                                page_number = page_selector.get_page_number(document)
                                st.write(
                                    f"Un tableau filiales et participations a été "
                                    f"repéré à la page {page_number + 1}."
                                )
                                document.select([page_number])
                                # Save to persistent storage
                                upload_pdf_to_s3(
                                    document=document, fs=fs, s3_path=s3_path
                                )

                            table_transformer_tab, extract_table_tab = st.tabs(
                                ["Table transformer", "Site ExtractTable"]
                            )

                            # Detection
                            with table_transformer_tab:
                                extraction_button = st.button(
                                    "Extraction des tableaux",
                                    key=f"extraction_btn_{company_id}_{year}",
                                )
                                text_placeholder = st.empty()
                                if not st.session_state.get(f"extraction_btn_{company_id}_{year}_state"):
                                    st.session_state[f"extraction_btn_{company_id}_{year}_state"] = (
                                        extraction_button
                                    )
                                if st.session_state[f"extraction_btn_{company_id}_{year}_state"]:
                                    extraction_s3_path = os.path.join(
                                        TABLE_TRANSFORMER_EXTRACTIONS_PATH,
                                        f"{company_id}_{year}",
                                    )
                                    if fs.exists(extraction_s3_path):
                                        text_placeholder.write(
                                            "L'extraction existe déjà: "
                                            "accédez-y grâce à l'onglet 'Extractions disponibles'."
                                        )
                                    else:
                                        text_placeholder.write("Extraction en cours...")
                                        # Detection
                                        crops = detector.detect(document)
                                        # Extraction
                                        for table_idx, crop in enumerate(crops):
                                            df, _ = extractor.extract(crop)
                                            df = format_df_for_comparison(df)
                                            # Save to persistent storage
                                            with fs.open(
                                                os.path.join(
                                                    extraction_s3_path,
                                                    f"table_{table_idx}.csv",
                                                ),
                                                "wb",
                                            ) as f:
                                                df.to_csv(f)
                                        text_placeholder.write(
                                            f"Extraction de {len(crops)} effectuée: "
                                            f"accédez-y grâce à l'onglet 'Extractions disponibles'."
                                        )

                            with extract_table_tab:
                                # ExtractTable extraction
                                extract_table_button = st.button(
                                    "Extraction des tableaux",
                                    key=f"extract_table_btn_{company_id}_{year}",
                                )
                                text_placeholder = st.empty()
                                if not st.session_state.get(f"extract_table_btn_{company_id}_{year}_state"):
                                    st.session_state[f"extract_table_btn_{company_id}_{year}_state"] = (
                                        extract_table_button
                                    )
                                if st.session_state[f"extract_table_btn_{company_id}_{year}_state"]:
                                    extract_table_s3_path = os.path.join(
                                        EXTRACT_TABLE_EXTRACTIONS_PATH,
                                        f"{company_id}_{year}",
                                    )
                                    extract_table_confidence_s3_path = os.path.join(
                                        EXTRACT_TABLE_CONFIDENCES_PATH,
                                        f"{company_id}_{year}",
                                    )
                                    if fs.exists(extract_table_s3_path):
                                        text_placeholder.write(
                                            "L'extraction existe déjà: "
                                            "accédez-y grâce à l'onglet 'Extractions disponibles'."
                                        )
                                    else:
                                        text_placeholder.write("Extraction en cours...")
                                        outputs = extract_table(document)
                                        for table_idx, (df, df_conf) in enumerate(outputs):
                                            # Save as excel file
                                            with fs.open(
                                                os.path.join(
                                                    extract_table_s3_path,
                                                    f"table_{table_idx}.xlsx",
                                                ),
                                                "wb",
                                            ) as f:
                                                df.to_excel(f)
                                            # Save confidences
                                            if df_conf is not None:
                                                with fs.open(
                                                    os.path.join(
                                                        extract_table_confidence_s3_path,
                                                        f"table_{table_idx}.xlsx",
                                                    ),
                                                    "wb",
                                                ) as f:
                                                    df_conf.to_excel(f)
                                        text_placeholder.write(
                                            f"Extraction de {len(outputs)} tableaux effectuée: "
                                            f"accédez-y grâce à l'onglet 'Extractions disponibles'."
                                        )
                        except ValueError as e:
                            # Print error message.
                            st.write(str(e))
