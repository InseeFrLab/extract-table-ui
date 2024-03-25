"""
Utility functions.
"""

from pathlib import Path
from ca_extract.extraction.table_transformer.detector import TableTransformerDetector
from ca_extract.extraction.table_transformer.extractor import TableTransformerExtractor
from ca_extract.page_selection.page_selector import PageSelector
import streamlit as st
import mlflow


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
