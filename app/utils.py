"""
Utility functions.
"""

import io
import json
import os
import shutil
import time
import zipfile
from pathlib import Path

import fitz
import mlflow
import pandas as pd
import requests
import streamlit as st
from ca_extract.extraction.table_transformer.detector import \
    TableTransformerDetector
from ca_extract.extraction.table_transformer.extractor import \
    TableTransformerExtractor
from ca_extract.page_selection.page_selector import PageSelector
from fastapi import UploadFile


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
def get_page_selector() -> PageSelector:
    """
    Load page selector.

    Returns:
        PageSelector: Page selector.
    """
    model_name = "page_selection"
    stage = "Staging"
    clf = mlflow.pyfunc.load_model(f"models:/{model_name}/{stage}")
    page_selector = PageSelector(clf=clf)
    print("Page selector loaded.")
    return page_selector


def pdf_to_csv(uploaded_pdf_file, company_id) -> bytes:

    destination = Path(os.path.join("data", "input_pdf", f"{company_id}.pdf"))
    output_folder = os.path.join("data/output_xlsx", company_id)
    if not os.path.exists(output_folder):
        os.mkdir(output_folder)

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

    for extracted_table in range(len(json_object["Tables"])):
        df = pd.DataFrame.from_dict(
            json_object["Tables"][extracted_table]["TableJson"], orient="index"
        )
        df.index = df.index.map(int)
        df = df.sort_index(axis=0)
        df.to_excel(
            os.path.join(
                output_folder, company_id + "--" + str(extracted_table + 1) + ".xlsx"
            )
        )

        df_conf = pd.DataFrame.from_dict(
            json_object["Tables"][extracted_table]["TableConfidence"], orient="index"
        )
        df_conf.index = df_conf.index.map(int)
        df_conf = df_conf.sort_index(axis=0)
        df_conf.to_excel(
            os.path.join(
                output_folder,
                company_id + "--" + str(extracted_table + 1) + "_confidence.xlsx",
            )
        )

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(
        file=zip_buf, mode="w", compression=zipfile.ZIP_DEFLATED
    ) as zip_file:
        for name in os.listdir(output_folder):
            zip_file.write(os.path.join(output_folder, name), name)
    buf = zip_buf.getvalue()
    zip_buf.close()
    return buf
