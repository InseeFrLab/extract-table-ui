"""
Utility functions.
"""
from typing import List, Tuple
import json
import os
from pathlib import Path
from s3fs import S3FileSystem
import pandas as pd
import requests
import streamlit as st
import fitz
import tempfile
from ca_query.querier import DocumentQuerier
import re


@st.cache_data
def check_availability(_document_querier: DocumentQuerier, company_id: str, year: str) -> Tuple:
    """
    Check if a document is available for a given company and year.

    Args:
        _document_querier (DocumentQuerier): Document querier.
        company_id (str): Company identifier.
        year (str): Year.

    Returns:
        Tuple: Availability status and document ID.
    """
    try:
        # Make an API request to check availability for each document
        availability, document_id = _document_querier.check_document_availability(
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
def download_pdf(_document_querier: DocumentQuerier, document_id: str):
    """
    Download a PDF document from its ID.

    Args:
        _document_querier (DocumentQuerier): Document querier.
        document_id (str): Document ID.
    """
    with tempfile.TemporaryDirectory() as tmpdirname:
        tmp_dir = Path(tmpdirname)
        tmp_file_path = tmp_dir / "tmp.pdf"
        _document_querier.download_from_id(
            document_id, save_path=tmp_file_path, s3=False
        )

        with open(tmp_file_path, "rb") as pdf_file:
            PDFbyte = pdf_file.read()
        # Also return fitz Document ? Probleme can't cache
    if len(PDFbyte) < 10000:
        print(PDFbyte)
    return PDFbyte


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


@st.cache_resource(ttl=3600)
def get_querier():
    """
    Get document querier.
    """
    return DocumentQuerier(
        os.environ["TEST_INPI_USERNAME"], os.environ["TEST_INPI_PASSWORD"]
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
    for dir_path, dir_names, file_names in fs.walk(s3_path):
        for file_name in file_names:
            if Path(file_name).name == ".keep":
                continue
            file_path = f'{dir_path}/{file_name}'
            files.append(file_path)
    return files


def get_extract_table_credits(token: str) -> int:
    """
    Get ExtractTable credits.

    Args:
        token (str): ExtractTable token.

    Returns:
        int: Remaining credits.
    """
    headers = {"x-api-key": token}

    # Token validation
    validation_url = "https://validator.extracttable.com"
    validation_response = requests.request("GET", validation_url, headers=headers)
    total_credits = json.loads(validation_response.text)["usage"]["credits"]
    used_credits = json.loads(validation_response.text)["usage"]["used"]
    remaining_credits = total_credits - used_credits
    return remaining_credits


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
    # Check file extension
    if not s3_path.endswith(".xlsx"):
        raise ValueError("File must be an Excel file.")
    with tempfile.TemporaryDirectory() as temp_dir:
        # Download the Excel file from S3 to the temporary directory
        local_path = os.path.join(temp_dir, 'tmp_file.xlsx')
        fs.get(s3_path, local_path)

        # Read the Excel file using pandas
        df = pd.read_excel(local_path, index_col=0)
    return df


def upload_pdf_to_s3(document: fitz.Document, fs: S3FileSystem, s3_path: str):
    """
    Upload a PDF document to S3.

    Args:
        document (fitz.Document): Document.
        fs (S3FileSystem): S3 file system.
        s3_path (str): S3 path.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        local_path = os.path.join(temp_dir, 'tmp_file.pdf')
        document.save(
            local_path
        )
        fs.put(local_path, s3_path)
        return


def read_pdf_from_s3(fs: S3FileSystem, s3_path: str):
    """
    Read PDF file from S3.

    Args:
        fs (S3FileSystem): S3 file system.
        s3_path (str): S3 path.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        # Download the PDF file from S3 to the temporary directory
        local_path = os.path.join(temp_dir, 'tmp_file.pdf')
        fs.get(s3_path, local_path)
        # Read the PDF file using fitz
        document = fitz.open(local_path)
    return document


def format_extraction_name(file_path: str) -> str:
    """
    Format table transformer extraction name.

    Args:
        file_path (str): File path.

    Returns:
        str: Formatted name.
    """
    pattern = r'(\d+)_(\d{4})/table_(\d+)\.(csv|xlsx)'
    match = re.search(pattern, file_path)

    if match:
        id_number, year, table_number, _ = match.groups()
        table_number = int(table_number) + 1  # Adjust table number to start from 1 instead of 0
        output_string = f"{id_number} ({year}) - Table {table_number}"
        return output_string
    else:
        return file_path
