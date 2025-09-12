import logging
from collections.abc import Buffer
from io import BytesIO
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

TARGET_SHEET = "ZAKAZ"

DXF_ROOT_DIR = "dxf_samples"

logger = logging.getLogger(__name__)


@st.cache_data(ttl=600)  # Cache for 10 minutes
def load_excel_file(file_content: Buffer) -> pd.DataFrame:
    """Load and cache Excel file processing - optimized for speed"""
    # Only load the ZAKAZ sheet instead of all sheets for faster loading
    excel_data = pd.read_excel(
        BytesIO(file_content),
        sheet_name=TARGET_SHEET,  # Load only ZAKAZ sheet
        header=None,
        date_format=None,
        parse_dates=False,
        engine="openpyxl",  # Use faster engine
    )
    return excel_data


def parse_orders_from_excel(
    df: pd.DataFrame,
) -> list[dict[str, Any]] | None:
    # Process only the "ZAKAZ" sheet
    all_orders = []

    # Skip first 2 rows (headers), start from row 2 (index 2)
    if df.shape[0] > 2:
        data_rows = df.iloc[2:].copy()

        # Check for empty "Сделано" column (index 2)
        if df.shape[1] > 3:  # Make sure we have enough columns
            pending_orders = data_rows[
                data_rows.iloc[:, 2].isna() | (data_rows.iloc[:, 2] == "")
            ]

            for idx, row in pending_orders.iterrows():
                if pd.notna(row.iloc[3]):  # Check if Артикул (column D) is not empty
                    # Get color from column I (index 8)
                    color = (
                        str(row.iloc[8]).lower().strip()
                        if pd.notna(row.iloc[8]) and df.shape[1] > 8
                        else ""
                    )
                    # Normalize color values
                    if "черн" in color or "black" in color:
                        color = "чёрный"
                    elif "сер" in color or "gray" in color or "grey" in color:
                        color = "серый"
                    else:
                        color = "серый"  # Default color if not specified

                    # Create unique order_id for each row (Excel row number + sheet name)
                    unique_order_id = f"{TARGET_SHEET}_row_{idx}"

                    order = {
                        "sheet": TARGET_SHEET,
                        "row_index": idx,
                        "date": str(row.iloc[0]) if pd.notna(row.iloc[0]) else "",
                        "article": str(row.iloc[3]),
                        "product": str(row.iloc[4]) if pd.notna(row.iloc[4]) else "",
                        "marketplace": str(row.iloc[5])
                        if pd.notna(row.iloc[5])
                        else ""
                        if df.shape[1] > 5
                        else "",
                        "order_id": unique_order_id,  # Use unique ID for each Excel row
                        "color": color,
                        "product_type": str(row.iloc[7])
                        if pd.notna(row.iloc[7]) and df.shape[1] > 7
                        else "",
                        "border_color": row.iloc[10],
                    }
                    all_orders.append(order)
    return all_orders


def find_product_folder(product_name: str):
    """Find the base folder for a product based on article and product name."""
    return Path(DXF_ROOT_DIR) / product_name


def calculate_folder_match_score(search_term: str, folder_name: str) -> float:
    """Calculate how well a folder name matches the search term."""
    import re

    search_lower = search_term.lower()
    folder_lower = folder_name.lower()
    score = 0

    # Direct substring match
    if search_lower in folder_lower or folder_lower in search_lower:
        score += max(len(search_lower), len(folder_lower)) * 2

    # Word-based matching
    search_words = re.split(r"[\s\-_()]+", search_lower)
    folder_words = re.split(r"[\s\-_()]+", folder_lower)

    # Remove empty words
    search_words = [w for w in search_words if len(w) > 1]
    folder_words = [w for w in folder_words if len(w) > 1]

    for search_word in search_words:
        for folder_word in folder_words:
            if search_word == folder_word:
                score += len(search_word) * 3
            elif search_word in folder_word:
                score += len(search_word) * 2
            elif folder_word in search_word:
                score += len(folder_word) * 2
            elif search_word[:3] == folder_word[:3] and len(search_word) > 2:
                score += 2  # Partial match for similar words

    logger.debug(f"Счёт соответствия '{search_term}' <-> '{folder_name}': {score}")

    return score


@st.cache_data(ttl=300)  # Cache for 5 minutes
def find_dxf_files_for_article(
    product_id: str, product_name: str = "", product_type: str = ""
) -> list[str]:
    """Find DXF files for a given article using the new product type mapping."""
    return get_dxf_files_for_product_type(product_id, product_name, product_type)


def get_dxf_files_for_product_type(
    product_id: str, product_name: str, product_type: str
):
    """Get DXF files for a specific product type based on the mapping rules."""
    product_name = product_name.strip()
    product_type = product_type.strip()
    product_id = product_id.strip()

    found_files = []

    logger.info(
        f"Поиск DXF файлов: артикул='{product_id}', товар='{product_name}', тип='{product_type}'"
    )

    # Find the base folder for this id/product
    base_folder = find_product_folder(product_name)

    if base_folder and base_folder.exists():
        logger.info(f"Найдена базовая папка: {base_folder}")

        # Get all DXF files in the folder
        all_dxf_files = list(base_folder.rglob("*.dxf", case_sensitive=False))

        # Apply product type specific filtering
        if product_type == "борт":
            # Files 1.dxf to 9.dxf
            for i in range(1, 10):
                target_file = base_folder / f"{i}.dxf"
                if target_file.exists():
                    found_files.append(target_file)

        elif product_type == "водитель":
            # Only 1.dxf
            target_file = base_folder / "1.dxf"
            if target_file.exists():
                found_files.append(target_file)

        elif product_type == "передние":
            # 1.dxf and 2.dxf
            for i in [1, 2]:
                target_file = base_folder / f"{i}.dxf"
                if target_file.exists():
                    found_files.append(target_file)

        elif product_type == "багажник":
            # Files 10.dxf to 16.dxf
            for i in range(10, 17):
                target_file = base_folder / f"{i}.dxf"
                if target_file.exists():
                    found_files.append(target_file)

        elif product_type in ["самокат", "лодка", "ковер"]:
            # All available files in the folder
            found_files = all_dxf_files

        else:
            # Unknown product type - take all files as fallback
            logger.warning(f"Неизвестный тип изделия: {product_type}, берем все файлы")
            found_files = all_dxf_files

    logger.info(
        f"Результат поиска для типа '{product_type}': найдено {len(found_files)} файлов"
    )
    if found_files:
        logger.debug(f"Найденные файлы: {[f.name for f in found_files]}")

    return found_files
