"""
Utility functions.
"""
from typing import List
import io
import json
import os
import time
import zipfile
from pathlib import Path
from s3fs import S3FileSystem
import mlflow
import pandas as pd
import requests
import streamlit as st
from ca_extract.extraction.table_transformer.detector import \
    TableTransformerDetector
from ca_extract.extraction.table_transformer.extractor import \
    TableTransformerExtractor
from ca_extract.page_selection.page_selector import PageSelector
import base64
import tempfile


@st.cache_resource
def get_file_system():
    """
    Get s3 file system.
    """
    return S3FileSystem(
        client_kwargs={'endpoint_url': 'https://'+'minio.lab.sspcloud.fr'},
        key=os.getenv("AWS_ACCESS_KEY_ID"),
        secret=os.getenv("AWS_SECRET_ACCESS_KEY"),
    )


def check_siren_length(siren: str) -> bool:
    """
    Check firm identifier has correct length.

    Args:
        siren (str): Firm identifier.

    Returns:
        bool: True if correct length, False otherwise.
    """
    if len(siren) == 9:
        return True
    return False


def get_root_path():
    return Path(__file__).parent.parent


@st.cache_resource
def get_detector() -> TableTransformerDetector:
    """
    Load table detector model.

    Returns:
        TableTransformerDetector: detector.
    """
    detector = TableTransformerDetector(
        padding_factor=1.02,
        crop_padding_factor=1.02,
    )
    print("TableTransformerDetector loaded.")
    return detector


@st.cache_resource
def get_extractor() -> TableTransformerExtractor:
    """
    Load table extractor model.

    Returns:
        TableTransformerExtractor: detector.
    """
    extractor = TableTransformerExtractor()
    print("TableTransformerExtractor loaded.")
    return extractor


@st.cache_resource
def get_page_selector(from_mlflow: bool = True) -> PageSelector:
    """
    Load page selector.

    Args:
        from_mlflow (bool, optional): Load from MLflow. Defaults to True.

    Returns:
        PageSelector: Page selector.
    """
    if from_mlflow:
        model_name = "page_selection"
        stage = "Staging"
        clf = mlflow.pyfunc.load_model(f"models:/{model_name}/{stage}")
    # Load from local
    else:
        clf = mlflow.pyfunc.load_model("models/page_selection")
    page_selector = PageSelector(clf=clf)
    print("Page selector loaded.")
    return page_selector


def list_files(fs: S3FileSystem, s3_path: str) -> List:
    """
    List files in s3_path directory.

    Args:
        fs (S3FileSystem): S3 file system.
        s3_path (str): Directory.

    Returns:
        List: List of files.
    """
    files = []
    for file in fs.ls(s3_path):
        if Path(file).name == ".keep":
            continue
        files.append(Path(file).name)
    return files


def change_state(edited_df):
    st.session_state["df_value"] = edited_df
    st.session_state["disable"] = False


def disable_button():
    """
    Disable button.
    """
    st.session_state["disable"] = True


def pdf_to_csv(uploaded_pdf_file, company_id, s3: bool = True) -> bytes:
    """


    Args:
        uploaded_pdf_file (_type_): _description_
        company_id (_type_): _description_
        s3 (bool): if True, then upload to S3. Defaults to True.

    Returns:
        bytes: _description_
    """
    if s3:
        s3_input_pdf_path = Path("projet-extraction-tableaux/app_data/pdf")
        s3_output_xlsx_path = Path("projet-extraction-tableaux/app_data/xlsx/extracttable")
    destination = Path(os.path.join("data", "input_pdf", f"{company_id}.pdf"))
    output_folder = os.path.join("data/output_xlsx", company_id)
    if not os.path.exists(output_folder):
        os.mkdir(output_folder)

    # Call extracttable API to get an extraction
    url = "https://trigger.extracttable.com"

    payload = {"dup_check": "False"}
    files = [
        (
            "input",
            (
                f"{company_id}.pdf",
                open(os.path.join("data/input_pdf", f"{company_id}.pdf"), "rb"),
            ),
        )
    ]
    headers = {"x-api-key": ""}

    response = requests.request("POST", url, headers=headers, data=payload, files=files)
    url = "https://getresult.extracttable.com/?JobId=" + str(
        json.loads(response.text)["JobId"]
    )
    payload = {}
    response = requests.request("GET", url, headers=headers, data=payload)
    while str(json.loads(response.text)["JobStatus"]) == "Processing":
        time.sleep(1)
        response = requests.request("GET", url, headers=headers, data=payload)

    json_object = json.loads(response.text)

    # Process extraction
    for extracted_table in range(len(json_object["Tables"])):
        # Process extracted table
        df = pd.DataFrame.from_dict(
            json_object["Tables"][extracted_table]["TableJson"], orient="index"
        )
        df.index = df.index.map(int)
        df = df.sort_index(axis=0)
        # Save as excel file
        df.to_excel(
            os.path.join(
                output_folder, company_id + "--" + str(extracted_table + 1) + ".xlsx"
            )
        )

        # Process confidence indices
        df_conf = pd.DataFrame.from_dict(
            json_object["Tables"][extracted_table]["TableConfidence"], orient="index"
        )
        df_conf.index = df_conf.index.map(int)
        df_conf = df_conf.sort_index(axis=0)
        # Save confidence indices
        df_conf.to_excel(
            os.path.join(
                output_folder,
                company_id + "--" + str(extracted_table + 1) + "_confidence.xlsx",
            )
        )

    # Return zip file
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(
        file=zip_buf, mode="w", compression=zipfile.ZIP_DEFLATED
    ) as zip_file:
        for name in os.listdir(output_folder):
            zip_file.write(os.path.join(output_folder, name), name)
    buf = zip_buf.getvalue()
    zip_buf.close()
    return buf


def display_pdf(fs: S3FileSystem, s3_path: str):
    """
    Display PDF.

    Args:
        fs (S3FileSystem): S3 file system.
        s3_path (str): S3 path.
    """
    with fs.open(s3_path, "rb") as f:
        base64_pdf = base64.b64encode(f.read()).decode("utf-8")

    # Embed PDF in HTML
    pdf_display = f'<embed id="pdfViewer" src="data:application/pdf;base64,{base64_pdf}" width="700" height="1000" type="application/pdf">'

    # Display file
    return st.markdown(pdf_display, unsafe_allow_html=True)


def read_excel_from_s3(
    fs: S3FileSystem,
    s3_path: str,
) -> pd.DataFrame:
    """
    Read Excel file from S3.

    Args:
        fs (S3FileSystem): S3 file system.
        s3_path (str): S3 path.

    Returns:
        pd.DataFrame: Excel file as DataFrame.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        # Download the Excel file from S3 to the temporary directory
        local_path = fs.get(s3_path, temp_dir)

        # Read the Excel file using pandas
        df = pd.read_excel(local_path)
    return df
