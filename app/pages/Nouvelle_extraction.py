"""
Page for new extractions.
"""

import streamlit as st
from ca_query.querier import DocumentQuerier
import os
from utils import (
    check_siren_length,
    check_availability,
    download_pdf,
    get_file_system,
    read_pdf_from_s3,
    upload_pdf_to_s3,
)
from extraction import extract_tables, extract_tables_transformer
from streamlit_utils import sidebar_content
import requests
from constants import (
    PDF_SAMPLES_PATH,
    TABLE_TRANSFORMER_EXTRACTIONS_PATH,
    EXTRACT_TABLE_EXTRACTIONS_PATH,
    EXTRACT_TABLE_CONFIDENCES_PATH,
)
import fitz


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

# Input year
year = st.text_area(
    label="Entrez l'année du document souhaité.",
    value="2021",
    max_chars=4,
)

# Input Siren
company_id = st.text_area("Entrez un numéro Siren:")

# Add a button to check availability for all specified documents
if not st.session_state.inpi_auth:
    st.write(
        "Vous n'êtes pas authentifié auprès le l'INPI. "
        "Renseigner des identifiants valides à gauche."
    )
else:
    document_querier = DocumentQuerier(
        username=st.session_state.inpi_credentials.get("username"),
        password=st.session_state.inpi_credentials.get("password"),
    )

    # Button to chck availability
    dispo_button = st.button("Vérifier la disponibilité")
    if not st.session_state.get("button"):
        st.session_state["button"] = dispo_button

    if st.session_state["button"]:
        try:
            year = int(year)
        except ValueError:
            st.error("Année non valide.")

        if not check_siren_length(company_id):
            st.error(
                f"Le numéro Siren {company_id} ne contient pas 9 caractères."
            )
        else:
            availability, document_id = check_availability(
                document_querier, company_id, year
            )

            if availability:
                file_name = f"CA_{company_id}_{year}.pdf"
                # Display the availability status for each document
                st.write(f"Document disponible pour le Siren {company_id}.")

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
                if not st.session_state.get(
                    f"selection_button_{company_id}_{year}"
                ):
                    st.session_state[f"selection_button_{company_id}_{year}"] = (
                        selection_button
                    )
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
                            page_selection_url = (
                                "https://extraction-cs.lab.sspcloud.fr/select_page"
                            )
                            files = {"pdf_file": document.tobytes()}
                            response = requests.post(
                                url=page_selection_url, files=files
                            )
                            # TODO: handle errors using result field
                            page_number = response.json()["page_number"]
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

                        # Extraction
                        with table_transformer_tab:
                            extraction_button = st.button(
                                "Extraction des tableaux",
                                key=f"extraction_btn_{company_id}_{year}",
                            )
                            text_placeholder = st.empty()
                            if not st.session_state.get(
                                f"extraction_btn_{company_id}_{year}_state"
                            ):
                                st.session_state[
                                    f"extraction_btn_{company_id}_{year}_state"
                                ] = extraction_button
                            if st.session_state[
                                f"extraction_btn_{company_id}_{year}_state"
                            ]:
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
                                    # Table extraction
                                    table_transformer_output = (
                                        extract_tables_transformer(document)
                                    )
                                    for table_idx, df in enumerate(
                                        table_transformer_output
                                    ):
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
                                        f"Extraction de {len(table_transformer_output)} effectuée: "
                                        f"accédez-y grâce à l'onglet 'Extractions disponibles'."
                                    )

                        with extract_table_tab:
                            # ExtractTable extraction
                            extract_table_button = st.button(
                                "Extraction des tableaux",
                                key=f"extract_table_btn_{company_id}_{year}",
                            )
                            text_placeholder = st.empty()
                            if not st.session_state.get(
                                f"extract_table_btn_{company_id}_{year}_state"
                            ):
                                st.session_state[
                                    f"extract_table_btn_{company_id}_{year}_state"
                                ] = extract_table_button
                            if st.session_state[
                                f"extract_table_btn_{company_id}_{year}_state"
                            ]:
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
                                    outputs = extract_tables(document)
                                    for table_idx, (df, df_conf) in enumerate(
                                        outputs
                                    ):
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
