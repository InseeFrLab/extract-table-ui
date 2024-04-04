"""
Dashboard app.
"""

import base64
import os
import tempfile
from pathlib import Path
from ExtractTable import ExtractTable
import fitz
import img2pdf
import numpy as np
import pandas as pd
import streamlit as st
from ca_query.querier import DocumentQuerier
from PIL import Image

from utils import check_siren_length, get_detector, get_page_selector, pdf_to_csv


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
col1, col2 = st.columns(2)
with col1:
    st.subheader("Récupération des comptes sociaux")

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
                                pdf = fitz.open(stream=PDFbyte, filetype="pdf")
                                if page_number <= pdf.page_count - 3:
                                    number_extracted_pages = 3
                                    pdf.select(
                                        [
                                            page
                                            for page in range(
                                                page_number, page_number + 3
                                            )
                                        ]
                                    )
                                elif page_number <= pdf.page_count - 2:
                                    number_extracted_pages = 2
                                    pdf.select(
                                        [
                                            page
                                            for page in range(
                                                page_number, page_number + 2
                                            )
                                        ]
                                    )
                                else:
                                    number_extracted_pages = 1
                                    pdf.select([page_number])
                                for page_number in range(pdf.page_count):
                                    page = pdf.load_page(page_number)
                                    pix = page.get_pixmap(dpi=300)
                                    pix.pil_save(
                                        os.path.join(
                                            "data",
                                            "input_pdf",
                                            f"{company_id}--{page_number}.jpg",
                                        )
                                    )
                                os.remove(
                                    os.path.join(
                                        "data", "input_pdf", f"{company_id}.pdf"
                                    )
                                )

                                with open(
                                    os.path.join(
                                        "data", "input_pdf", f"{company_id}.pdf"
                                    ),
                                    "wb",
                                ) as f:
                                    f.write(
                                        img2pdf.convert(
                                            [
                                                os.path.join(
                                                    "data",
                                                    "input_pdf",
                                                    f"{company_id}--{page_number}.jpg",
                                                )
                                                for page_number in range(
                                                    number_extracted_pages
                                                )
                                            ]
                                        )
                                    )
                                for page_number in range(number_extracted_pages):
                                    os.remove(
                                        os.path.join(
                                            "data",
                                            "input_pdf",
                                            f"{company_id}--{page_number}.jpg",
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


def change_state(edited_df):
    st.session_state["df_value"] = edited_df
    st.session_state["disable"] = False


def disable_button():
    st.session_state["disable"] = True


directory_path = "data/output_xlsx/"
files = list_files(directory_path)
selected_table = st.sidebar.selectbox(
    label="Tableaux", options=files, on_change=disable_button
)
st.column_config.Column(width="large")
if selected_table:
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
    with col1:
        st.write(
            f"{selected_table} : Confiance = [{confidence_table.min(axis=None)} - {confidence_table.max(axis=None)}]"
        )
        col5, col6, col7, col8, col9 = st.columns(5)
        with col5:
            value_info = st.text_input(
                label="", value="ligne col val à changer", label_visibility="collapsed"
            )
        with col6:
            if st.button(label="Modifier"):
                try:
                    row, col, value = (
                        value_info.split()[0],
                        value_info.split()[1],
                        " ".join(value_info.split()[2:]),
                    )
                    row = int(row)
                    col = int(col)
                    table.iat[row, col] = value
                    table.to_excel(
                        f'{os.path.join("data/output_xlsx/", selected_table.split("--")[0], selected_table)}.xlsx'
                    )
                    st.session_state.df_value = table
                except:
                    st.error("ligne colonne ou valeur au mauvais format")
        new_table = table.style.background_gradient(
            axis=None, gmap=confidence_table, cmap="Reds"
        )
        with col7:
            edition_tableau = st.toggle(label="Edition")
        with col8:
            st.download_button(
                label="Export",
                data=table.to_csv(sep=";").encode("utf_8_sig"),
                file_name="selected_table.csv",
                mime="text/csv",
            )
        if edition_tableau:
            # if "df_value" not in st.session_state:
            st.session_state.df_value = table
            if "disable" not in st.session_state:
                st.session_state.disable = True
            edited_table = st.session_state["df_value"]
            edited_table = st.data_editor(
                edited_table, on_change=change_state, args=(edited_table,)
            )
            with col9:
                placeholder = st.empty()
                save_btn = placeholder.button(
                    label="Save", disabled=st.session_state.disable, key=1
                )
                if save_btn:
                    placeholder.button(label="Save", disabled=True, key=2)
                    edited_table.to_excel(
                        f'{os.path.join("data/output_xlsx/", selected_table.split("--")[0], selected_table)}.xlsx'
                    )
                    st.session_state["df_value"] = edited_table
        else:
            st.session_state.disable = True
            with col9:
                pass
            st.dataframe(
                new_table, height=800, use_container_width=True, hide_index=False
            )

    with col2:
        et_sess = ExtractTable(
            api_key=""
        )  # Replace your VALID API Key here
        usage = et_sess.check_usage()
        st.markdown(
            f'<div style="text-align: right;">Crédits utilisés : {usage["used"]}/{usage["credits"]}</div>',
            unsafe_allow_html=True,
        )

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
