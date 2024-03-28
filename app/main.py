"""
Dashboard app.
"""

import base64
import os
import tempfile
from pathlib import Path

import fitz
import img2pdf
import numpy as np
import pandas as pd
import streamlit as st
from ca_query.querier import DocumentQuerier
from PIL import Image

from utils import (check_siren_length, get_detector, get_page_selector,
                   pdf_to_csv)


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
st.set_page_config(layout="wide")
st.title("Récupération des comptes sociaux")

# Document querier
document_querier = DocumentQuerier(
    os.environ["TEST_INPI_USERNAME"], os.environ["TEST_INPI_PASSWORD"]
)
detector = get_detector()
page_selector = get_page_selector()

with st.sidebar.container():
    # Allow users to input year
    year = st.text_area(
        label="Entrez l'année pour laquelle vous souhaitez vérifier"
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
            for idx, company_id in enumerate(company_ids):
                if not check_siren_length(company_id):
                    st.error(
                        f"Le numéro Siren {company_id} ne contient "
                        f"pas 9 caractères."
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
                                document.save(
                                    os.path.join(
                                        "data", "input_pdf", f"{company_id}.pdf"
                                    )
                                )
                                zip_buffer = pdf_to_csv(document, company_id)
                                pdf = fitz.open(
                                    os.path.join(
                                        "data", "input_pdf", f"{company_id}.pdf"
                                    )
                                )
                                page = pdf.load_page(0)
                                pix = page.get_pixmap(dpi=300)
                                pix.pil_save(
                                    os.path.join(
                                        "data", "input_pdf", f"{company_id}.jpg"
                                    )
                                )
                                os.remove(
                                    os.path.join(
                                        "data", "input_pdf", f"{company_id}.pdf"
                                    )
                                )
                                image = Image.open(
                                    os.path.join(
                                        "data", "input_pdf", f"{company_id}.jpg"
                                    )
                                )
                                pdf_bytes = img2pdf.convert(image.filename)
                                file = open(
                                    os.path.join(
                                        "data", "input_pdf", f"{company_id}.pdf"
                                    ),
                                    "wb",
                                )
                                file.write(pdf_bytes)
                                image.close()
                                file.close()
                                os.remove(
                                    os.path.join(
                                        "data", "input_pdf", f"{company_id}.jpg"
                                    )
                                )
                                st.download_button(
                                    label="Télécharger les résultats",
                                    data=zip_buffer,
                                    file_name="results.zip",
                                )
                            except ValueError as e:
                                st.write(str(e))
                    else:
                        st.write(
                            f"Document indisponible pour le " f"Siren {company_id}."
                        )


def list_files(directory):
    file_list = []
    for root, directories, files in os.walk(directory):
        for filename in files:
            if "confidence" not in filename and "gitkeep" not in filename:
                file_list.append(filename[:-5])
    return file_list


directory_path = "data/output_xlsx/"
files = list_files(directory_path)
selected_table = st.sidebar.selectbox(label="Tableaux", options=files)
st.column_config.Column(width="large")
if selected_table:
    st.write(selected_table)
    table = pd.read_excel(
        f'{os.path.join("data/output_xlsx/", selected_table.split("--")[0], selected_table)}.xlsx',
        index_col=0,
    )
    table.fillna("", inplace=True)
    confidence_table = pd.read_excel(
        f'{os.path.join("data/output_xlsx/", selected_table.split("--")[0], selected_table)}_confidence.xlsx',
        index_col=0,
    )
    table = table.values.tolist()
    table = pd.DataFrame(table)
    confidence_table = confidence_table.values.tolist()
    confidence_table = pd.DataFrame(confidence_table).replace(0.0, np.nan)
    st.write(
        f"Taux de confiance d'extraction des cellules: [min={confidence_table.min(axis=None)}, max={confidence_table.max(axis=None)}]"
    )
    col1, col2 = st.columns(2)
    with col1:
        new_table = table.style.background_gradient(
            axis=None, gmap=confidence_table, cmap="Reds"
        )
        st.dataframe(new_table)
    with col2:
        from streamlit_pdf_viewer import pdf_viewer

        file = f'{os.path.join("data/input_pdf", selected_table.split("--")[0])}.pdf'

        with open(file, "rb") as f:
            base64_pdf = base64.b64encode(f.read()).decode("utf-8")

        # Embedding PDF in HTML
        pdf_display = f'<embed id="pdfViewer" src="data:application/pdf;base64,{base64_pdf}" width="700" height="1000" type="application/pdf">'

        # Displaying File
        st.markdown(pdf_display, unsafe_allow_html=True)

        # Scroll to and highlight text
        html = f"""
        <alert> JS injected... </alert>
        <script>
        var container = document.getElementById("pdfViewer");
        container.scrollTop = container.scrollHeight;
        </script>
        """
