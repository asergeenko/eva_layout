import streamlit as st
import pandas as pd
import os
from datetime import datetime
from io import BytesIO
import zipfile
import logging


from layout_optimizer import (
    parse_dxf_complete,
    bin_packing_with_inventory,
    plot_layout,
    plot_input_polygons,
    save_dxf_layout_complete,
    Carpet,
)

# Константы
MAX_SHEETS_PER_ORDER = (
    5  # Максимальное количество листов на один заказ (номер заказа из колонки O)
)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("eva_layout_debug.log", mode="w", encoding="utf-8"),
        logging.StreamHandler(),  # Также выводить в консоль
    ],
)
logger = logging.getLogger(__name__)

logger.info("=== НАЧАЛО СЕССИИ EVA LAYOUT ===")
logger.info(f"MAX_SHEETS_PER_ORDER = {MAX_SHEETS_PER_ORDER}")

# Configuration
DEFAULT_SHEET_TYPES = [
    (140, 200),
    (142, 200),
    (144, 200),
    (146, 200),
    (148, 200),
    (140, 195),
    (142, 195),
    (144, 195),
    (146, 195),
    (148, 195),
    (100, 100),
    (150, 150),
    (200, 300),
]
OUTPUT_FOLDER = "output_layouts"
os.makedirs(OUTPUT_FOLDER, exist_ok=True)


# Streamlit App
# Display logo at the very top
try:
    st.image("logo.png", use_container_width=True)
except FileNotFoundError:
    pass  # Skip logo if file not found

# Sheet Inventory Section
st.header("📋 Настройка доступных листов")
st.write("Укажите какие листы у вас есть в наличии и их количество.")

# Initialize session state for sheets
if "available_sheets" not in st.session_state:
    st.session_state.available_sheets = []

# Update existing sheets to have color if missing (for backward compatibility)
for sheet in st.session_state.available_sheets:
    if "color" not in sheet:
        sheet["color"] = "серый"  # Default color for existing sheets

# Add new sheet type
st.subheader("Добавить тип листа")
col1, col2, col3 = st.columns([2, 2, 1])

with col1:
    sheet_type_option = st.selectbox(
        "Выберите размер листа (см)",
        ["Произвольный"] + [f"{w}x{h}" for w, h in DEFAULT_SHEET_TYPES],
        key="sheet_type_select",
    )

    if sheet_type_option == "Произвольный":
        sheet_width = st.number_input(
            "Ширина (см)",
            min_value=50,
            max_value=1000,
            step=1,
            value=140,
            key="custom_width",
        )
        sheet_height = st.number_input(
            "Высота (см)",
            min_value=50,
            max_value=1000,
            step=1,
            value=200,
            key="custom_height",
        )
        selected_size = (sheet_width, sheet_height)
    else:
        selected_size = tuple(map(int, sheet_type_option.split("x")))

    # Color selection
    sheet_color = st.selectbox("Цвет листа", ["чёрный", "серый"], key="sheet_color")

with col2:
    sheet_count = st.number_input(
        "Количество листов", min_value=1, max_value=100, value=5, key="sheet_count"
    )
    sheet_name = st.text_input(
        "Название типа листа (опционально)",
        value=f"Лист {selected_size[0]}x{selected_size[1]} {sheet_color}",
        key="sheet_name",
    )

with col3:
    st.write("")
    st.write("")
    if st.button("➕ Добавить", key="add_sheet"):
        new_sheet = {
            "name": sheet_name,
            "width": selected_size[0],
            "height": selected_size[1],
            "color": sheet_color,
            "count": sheet_count,
            "used": 0,
        }
        st.session_state.available_sheets.append(new_sheet)
        st.success(
            f"Добавлен тип листа: {new_sheet['name']} ({new_sheet['count']} шт.)"
        )
        st.rerun()

# Display current sheet inventory
if st.session_state.available_sheets:
    st.subheader("📊 Доступные листы")

    # Create DataFrame for display
    sheets_data = []
    total_sheets = 0
    for i, sheet in enumerate(st.session_state.available_sheets):
        # Add color indicator
        color = sheet.get("color", "не указан")
        color_emoji = "⚫" if color == "чёрный" else "⚪" if color == "серый" else "🔘"
        color_display = f"{color_emoji}"

        sheets_data.append(
            {
                "№": i + 1,
                "Название": sheet["name"],
                "Размер (см)": f"{sheet['width']}x{sheet['height']}",
                "Цвет": color_display,
                "Доступно": f"{sheet['count'] - sheet['used']}/{sheet['count']}",
                "Использовано": sheet["used"],
            }
        )
        total_sheets += sheet["count"]

    sheets_df = pd.DataFrame(sheets_data)
    st.dataframe(sheets_df, use_container_width=True)

    col1, col2 = st.columns([3, 1])
    with col1:
        st.metric("Всего листов в наличии", total_sheets)
    with col2:
        if st.button("🗑️ Очистить все", key="clear_sheets"):
            st.session_state.available_sheets = []
            st.rerun()
else:
    st.info("Добавьте типы листов, которые у вас есть в наличии.")

# Order Loading Section
st.header("📋 Загрузка заказов из Excel таблицы")

# Initialize session state for orders
if "selected_orders" not in st.session_state:
    st.session_state.selected_orders = []
if "manual_files" not in st.session_state:
    st.session_state.manual_files = []

# Excel file upload
excel_file = st.file_uploader(
    "Загрузите файл заказов Excel", type=["xlsx", "xls"], key="excel_upload"
)


@st.cache_data(ttl=600)  # Cache for 10 minutes
def load_excel_file(file_content):
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
        return {"ZAKAZ": excel_data}
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


if excel_file is not None:
    try:
        with st.spinner("Загрузка Excel файла..."):
            # Read Excel file with caching - use file hash for cache key
            file_content = excel_file.read()
            file_hash = hash(file_content)
            excel_data = load_excel_file(file_content)
            logger.info(f"Excel файл загружен. Листы: {list(excel_data.keys())}")

        # Process only the "ZAKAZ" sheet
        all_orders = []
        target_sheet = "ZAKAZ"

        if target_sheet in excel_data:
            sheet_name = target_sheet
            df = excel_data[sheet_name]

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
                            unique_order_id = f"{sheet_name}_row_{idx}"

                            order = {
                                "sheet": sheet_name,
                                "row_index": idx,
                                "date": str(row.iloc[0])
                                if pd.notna(row.iloc[0])
                                else "",
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
            st.warning(
                f"⚠️ Лист '{target_sheet}' не найден в Excel файле. Доступные листы: {list(excel_data.keys())}"
            )

        if all_orders:
            st.success(f"✅ Найдено {len(all_orders)} невыполненных заказов")
            logger.info(f"Найдено {len(all_orders)} невыполненных заказов в Excel")

            # Display orders for selection
            st.subheader("📝 Выберите заказы для раскроя")

            # Add search/filter options
            col_filter1, col_filter2 = st.columns([1, 1])
            with col_filter1:
                search_article = st.text_input(
                    "🔍 Поиск по артикулу:",
                    placeholder="Введите часть артикула",
                    key="search_article",
                )
            with col_filter2:
                search_product = st.text_input(
                    "🔍 Поиск по товару:",
                    placeholder="Введите часть названия",
                    key="search_product",
                )

            # Filter orders based on search
            filtered_orders = all_orders
            if search_article:
                filtered_orders = [
                    order
                    for order in filtered_orders
                    if search_article.lower() in order["article"].lower()
                ]
            if search_product:
                filtered_orders = [
                    order
                    for order in filtered_orders
                    if search_product.lower() in order["product"].lower()
                ]

            if filtered_orders != all_orders:
                st.info(
                    f"🔍 Найдено {len(filtered_orders)} заказов из {len(all_orders)} (применены фильтры)"
                )

            # Update all_orders with filtered results for display
            display_orders = filtered_orders

            # Create selection interface with all orders (no pagination)
            orders_to_show = display_orders
            start_idx = 0

            # Display orders with interactive controls
            if orders_to_show:
                # Interactive table with controls for each row
                st.markdown("**Выберите заказы для раскроя:**")

                # Prepare data for DataFrame display
                orders_data = []
                for i, order in enumerate(orders_to_show):
                    actual_idx = start_idx + i

                    # Get current selection state and quantity
                    is_selected = st.session_state.get(f"order_{actual_idx}", False)
                    current_qty = st.session_state.get(f"quantity_{actual_idx}", 1)

                    # Color emoji
                    color = order.get("color", "серый")
                    color_emoji = (
                        "⚫"
                        if color == "чёрный"
                        else "⚪"
                        if color == "серый"
                        else "🔘"
                    )

                    orders_data.append(
                        {
                            "№": actual_idx + 1,
                            "Выбрать": "✓" if is_selected else "",
                            "Кол-во": current_qty,
                            "Артикул": order["article"],
                            "Товар": order["product"][:40] + "..."
                            if len(order["product"]) > 40
                            else order["product"],
                            "Тип": order.get("product_type", ""),
                            "Цвет": color_emoji,
                            "Дата": order.get("date", "")[:10]
                            if order.get("date", "")
                            else "",
                            "Кант цвет": order.get("border_color", ""),
                        }
                    )

                # Create columns for interactive controls
                for i, order in enumerate(orders_to_show):
                    actual_idx = start_idx + i

                    cols = st.columns([1, 2, 10, 6, 3, 3])

                    # Selection checkbox
                    with cols[0]:
                        is_selected = st.checkbox(
                            f"№{actual_idx + 1}",
                            value=st.session_state.get(f"order_{actual_idx}", False),
                            key=f"select_{actual_idx}",
                            label_visibility="collapsed",
                        )
                        st.session_state[f"order_{actual_idx}"] = is_selected

                    # Quantity number input
                    with cols[1]:
                        quantity = st.number_input(
                            f"Количество для заказа {actual_idx + 1}",
                            min_value=1,
                            max_value=100,
                            value=st.session_state.get(f"quantity_{actual_idx}", 1),
                            key=f"qty_{actual_idx}",
                            label_visibility="collapsed",
                        )
                        st.session_state[f"quantity_{actual_idx}"] = quantity

                    # Display order info for reference
                    with cols[2]:
                        st.write(f"**{order['article']}**")

                    with cols[3]:
                        product_text = (
                            order["product"][:30] + "..."
                            if len(order["product"]) > 30
                            else order["product"]
                        )
                        st.write(product_text)

                    with cols[4]:
                        color = order.get("color", "серый")
                        color_emoji = (
                            "⚫"
                            if color == "чёрный"
                            else "⚪"
                            if color == "серый"
                            else "🔘"
                        )
                        st.write(f"{color_emoji} {order.get('product_type', '')}")

                    with cols[5]:
                        st.write(order.get("border_color", ""))

                # Bulk controls
                col1, col2 = st.columns([1, 1])
                with col1:
                    if st.button("✅ Выбрать все", key="select_all_orders"):
                        for i in range(len(orders_to_show)):
                            st.session_state[f"order_{start_idx + i}"] = True
                        st.rerun()

                with col2:
                    if st.button("❌ Снять выбор", key="deselect_all_orders"):
                        for i in range(len(orders_to_show)):
                            st.session_state[f"order_{start_idx + i}"] = False
                        st.rerun()

            # Collect all selected orders, multiplying by quantity
            all_selected_orders = []
            for i in range(len(display_orders)):
                if st.session_state.get(f"order_{i}", False):
                    order = display_orders[i]
                    quantity = st.session_state.get(f"quantity_{i}", 1)

                    # Add the order multiple times based on quantity
                    for repeat_num in range(quantity):
                        # Create a copy of the order with a unique identifier
                        repeated_order = order.copy()
                        repeated_order["repeat_index"] = repeat_num + 1
                        repeated_order["original_index"] = i

                        # Make order_id unique for each repeat
                        if quantity > 1:
                            repeated_order["order_id"] = (
                                f"{order['order_id']}_повтор_{repeat_num + 1}"
                            )

                        all_selected_orders.append(repeated_order)

            if all_selected_orders:
                # Count unique orders
                unique_orders = len(
                    set(
                        order.get("original_index", i)
                        for i, order in enumerate(all_selected_orders)
                    )
                )
                total_orders = len(all_selected_orders)

                st.info(f"📋 Выбрано {len(all_selected_orders)} заказов")

                # Store selected orders in session state
                st.session_state.selected_orders = all_selected_orders
                logger.info(f"Выбрано {len(all_selected_orders)} заказов для обработки")
                # Log only first few orders to avoid slowdown
                if len(all_selected_orders) <= 5:
                    for order in all_selected_orders:
                        logger.info(
                            f"  Заказ {order.get('order_id', 'N/A')}: {order.get('article', 'N/A')}"
                        )
                else:
                    # Log only first 3 and last 2 for large lists
                    for order in all_selected_orders[:3]:
                        logger.info(
                            f"  Заказ {order.get('order_id', 'N/A')}: {order.get('article', 'N/A')}"
                        )
                    logger.info(
                        f"  ... (пропущено {len(all_selected_orders) - 5} заказов) ..."
                    )
                    for order in all_selected_orders[-2:]:
                        logger.info(
                            f"  Заказ {order.get('order_id', 'N/A')}: {order.get('article', 'N/A')}"
                        )
        else:
            st.warning("⚠️ Не найдено невыполненных заказов в указанных месяцах")

    except Exception as e:
        st.error(f"❌ Ошибка обработки Excel файла: {e}")
        logger.error(f"Ошибка при обработке Excel: {e}")
        import traceback

        logger.error(f"Полная трассировка ошибки: {traceback.format_exc()}")
        st.error("💡 **Возможные решения:**")
        st.error("• Сохраните Excel файл в новом формате (.xlsx)")
        st.error("• Проверьте правильность дат в файле")
        st.error(
            "• Убедитесь, что в датах нет некорректных значений (например, 30 февраля)"
        )

# Initialize auto_loaded_files
auto_loaded_files = []

# DXF files will be loaded on demand during optimization
# This section shows what will be processed when optimization starts
if st.session_state.selected_orders:
    # st.subheader("📋 Готовые к обработке заказы")

    # st.success(f"✅ Выбрано {len(st.session_state.selected_orders)} заказов")
    # st.info("💡 DXF файлы будут загружены при нажатии кнопки 'Оптимизировать раскрой' для ускорения интерфейса.")

    # Show preview of what will be loaded
    articles_found = []
    articles_not_found = []

    # Create a file-like object with name attribute
    class FileObj:
        def __init__(self, content, name):
            self.content = BytesIO(content)
            self.name = name

        def read(self):
            return self.content.read()

        def seek(self, pos):
            return self.content.seek(pos)

    def get_dxf_files_for_product_type(article, product_name, product_type):
        """Get DXF files for a specific product type based on the mapping rules."""

        found_files = []

        logger.info(
            f"Поиск DXF файлов: артикул='{article}', товар='{product_name}', тип='{product_type}'"
        )

        # Find the base folder for this article/product
        base_folder = find_product_folder(article, product_name)

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
                logger.warning(
                    f"Неизвестный тип изделия: {product_type}, берем все файлы"
                )
                found_files = all_dxf_files

        logger.info(
            f"Результат поиска для типа '{product_type}': найдено {len(found_files)} файлов"
        )
        if found_files:
            logger.debug(
                f"Найденные файлы: {[os.path.basename(f) for f in found_files]}"
            )

        return found_files

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
                            logger.info(
                                f"Найдено специальное соответствие: {folder_path}"
                            )
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

    def calculate_folder_match_score(search_term, folder_name):
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
    def find_dxf_files_for_article(article, product_name="", product_type=""):
        """Find DXF files for a given article using the new product type mapping."""
        if product_type:
            return get_dxf_files_for_product_type(article, product_name, product_type)
        else:
            # Fallback to old behavior if product_type not provided
            base_folder = find_product_folder(article, product_name)
            if base_folder:
                found_files = []
                dxf_folder = os.path.join(base_folder, "DXF")
                search_folder = (
                    dxf_folder if os.path.exists(dxf_folder) else base_folder
                )

                try:
                    for file in os.listdir(search_folder):
                        if file.lower().endswith(".dxf"):
                            found_files.append(os.path.join(search_folder, file))
                except OSError:
                    pass

                return found_files
            return []


# Additional DXF files section (always available)
st.subheader("📎 Загрузить вручную")
st.write(
    "Добавьте DXF файлы группами. Каждая группа будет иметь свои настройки цвета и количества."
)

# Initialize session state for file groups
if "file_groups" not in st.session_state:
    st.session_state.file_groups = []
if "group_counter" not in st.session_state:
    st.session_state.group_counter = 1

# File uploader for new files - each selection creates a new group
# Use group_counter in key to reset uploader after each group creation
uploader_key = f"manual_dxf_{len(st.session_state.file_groups)}"
manual_files = st.file_uploader(
    "Выберите DXF файлы (будет создана новая группа)",
    type=["dxf"],
    accept_multiple_files=True,
    key=uploader_key,
)

# Process newly uploaded files - show settings and create group when ready
if manual_files:
    # Store current files for this group configuration
    current_group_key = f"current_group_{len(st.session_state.file_groups)}"

    st.write(f"**Новая группа #{st.session_state.group_counter}:**")

    # Settings for this group
    col1, col2, col3 = st.columns([1, 1, 1])

    with col1:
        group_color = st.selectbox(
            "Цвет листа:",
            options=["чёрный", "серый"],
            index=0,
            key=f"color_{current_group_key}",
            help="Цвет листа для всех файлов группы",
        )

    with col2:
        group_quantity = st.number_input(
            "Количество копий:",
            min_value=1,
            max_value=50,
            value=1,
            key=f"qty_{current_group_key}",
            help="Копий каждого файла",
        )

    with col3:
        group_priority = st.selectbox(
            "Приоритет:",
            options=[1, 2],
            index=1,  # Default to priority 2
            key=f"priority_{current_group_key}",
            help="1 - размещается наравне с Excel файлами, 2 - заполняет пустоты на листах",
        )

    # Button to create group with current settings
    if st.button(
        f"➕ Создать группу #{st.session_state.group_counter}",
        key=f"create_group_{current_group_key}",
    ):
        # Create group with selected settings
        group_files = []
        group_name = f"Группа #{st.session_state.group_counter}"

        for file in manual_files:
            # Store file content to avoid issues with file handles
            file.seek(0)
            file_content = file.read()

            for copy_num in range(group_quantity):
                import io

                file_copy = io.BytesIO(file_content)
                file_copy.name = file.name
                file_copy.color = group_color
                file_copy.priority = group_priority
                file_copy.order_id = f"group_{st.session_state.group_counter}"
                file_copy.copy_number = copy_num + 1
                file_copy.original_name = file.name
                file_copy.group_id = st.session_state.group_counter

                # Create unique name for multiple copies
                if group_quantity > 1:
                    base_name = file.name.replace(".dxf", "")
                    file_copy.display_name = f"{base_name}_копия_{copy_num + 1}.dxf"
                else:
                    file_copy.display_name = file.name

                file_copy.copy_info = f"copy_{copy_num + 1}_of_{group_quantity}"
                group_files.append(file_copy)

        # Add group to session state
        new_group = {
            "id": st.session_state.group_counter,
            "name": group_name,
            "files": [f.name for f in manual_files],
            "color": group_color,
            "priority": group_priority,
            "quantity": group_quantity,
            "total_objects": len(manual_files) * group_quantity,
            "file_objects": group_files,
        }

        st.session_state.file_groups.append(new_group)
        st.session_state.group_counter += 1

        st.success(
            f"✅ Группа создана: {len(manual_files)} файлов × {group_quantity} копий = {len(group_files)} объектов (приоритет {group_priority})"
        )

        # Force rerun to reset uploader
        st.rerun()

    # Show preview of what will be created
    total_objects = len(manual_files) * group_quantity
    color_emoji = "⚫" if group_color == "чёрный" else "⚪"


# Display existing groups table
if st.session_state.file_groups:
    st.subheader("📋 Загруженные группы файлов")

    groups_data = []
    total_objects = 0

    for group in st.session_state.file_groups:
        color_emoji = "⚫" if group["color"] == "чёрный" else "⚪"
        files_list = ", ".join(group["files"][:3])  # Show first 3 files
        if len(group["files"]) > 3:
            files_list += f" и ещё {len(group['files']) - 3}..."

        groups_data.append(
            {
                "Группа": group["name"],
                "Файлы": files_list,
                "Цвет": f"{color_emoji} {group['color']}",
                "Приоритет": group.get("priority", 2),
                "Копий на файл": group["quantity"],
            }
        )
        total_objects += group["total_objects"]

    groups_df = pd.DataFrame(groups_data)
    st.dataframe(groups_df, use_container_width=True)

    col1, col2 = st.columns([3, 1])
    with col1:
        st.metric("Всего объектов во всех группах", total_objects)
    with col2:
        if st.button("🗑️ Очистить все группы", key="clear_all_groups"):
            st.session_state.file_groups = []
            st.session_state.group_counter = 1
            st.rerun()

    # Prepare all files for processing (flatten all groups)
    all_manual_files = []
    for group in st.session_state.file_groups:
        all_manual_files.extend(group["file_objects"])

    st.session_state.manual_files = all_manual_files
else:
    st.session_state.manual_files = []


# Legacy compatibility - no longer needed but kept for backward compatibility
if "manual_file_settings" not in st.session_state:
    st.session_state.manual_file_settings = {}

# Show status messages based on what's available
has_manual_files = len(st.session_state.file_groups) > 0
if st.session_state.selected_orders and has_manual_files:
    st.info("💡 Будут обработаны заказы из Excel + дополнительные файлы")
elif st.session_state.selected_orders:
    st.info("💡 Будут обработаны только заказы из Excel таблицы")
elif has_manual_files:
    st.info("💡 Будут обработаны только дополнительные файлы")
else:
    st.warning(
        "⚠️ Загрузите Excel файл с заказами или добавьте DXF файлы вручную для продолжения"
    )

if st.button("🚀 Оптимизировать раскрой"):
    logger.info("=== НАЧАЛО ОПТИМИЗАЦИИ РАСКРОЯ ===")
    if not st.session_state.available_sheets:
        logger.error("Нет доступных листов для оптимизации")
        st.error("⚠️ Пожалуйста, добавьте хотя бы один тип листа в наличии.")
    elif not st.session_state.selected_orders and not st.session_state.manual_files:
        logger.error("Нет файлов для оптимизации")
        st.error(
            "⚠️ Пожалуйста, выберите заказы из Excel таблицы или добавьте DXF файлы вручную."
        )
    else:
        # Now load DXF files on demand
        st.header("📥 Загрузка DXF файлов")

        # Load files from selected orders
        auto_loaded_files = []
        manual_files_with_color = []

        # Create FileObj class for this context
        class FileObj:
            def __init__(self, content, name):
                self.content = BytesIO(content)
                self.name = name

            def read(self):
                return self.content.read()

            def seek(self, pos):
                return self.content.seek(pos)

        # Load files from orders
        progress_bar = st.progress(0)
        status_text = st.empty()

        total_orders = len(st.session_state.selected_orders)
        for i, order in enumerate(st.session_state.selected_orders):
            progress = (i + 1) / total_orders
            progress_bar.progress(progress)
            status_text.text(
                f"Загружаем файлы для заказа {i + 1}/{total_orders}: {order['product'][:50]}..."
            )

            article = order["article"]
            product = order["product"]
            product_type = order.get("product_type", "")

            logger.info(
                f"Обрабатываем заказ: артикул={article}, товар={product}, тип={product_type}"
            )

            found_dxf_files = find_dxf_files_for_article(article, product, product_type)

            if found_dxf_files:
                logger.info(
                    f"Найдено {len(found_dxf_files)} DXF файлов для типа '{product_type}'"
                )
                for file_path in found_dxf_files:
                    try:
                        with open(file_path, "rb") as f:
                            file_content = f.read()

                        display_name = f"{product}_{os.path.basename(file_path)}"
                        file_obj = FileObj(file_content, display_name)
                        file_obj.color = order.get("color", "серый")
                        file_obj.order_id = order.get("order_id", "unknown")
                        auto_loaded_files.append(file_obj)
                        logger.debug(
                            f"Загружен файл {display_name} для заказа {file_obj.order_id}"
                        )
                    except Exception as e:
                        st.warning(f"⚠️ Ошибка загрузки {file_path}: {e}")
            else:
                st.warning(
                    f"⚠️ Не найдены DXF файлы для заказа: {product} (тип: {product_type})"
                )

        # Load manual files if any (already configured with colors and quantities)
        if hasattr(st.session_state, "manual_files") and st.session_state.manual_files:
            for file in st.session_state.manual_files:
                # Files are already configured with color, order_id, and display_name
                manual_files_with_color.append(file)

        # Combine all files
        dxf_files = auto_loaded_files + manual_files_with_color

        progress_bar.empty()
        status_text.text(
            f"✅ Загружено {len(dxf_files)} файлов ({len(auto_loaded_files)} из заказов, {len(manual_files_with_color)} дополнительных)"
        )

        logger.info(
            f"Начинаем оптимизацию с {len(dxf_files)} DXF файлами и {len(st.session_state.available_sheets)} типами листов"
        )
        # Parse DXF files
        st.header("📄 Обработка DXF файлов")
        carpets = []
        original_dxf_data_map = {}  # Store original DXF data for each file

        # Parse loaded DXF files
        logger.info("Начинаем парсинг DXF файлов...")

        # Show progress for file parsing
        progress_bar = st.progress(0)
        status_text = st.empty()

        for idx, file in enumerate(dxf_files):
            # Update progress
            progress = (idx + 1) / len(dxf_files)
            progress_bar.progress(progress)

            # Use display_name if available (for manual files with copies), otherwise use file.name
            display_name = getattr(file, "display_name", file.name)
            status_text.text(f"Парсим файл {idx + 1}/{len(dxf_files)}: {display_name}")

            file.seek(0)
            file_bytes = BytesIO(file.read())
            parsed_data = parse_dxf_complete(file_bytes, verbose=False)
            if parsed_data and parsed_data["combined_polygon"]:
                # Add color and order information to polygon tuple
                file_color = getattr(file, "color", "серый")
                file_order_id = getattr(file, "order_id", "unknown")
                file_priority = getattr(
                    file, "priority", 1
                )  # Default priority 1 for Excel files

                # DEBUG: Log all file attributes to understand the issue
                file_attrs = [attr for attr in dir(file) if not attr.startswith("_")]
                logger.debug(f"ФАЙЛ {display_name}: атрибуты = {file_attrs}")
                logger.debug(
                    f"ФАЙЛ {display_name}: color = {file_color}, order_id = {file_order_id}, priority = {file_priority}"
                )

                # Use the display_name for polygon identification, include priority
                carpet = Carpet(
                    parsed_data["combined_polygon"],
                    display_name,
                    file_color,
                    file_order_id,
                    file_priority,  # Add priority as 5th element
                )
                carpets.append(carpet)
                logger.info(f"ДОБАВЛЕН ПОЛИГОН: order_id={carpet.order_id}")
                # Store original DXF data using display_name as key
                original_dxf_data_map[display_name] = parsed_data
                logger.info(
                    f"СОЗДАН ПОЛИГОН: файл={display_name}, заказ={file_order_id}, цвет={file_color}"
                )
            else:
                logger.warning(f"Не удалось получить полигон из файла {display_name}")

        # Clear progress indicators
        progress_bar.empty()
        status_text.text(
            f"✅ Обработка завершена. Загружено {len(carpets)} полигонов из {len(dxf_files)} файлов"
        )

        if not carpets:
            st.error("В загруженных DXF файлах не найдено валидных полигонов")
            st.stop()

        # Show order distribution before optimization
        order_counts = {}
        for carpet in carpets:
            order_counts[carpet.order_id] = order_counts.get(carpet.order_id, 0) + 1

        logger.info(f"Анализ заказов: найдено {len(order_counts)} уникальных заказов")
        for order_id, count in order_counts.items():
            logger.info(f"  • Заказ {order_id}: {count} файлов")

        # Optional input visualization (button-triggered)
        if st.button("📊 Показать исходные файлы", key="show_input_visualization"):
            st.subheader("🔍 Визуализация входных файлов")
            input_plots = plot_input_polygons(carpets)
            if input_plots:
                # Show color legend
                with st.expander("🎨 Цветовая схема файлов", expanded=False):
                    legend_cols = st.columns(min(5, len(carpets)))
                    for i, carpet in enumerate(carpets):
                        with legend_cols[i % len(legend_cols)]:
                            from layout_optimizer import get_color_for_file

                            color = get_color_for_file(carpet.filename)
                            # Convert RGB to hex for HTML
                            color_hex = f"#{int(color[0]*255):02x}{int(color[1]*255):02x}{int(color[2]*255):02x}"
                            st.markdown(
                                f'<div style="background-color: {color_hex}; padding: 10px; border-radius: 5px; text-align: center; margin: 2px;"><b>{carpet.filename}</b></div>',
                                unsafe_allow_html=True,
                            )

                cols = st.columns(min(3, len(input_plots)))
                for i, (file_name, plot_buf) in enumerate(input_plots.items()):
                    with cols[i % len(cols)]:
                        st.image(
                            plot_buf, caption=f"{file_name}", use_container_width=True
                        )

        # Store original dimensions for comparison later
        original_dimensions = {}

        # Create a summary table with proper unit conversion
        summary_data = []
        total_area_cm2 = 0
        for carpet in carpets:
            poly = carpet.polygon
            bounds = poly.bounds
            width_mm = bounds[2] - bounds[0]
            height_mm = bounds[3] - bounds[1]
            area_mm2 = poly.area

            # Convert from mm to cm
            width_cm = width_mm / 10.0
            height_cm = height_mm / 10.0
            area_cm2 = area_mm2 / 100.0

            # Store original dimensions
            original_dimensions[carpet.filename] = {
                "width_cm": width_cm,
                "height_cm": height_cm,
                "area_cm2": area_cm2,
            }

            total_area_cm2 += area_cm2
            # Add color emoji for display
            color_emoji = (
                "⚫" if color == "чёрный" else "⚪" if color == "серый" else "🔘"
            )
            color_display = f"{color_emoji} {color}"

            summary_data.append(
                {
                    "Файл": carpet.filename,
                    "Ширина (см)": f"{width_cm:.1f}",
                    "Высота (см)": f"{height_cm:.1f}",
                    "Площадь (см²)": f"{area_cm2:.2f}",
                    "Цвет": color_display,
                }
            )

        # Calculate theoretical minimum using largest available sheet
        largest_sheet_area = max(
            sheet["width"] * sheet["height"]
            for sheet in st.session_state.available_sheets
        )

        # Find largest sheet for scaling reference
        max_sheet_area = 0
        reference_sheet_size = (140, 200)  # default fallback
        for sheet in st.session_state.available_sheets:
            area = sheet["width"] * sheet["height"]
            if area > max_sheet_area:
                max_sheet_area = area
                reference_sheet_size = (sheet["width"], sheet["height"])

        # Полигоны остаются в исходном масштабе (не масштабируются)
        logger.info(
            f"✅ Полигоны сохранены в исходном масштабе: {len(carpets)} объектов"
        )

        st.header("🔄 Процесс оптимизации")
        try:
            # Debug processing with detailed info
            # with st.expander("🔍 Подробная информация об оптимизации", expanded=False):
            #    debug_layouts, debug_unplaced = bin_packing_with_inventory(polygons, st.session_state.available_sheets, verbose=True, max_sheets_per_order=MAX_SHEETS_PER_ORDER)

            # Actual processing with progress tracking
            st.info("🔄 Запуск процесса оптимизации...")
            optimization_progress = st.progress(0)
            optimization_status = st.empty()

            # Initialize optimization
            optimization_progress.progress(10)
            optimization_status.text("Подготовка данных для оптимизации...")

            logger.info(
                f"Вызываем bin_packing_with_inventory с MAX_SHEETS_PER_ORDER={MAX_SHEETS_PER_ORDER}"
            )
            logger.info(
                f"Входные параметры: {len(carpets)} полигонов, {len(st.session_state.available_sheets)} типов листов"
            )

            # DEBUG: Log what polygons we're sending
            optimization_progress.progress(20)
            optimization_status.text("Анализ входных полигонов...")

            logger.info("ПОЛИГОНЫ ПЕРЕД ОТПРАВКОЙ В bin_packing_with_inventory:")
            for i, carpet in enumerate(carpets):
                logger.info(
                    f"  Полигон {i}: файл={carpet.filename}, order_id={carpet.order_id}"
                )

            # Main optimization step
            optimization_progress.progress(50)
            optimization_status.text("Выполнение алгоритма размещения...")

            # Progress callback function
            def update_progress(percent, status_text):
                optimization_progress.progress(int(percent))
                optimization_status.text(status_text)


            placed_layouts, unplaced_polygons = bin_packing_with_inventory(
                carpets,
                st.session_state.available_sheets,
                verbose=False,
                max_sheets_per_order=MAX_SHEETS_PER_ORDER,
                progress_callback=update_progress,
            )

            # Processing results
            optimization_progress.progress(80)
            optimization_status.text("Обработка результатов...")

            logger.info(
                f"Результат bin_packing: {len(placed_layouts)} размещенных листов, {len(unplaced_polygons)} неразмещенных полигонов"
            )

            # Finalize
            optimization_progress.progress(100)
            optimization_status.text("✅ Оптимизация завершена.")

            # Clear progress indicators after a moment
            import time

            time.sleep(1)
            optimization_progress.empty()
            optimization_status.empty()

        except ValueError as e:
            # Handle order constraint violations
            if "Нарушение ограничений заказов" in str(e):
                st.error(f"❌ {str(e)}")
                st.info(
                    f"💡 **Решение**: Увеличьте константу MAX_SHEETS_PER_ORDER (сейчас: {MAX_SHEETS_PER_ORDER}) или разделите файлы заказа на несколько частей."
                )
                st.stop()
            else:
                # Re-raise other ValueError exceptions
                raise

        # Convert to old format for compatibility with existing display code
        st.info("🔨 Создание выходных файлов и визуализаций...")
        results_progress = st.progress(0)
        results_status = st.empty()

        all_layouts = []
        report_data = []

        total_layouts = len(placed_layouts)
        for i, layout in enumerate(placed_layouts):
            # Update progress
            progress_value = (
                int((i / total_layouts) * 100) if total_layouts > 0 else 100
            )
            results_progress.progress(progress_value)
            results_status.text(
                f"Создание файла {i + 1}/{total_layouts}: лист {layout['sheet_number']}"
            )

            # Save and visualize layout with new naming format: length_width_number_color.dxf
            sheet_width = int(layout["sheet_size"][0])
            sheet_height = int(layout["sheet_size"][1])
            sheet_number = layout["sheet_number"]

            # Find sheet color from original sheet data
            sheet_color = "не указан"
            color_suffix = "unknown"

            # Try to get sheet color from layout first, then match by name
            if "sheet_color" in layout:
                sheet_color = layout["sheet_color"]
            elif "sheet_type" in layout:
                for sheet in st.session_state.available_sheets:
                    if sheet["name"] == layout["sheet_type"]:
                        sheet_color = sheet.get("color", "не указан")
                        break
            else:
                # Fallback: use first available sheet color
                if st.session_state.available_sheets:
                    sheet_color = st.session_state.available_sheets[0].get(
                        "color", "не указан"
                    )

            # Convert color name to English suffix
            if sheet_color == "чёрный":
                color_suffix = "black"
            elif sheet_color == "серый":
                color_suffix = "gray"
            else:
                color_suffix = "unknown"

            output_filename = (
                f"{sheet_height}_{sheet_width}_{sheet_number}_{color_suffix}.dxf"
            )
            output_file = os.path.join(OUTPUT_FOLDER, output_filename)

            save_dxf_layout_complete(
                layout["placed_polygons"],
                layout["sheet_size"],
                output_file,
                original_dxf_data_map,
            )
            layout_plot = plot_layout(layout["placed_polygons"], layout["sheet_size"])

            # Store layout info in old format for compatibility
            shapes_count = len(layout["placed_polygons"])
            logger.info(
                f"Лист #{layout['sheet_number']}: создаем all_layouts запись с {shapes_count} размещенными полигонами"
            )

            # Определяем тип листа с проверкой наличия ключа
            if "sheet_type" in layout:
                sheet_type = layout["sheet_type"]
            elif "sheet_color" in layout:
                sheet_type = layout["sheet_color"]
            else:
                # Fallback: используем первый доступный лист как тип
                if st.session_state.available_sheets:
                    sheet_type = st.session_state.available_sheets[0].get(
                        "name", "Unknown"
                    )
                else:
                    sheet_type = "Unknown"

            all_layouts.append(
                {
                    "Sheet": layout["sheet_number"],
                    "Sheet Type": sheet_type,
                    "Sheet Color": sheet_color,
                    "Sheet Size": f"{layout['sheet_size'][0]}x{layout['sheet_size'][1]} см",
                    "Output File": output_file,
                    "Plot": layout_plot,
                    "Shapes Placed": shapes_count,
                    "Material Usage (%)": f"{layout['usage_percent']:.2f}",
                    "Placed Polygons": layout["placed_polygons"],
                }
            )
            report_data.extend(
                [
                    (p[4], layout["sheet_number"], output_file)
                    for p in layout["placed_polygons"]
                ]
            )

        # Finalize results processing
        results_progress.progress(100)
        results_status.text("✅ Все файлы созданы.")

        # Update sheet inventory in session state
        for layout in placed_layouts:
            # Определяем тип листа с проверкой наличия ключа
            layout_sheet_type = None
            if "sheet_type" in layout:
                layout_sheet_type = layout["sheet_type"]
            elif "sheet_color" in layout:
                # Если нет sheet_type, попробуем найти лист по цвету и размеру
                sheet_color = layout["sheet_color"]
                sheet_size = layout.get("sheet_size", (0, 0))
                for sheet in st.session_state.available_sheets:
                    if (
                        sheet.get("color", "") == sheet_color
                        and sheet.get("width", 0) == sheet_size[0]
                        and sheet.get("height", 0) == sheet_size[1]
                    ):
                        layout_sheet_type = sheet["name"]
                        break

            if layout_sheet_type:
                for original_sheet in st.session_state.available_sheets:
                    if layout_sheet_type == original_sheet["name"]:
                        original_sheet["used"] += 1
                        break

        # Clear progress indicators
        import time

        time.sleep(1)
        results_progress.empty()
        results_status.empty()

        # Save results to session state to prevent loss on rerun
        st.session_state.optimization_results = {
            "all_layouts": all_layouts,
            "report_data": report_data,
            "unplaced_polygons": unplaced_polygons,
            "polygons_count": len(carpets),
            "placed_layouts": placed_layouts,  # Raw results from bin_packing
            "original_dxf_data_map": original_dxf_data_map,
            "original_dimensions": original_dimensions,
        }

# Display Results (moved outside the optimization block)
if "optimization_results" in st.session_state and st.session_state.optimization_results:
    # Add button to clear results
    if st.button(
        "🗑️ Очистить результаты",
        help="Очистить результаты оптимизации для нового расчета",
    ):
        st.session_state.optimization_results = None
        st.rerun()

if "optimization_results" in st.session_state and st.session_state.optimization_results:
    results = st.session_state.optimization_results
    all_layouts = results["all_layouts"]
    report_data = results["report_data"]
    unplaced_polygons = results["unplaced_polygons"]
    polygons_count = results["polygons_count"]
    placed_layouts = results["placed_layouts"]
    original_dxf_data_map = results["original_dxf_data_map"]
    original_dimensions = results.get("original_dimensions", {})

    st.header("📊 Результаты")
    if all_layouts:
        st.success(f"✅ Успешно использовано листов: {len(all_layouts)}")

        # Summary statistics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Всего листов", len(all_layouts))
        with col2:
            # Calculate correctly: actual placed polygons from bin_packing result
            # Should equal total_input_polygons - len(unplaced_polygons)
            total_input_polygons = polygons_count
            actual_placed_count = total_input_polygons - len(unplaced_polygons)

            # Debug: log the calculation
            raw_count_from_layouts = sum(
                len(layout["placed_polygons"]) for layout in placed_layouts
            )
            logger.info(
                f"DEBUG подсчет: raw_from_layouts={raw_count_from_layouts}, calculated_placed={actual_placed_count}, input={total_input_polygons}, unplaced={len(unplaced_polygons)}"
            )

            logger.info(
                f"UI подсчет: actual_placed={actual_placed_count}, total_input={total_input_polygons}, unplaced={len(unplaced_polygons)}"
            )
            logger.info(
                f"Подробности по листам: {[(layout['sheet_number'], len(layout['placed_polygons'])) for layout in placed_layouts]}"
            )
            st.metric(
                "Размещено объектов", f"{actual_placed_count}/{total_input_polygons}"
            )
        with col3:
            avg_usage = sum(
                float(layout["Material Usage (%)"].replace("%", ""))
                for layout in all_layouts
            ) / len(all_layouts)
            st.metric("Средний расход материала", f"{avg_usage:.1f}%")
        with col4:
            if unplaced_polygons:
                st.metric(
                    "Не размещено",
                    len(unplaced_polygons),
                    delta=f"-{len(unplaced_polygons)}",
                    delta_color="inverse",
                )
            else:
                st.metric("Не размещено", 0, delta="Все размещено ✅")

        # Show updated inventory
        st.subheader("📦 Обновленный инвентарь листов")
        updated_sheets_data = []
        for sheet in st.session_state.available_sheets:
            # Add color indicator
            color = sheet.get("color", "не указан")
            color_emoji = (
                "⚫" if color == "чёрный" else "⚪" if color == "серый" else "🔘"
            )
            color_display = f"{color_emoji} {color}"

            updated_sheets_data.append(
                {
                    "Тип листа": sheet["name"],
                    "Размер (см)": f"{sheet['width']}x{sheet['height']}",
                    "Цвет": color_display,
                    "Было": sheet["count"],
                    "Использовано": sheet["used"],
                    "Осталось": sheet["count"] - sheet["used"],
                }
            )
        updated_df = pd.DataFrame(updated_sheets_data)
        st.dataframe(updated_df, use_container_width=True)

        # Detailed results table with sizes
        st.subheader("📋 Подробные результаты")

        # Create enhanced report with sizes
        enhanced_report_data = []
        for layout in all_layouts:
            for placed_tuple in layout["Placed Polygons"]:
                if len(placed_tuple) >= 6:  # New format with color
                    polygon, _, _, angle, file_name, color = placed_tuple[:6]
                else:  # Old format without color
                    polygon, _, _, angle, file_name = placed_tuple[:5]
                    color = "серый"
                bounds = polygon.bounds
                width_cm = (bounds[2] - bounds[0]) / 10
                height_cm = (bounds[3] - bounds[1]) / 10
                area_cm2 = polygon.area / 100

                # Compare with original dimensions
                original = original_dimensions.get(file_name, {})
                original_width = original.get("width_cm", 0)
                original_height = original.get("height_cm", 0)
                original_area = original.get("area_cm2", 0)

                scale_factor = (
                    (width_cm / original_width) if original_width > 0 else 1.0
                )

                size_comparison = f"{width_cm:.1f}×{height_cm:.1f}"
                if abs(scale_factor - 1.0) > 0.01:  # If scaled
                    size_comparison += (
                        f" (было {original_width:.1f}×{original_height:.1f})"
                    )

                enhanced_report_data.append(
                    {
                        "DXF файл": file_name,
                        "Номер листа": layout["Sheet"],
                        # "Размер (см)": size_comparison,
                        # "Площадь (см²)": f"{area_cm2:.2f}",
                        "Поворот (°)": f"{angle:.0f}",
                        "Выходной файл": layout["Output File"],
                    }
                )

        if enhanced_report_data:
            enhanced_df = pd.DataFrame(enhanced_report_data)
            st.dataframe(enhanced_df, use_container_width=True)
            # Also create simple report_df for export
            report_df = pd.DataFrame(
                report_data, columns=["DXF файл", "Номер листа", "Выходной файл"]
            )
        else:
            report_df = pd.DataFrame(
                report_data, columns=["DXF файл", "Номер листа", "Выходной файл"]
            )
            st.dataframe(report_df, use_container_width=True)

        # Sheet visualizations
        st.subheader("📐 Схемы раскроя листов")
        for layout in all_layouts:
            # Add color indicator emoji
            color_emoji = (
                "⚫"
                if layout["Sheet Color"] == "чёрный"
                else "⚪"
                if layout["Sheet Color"] == "серый"
                else "🔘"
            )

            st.write(
                f"**Лист №{layout['Sheet']}: {color_emoji} {layout['Sheet Type']} ({layout['Sheet Size']}) - {layout['Shapes Placed']} объектов - {layout['Material Usage (%)']}% расход**"
            )
            col1, col2 = st.columns([2, 1])
            with col1:
                st.image(
                    layout["Plot"],
                    caption=f"Раскрой листа №{layout['Sheet']} ({layout['Sheet Type']})",
                    use_container_width=True,
                )
            with col2:
                st.write(f"**Тип листа:** {layout['Sheet Type']}")
                st.write(f"**Цвет листа:** {color_emoji} {layout['Sheet Color']}")
                st.write(f"**Размер листа:** {layout['Sheet Size']}")
                st.write(f"**Размещено объектов:** {layout['Shapes Placed']}")
                st.write(f"**Расход материала:** {layout['Material Usage (%)']}%")
                with open(layout["Output File"], "rb") as f:
                    st.download_button(
                        label="📥 Скачать DXF",
                        data=f,
                        file_name=os.path.basename(layout["Output File"]),
                        mime="application/dxf",
                        key=f"download_{layout['Sheet']}",
                    )
            st.divider()  # Add visual separator between sheets
    else:
        st.error(
            "❌ Не было создано ни одного листа. Проверьте отладочную информацию выше."
        )

    # Show unplaced polygons if any
    if unplaced_polygons:
        st.warning(f"⚠️ {len(unplaced_polygons)} объектов не удалось разместить.")
        st.subheader("🚫 Неразмещенные объекты")
        unplaced_data = []
        for carpet in unplaced_polygons:
            unplaced_data.append(
                (carpet.filename, f"{carpet.polygon.area/100:.2f}", carpet.color)
            )

        unplaced_df = pd.DataFrame(
            unplaced_data, columns=["Файл", "Площадь (см²)", "Цвет"]
        )
        st.dataframe(unplaced_df, use_container_width=True)

    # Save report
    if all_layouts:
        report_file = os.path.join(
            OUTPUT_FOLDER,
            f"layout_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
        )

        # Use enhanced report if available, otherwise simple report
        if enhanced_report_data:
            enhanced_df.to_excel(report_file, index=False)
        elif "report_df" in locals():
            report_df.to_excel(report_file, index=False)
        else:
            # Fallback: create simple report from report_data
            fallback_df = pd.DataFrame(
                report_data, columns=["DXF файл", "Номер листа", "Выходной файл"]
            )
            fallback_df.to_excel(report_file, index=False)

        # Create ZIP archive with all DXF files
        zip_filename = f"layout_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        zip_path = os.path.join(OUTPUT_FOLDER, zip_filename)

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            # Add all DXF layout files
            for layout in all_layouts:
                dxf_file_path = layout["Output File"]
                if os.path.exists(dxf_file_path):
                    # Use the new naming format for files in zip
                    arcname = os.path.basename(dxf_file_path)
                    zipf.write(dxf_file_path, arcname)

            # Add report file
            if os.path.exists(report_file):
                zipf.write(report_file, os.path.basename(report_file))

        # Download buttons
        col1, col2 = st.columns([1, 1])

        with col1:
            with open(report_file, "rb") as f:
                st.download_button(
                    label="📊 Скачать отчет Excel",
                    data=f,
                    file_name=os.path.basename(report_file),
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )

        with col2:
            with open(zip_path, "rb") as f:
                st.download_button(
                    label="📦 Скачать все файлы (ZIP)",
                    data=f,
                    file_name=zip_filename,
                    mime="application/zip",
                )
