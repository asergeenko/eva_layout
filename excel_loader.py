import logging
import os
from collections.abc import Buffer
from io import BytesIO
from typing import Any

import pandas as pd

TARGET_SHEET = "ZAKAZ"

logger = logging.getLogger(__name__)


# @st.cache_data(ttl=600)  # Cache for 10 minutes
def load_excel_file(file_content: Buffer) -> dict[str, pd.DataFrame] | pd.DataFrame:
    """Load and cache Excel file processing - optimized for speed"""
    # Only load the ZAKAZ sheet instead of all sheets for faster loading
    try:
        excel_data = pd.read_excel(
            BytesIO(file_content),
            sheet_name="ZAKAZ",  # Load only ZAKAZ sheet
            header=None,
            date_format=None,
            parse_dates=False,
            engine="openpyxl",  # Use faster engine
        )
        return {TARGET_SHEET: excel_data}
    except ValueError:
        # If ZAKAZ sheet doesn't exist, load all sheets to show available ones
        excel_data = pd.read_excel(
            BytesIO(file_content),
            sheet_name=None,
            header=None,
            date_format=None,
            parse_dates=False,
            engine="openpyxl",
        )
        return excel_data


def parse_orders_from_excel(
    excel_data: dict[str, pd.DataFrame],
) -> list[dict[str, Any]] | None:
    # Process only the "ZAKAZ" sheet
    all_orders = []

    if TARGET_SHEET in excel_data:
        df = excel_data[TARGET_SHEET]

        # Skip first 2 rows (headers), start from row 2 (index 2)
        if df.shape[0] > 2:
            data_rows = df.iloc[2:].copy()

            # Check for empty "Сделано" column (index 2)
            if df.shape[1] > 3:  # Make sure we have enough columns
                pending_orders = data_rows[
                    data_rows.iloc[:, 2].isna() | (data_rows.iloc[:, 2] == "")
                ]

                for idx, row in pending_orders.iterrows():
                    if pd.notna(
                        row.iloc[3]
                    ):  # Check if Артикул (column D) is not empty
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
                            "product": str(row.iloc[4])
                            if pd.notna(row.iloc[4])
                            else "",
                            "client": str(row.iloc[5])
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
    else:
        return None
    return all_orders


def find_product_folder(article, product_name):
    """Find the base folder for a product based on article and product name."""

    logger.info(f"Поиск папки для артикула: '{article}', товара: '{product_name}'")

    # Strategy 1: Direct search in flat dxf_samples folder structure
    if product_name:
        product_upper = product_name.upper()

        # Search directly in dxf_samples folder for matching folder names
        best_match = None
        best_score = 0

        for item in os.listdir("dxf_samples"):
            item_path = os.path.join("dxf_samples", item)
            if os.path.isdir(item_path):
                score = calculate_folder_match_score(product_name, item)
                if score > best_score:
                    best_score = score
                    best_match = item_path

        if best_match and best_score >= 6:
            logger.info(
                f"Найдено соответствие по имени товара: {best_match} (счёт: {best_score})"
            )
            return best_match

        # Special categories handling
        special_keywords = {
            "лодка": ["Лодка", "ADMIRAL", "ABAKAN", "AKVA", "АГУЛ", "Азимут"],
            "ковер": ["Коврик"],
            "самокат": ["ДЕКА", "KUGOO"],
        }

        for category, keywords in special_keywords.items():
            for keyword in keywords:
                if keyword.upper() in product_upper:
                    # Search for folders containing this keyword
                    for item in os.listdir("dxf_samples"):
                        if keyword.lower() in item.lower():
                            folder_path = os.path.join("dxf_samples", item)
                            if os.path.isdir(folder_path):
                                logger.info(
                                    f"Найдено соответствие по ключевому слову '{keyword}': {folder_path}"
                                )
                                return folder_path

    # Strategy 2: Parse article format like EVA_BORT+Brand+Model
    if "+" in article:
        parts = article.split("+")
        if len(parts) >= 3:
            brand = parts[1].strip()
            model_info = parts[2].strip()

            logger.info(f"Парсинг артикула: бренд='{brand}', модель='{model_info}'")

            # Handle special case mappings first
            special_mappings = {
                "Kugoo": ["ДЕКА KUGOO KIRIN M4 PRO", "ДЕКА KUGOO M4 PRO JILONG"],
                "Абакан": ["Лодка ABAKAN 430 JET"],
                "Admiral": [
                    "Лодка ADMIRAL 335",
                    "Лодка ADMIRAL 340",
                    "Лодка ADMIRAL 410",
                ],
                "AKVA": ["Лодка AKVA 2600", "Лодка AKVA 2800"],
            }

            if brand in special_mappings:
                for folder_name in special_mappings[brand]:
                    folder_path = os.path.join("dxf_samples", folder_name)
                    if os.path.exists(folder_path):
                        logger.info(f"Найдено специальное соответствие: {folder_path}")
                        return folder_path

            # For standard automotive brands, search the flat folder structure
            # Create search term from brand and model
            search_term = f"{brand} {model_info}".upper()

            # Find best match in flat folder structure
            best_match = None
            best_score = 0

            for item in os.listdir("dxf_samples"):
                item_path = os.path.join("dxf_samples", item)
                if os.path.isdir(item_path):
                    score = calculate_folder_match_score(search_term, item)
                    if score > best_score:
                        best_score = score
                        best_match = item_path

            if best_match and best_score >= 3:
                logger.info(
                    f"Найдено соответствие по артикулу: {best_match} (счёт: {best_score})"
                )
                return best_match

    # Strategy 3: Direct path mapping
    direct_path = f"dxf_samples/{article}"
    if os.path.exists(direct_path):
        return direct_path

    return None


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


# @st.cache_data(ttl=300)  # Cache for 5 minutes
def find_dxf_files_for_article(
    id: str, product_name: str = "", product_type: str = ""
) -> list[str]:
    """Find DXF files for a given article using the new product type mapping."""
    if product_type:
        return get_dxf_files_for_product_type(id, product_name, product_type)
    else:
        # Fallback to old behavior if product_type not provided
        base_folder = find_product_folder(id, product_name)
        if base_folder:
            found_files = []
            dxf_folder = os.path.join(base_folder, "DXF")
            search_folder = dxf_folder if os.path.exists(dxf_folder) else base_folder

            try:
                for file in os.listdir(search_folder):
                    if file.lower().endswith(".dxf"):
                        found_files.append(os.path.join(search_folder, file))
            except OSError:
                pass

            return found_files
        return []


def get_dxf_files_for_product_type(id: str, product_name: str, product_type: str):
    """Get DXF files for a specific product type based on the mapping rules."""

    found_files = []

    logger.info(
        f"Поиск DXF файлов: артикул='{id}', товар='{product_name}', тип='{product_type}'"
    )

    # Find the base folder for this id/product
    base_folder = find_product_folder(id, product_name)

    if base_folder and os.path.exists(base_folder):
        logger.info(f"Найдена базовая папка: {base_folder}")

        # Look for DXF folder first, then try the base folder directly
        dxf_folder = os.path.join(base_folder, "DXF")
        if os.path.exists(dxf_folder):
            search_folder = dxf_folder
            logger.info(f"Используется подпапка DXF: {search_folder}")
        else:
            search_folder = base_folder
            logger.info(f"DXF файлы ищутся непосредственно в: {search_folder}")

        # Get all DXF files in the folder
        all_dxf_files = []
        try:
            for file in os.listdir(search_folder):
                if file.lower().endswith(".dxf"):
                    all_dxf_files.append(os.path.join(search_folder, file))
        except OSError as e:
            logger.error(f"Ошибка чтения папки {search_folder}: {e}")
            return []

        # Apply product type specific filtering
        if product_type == "борт":
            # Files 1.dxf to 9.dxf
            for i in range(1, 10):
                target_file = os.path.join(search_folder, f"{i}.dxf")
                if os.path.exists(target_file):
                    found_files.append(target_file)

        elif product_type == "водитель":
            # Only 1.dxf
            target_file = os.path.join(search_folder, "1.dxf")
            if os.path.exists(target_file):
                found_files.append(target_file)

        elif product_type == "передние":
            # 1.dxf and 2.dxf
            for i in [1, 2]:
                target_file = os.path.join(search_folder, f"{i}.dxf")
                if os.path.exists(target_file):
                    found_files.append(target_file)

        elif product_type == "багажник":
            # Files 10.dxf to 16.dxf
            for i in range(10, 17):
                target_file = os.path.join(search_folder, f"{i}.dxf")
                if os.path.exists(target_file):
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
        logger.debug(f"Найденные файлы: {[os.path.basename(f) for f in found_files]}")

    return found_files
