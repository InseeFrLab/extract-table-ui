"""
Dashboard app.
"""
from typing import Tuple
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

from utils import check_siren_length, get_detector, get_page_selector, pdf_to_csv, disable_button, list_files, get_file_system
from constants import S3_OUTPUT_XLSX_DIR




# Create the Streamlit app
st.set_page_config(layout="wide")
col1, col2 = st.columns(2)
with col1:
    st.subheader("Récupération des comptes sociaux")



    

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


files = list_files(fs=fs, s3_path=S3_OUTPUT_XLSX_DIR)
selected_table = st.sidebar.selectbox(
    label="Tableaux", options=files, on_change=disable_button
)
st.column_config.Column(width="large")
if selected_table:
    # Load pandas DataFrames from xlsx files stored in S3
    extraction_path = S3_OUTPUT_XLSX_DIR / selected_table
    confidence_path = S3_OUTPUT_CONFIDENCE_DIR / selected_table

    with fs.open(extraction_path, "rb") as f:
        extraction = pd.read_excel(f, index_col=0)
        extraction.fillna("", inplace=True)
        extraction = extraction.values.tolist()
        extraction = pd.DataFrame(extraction)
    # TODO: when no confidence available, display a message
    with fs.open(confidence_path, "rb") as f:
        confidence = pd.read_excel(f, index_col=0)
        confidence = confidence.values.tolist()
        confidence = pd.DataFrame(confidence).replace(0.0, np.nan)
    confidence = None

    with col1:
        # If there is a confidence
        if confidence is not None:
            st.write(
                f"{selected_table} : Confiance = [{confidence.min(axis=None)} - {confidence.max(axis=None)}]"
            )
        else:
            st.write(
                "No confidence available for this table."
            )

        # TODO: reimplement possibility to change values
        """
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
        """
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
