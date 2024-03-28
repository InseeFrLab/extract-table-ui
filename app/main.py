"""
Dashboard app.
"""

import os
from pathlib import Path
import tempfile
import streamlit as st
from ca_query.querier import DocumentQuerier
from utils import (
    check_siren_length,
    get_detector,
    get_extractor,
    get_page_selector,
)
from ca_extract.extraction.table_transformer.utils import format_df_for_comparison
import fitz


@st.cache_data
def check_availability(_document_querier, company_id, year):
    try:
        # Make an API request to check availability for each document
        availability, document_id = document_querier.check_document_availability(
            company_id, year
        )
    except KeyError:
        # KeyError lorsque pas de clé "bilans" pour le SIREN
        # TODO: différence entre SIREN qui n'existe pas et SIREN qui existe ?
        # Retour 404 vs. 200, plutôt que catch la KeyError
        availability = False
        document_id = None
    # TODO: update token if necessary ?
    return availability, document_id


@st.cache_data
def download_pdf(_document_querier, document_id):
    with tempfile.TemporaryDirectory() as tmpdirname:
        tmp_dir = Path(tmpdirname)
        tmp_file_path = tmp_dir / "tmp.pdf"
        document_querier.download_from_id(
            document_id, save_path=tmp_file_path, s3=False
        )

        with open(tmp_file_path, "rb") as pdf_file:
            PDFbyte = pdf_file.read()
        # Also return fitz Document ? Probleme can't cache
    if len(PDFbyte) < 10000:
        print(PDFbyte)
    return PDFbyte


# Create the Streamlit app
st.title("Récupération des comptes sociaux")

# Document querier
document_querier = DocumentQuerier(
    os.environ["TEST_INPI_USERNAME"], os.environ["TEST_INPI_PASSWORD"]
)
detector = get_detector()
extractor = get_extractor()
page_selector = get_page_selector()

# Allow users to input year
year = st.text_area(
    label="Entrez l'année pour laquelle vous souhaitez vérifier"
    "la disponibilité du document",
    value="2021",
    max_chars=4,
)

# Allow users to input multiple document IDs
company_ids = st.text_area("Entrez les numéros Siren (un par ligne):")
# Split the user input into a list of document IDs
company_ids = company_ids.split("\n")

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
        for idx, company_id in enumerate(company_ids):
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
                    if st.button("Extraction", key=f"extraction_btn_{idx}"):
                        try:
                            document = fitz.open(stream=PDFbyte, filetype="pdf")
                            # There can be multiple pages sometimes
                            page_number = page_selector.get_page_number(document)
                            st.write(
                                f"Un tableau filiales et participations a été "
                                f"repéré à la page {page_number + 1}."
                            )
                            document.select([page_number])
                            # Detection
                            crops = detector.detect(document)
                            # Extraction
                            for table_idx, crop in enumerate(crops):
                                df, _ = extractor.extract(crop)
                                df = format_df_for_comparison(df)
                                st.dataframe(df)
                        except ValueError as e:
                            st.write(str(e))
                else:
                    st.write(f"Document indisponible pour le " f"Siren {company_id}.")
