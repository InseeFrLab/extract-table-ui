"""
Functions implementing table extraction.
"""
import requests
import json
import time
import pandas as pd
from typing import List
import fitz
import streamlit as st
from utils import get_extract_table_credits


def extract_tables_transformer(document: fitz.Document) -> List:
    """
    Extract tables using Table Transformer.

    Args:
        document (fitz.Document): Document.

    Returns:
        List: List of extracted tables
    """
    extraction_url = "https://extraction-cs.lab.sspcloud.fr/extract"
    files = {"pdf_page": document.tobytes()}
    response = requests.post(
        url=extraction_url, files=files
    )
    # TODO: handle errors using result field
    tables = response.json()["tables"]
    return [pd.DataFrame.from_dict(table) for table in tables]


def extract_tables(document: fitz.Document) -> List:
    """
    Extract tables using https://extracttable.com/.

    Args:
        document (fitz.Document): Document.

    Returns:
        List: List of extracted tables and confidences.
    """
    token = st.session_state.auth_token
    remaining_credits = get_extract_table_credits(token)
    if remaining_credits < 1:
        raise ValueError(
            "Not enough credits to extract tables."
            "Specify a valid token with enough credits.")

    # Post request to extract tables
    url = "https://trigger.extracttable.com"
    # Call extracttable API to get an extraction
    headers = {"x-api-key": token}
    payload = {
        "dup_check": "False",
    }
    files = [
        (
            "input",
            (
                "document.pdf",
                document.tobytes(),
            ),
        )
    ]

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
    outputs = []
    for extracted_table in range(len(json_object["Tables"])):
        # Process extracted table
        df = pd.DataFrame.from_dict(
            json_object["Tables"][extracted_table]["TableJson"], orient="index"
        )
        df.index = df.index.map(int)
        df = df.sort_index(axis=0)

        try:
            # Process confidence indices
            df_conf = pd.DataFrame.from_dict(
                json_object["Tables"][extracted_table]["TableConfidence"], orient="index"
            )
            df_conf.index = df_conf.index.map(int)
            df_conf = df_conf.sort_index(axis=0)
            outputs.append((df, df_conf))
        except KeyError:
            # No confidence index, return None
            outputs.append((df, None))
    return outputs
