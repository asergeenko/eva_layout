import streamlit as st
import pandas as pd
import os
from datetime import datetime
from io import BytesIO
import zipfile
import logging

from dxf_utils import parse_dxf_complete, save_dxf_layout_complete
from file_object import FileObject
from layout_optimizer import (
    bin_packing_with_inventory,
    Carpet,
)

from excel_loader import (
    load_excel_file,
    parse_orders_from_excel,
    find_dxf_files_for_article,
)
from plot import plot_layout

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
logger.info(
    "Работа без ограничений на диапазон листов - максимальная плотность раскладки"
)

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


def deselect(orders_to_show, start_idx):
    for i in range(len(orders_to_show)):
        st.session_state[f"order_{start_idx + i}"] = False
    st.rerun()


os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Streamlit App
# Display logo at the very top
st.set_page_config(
    layout="wide",
    page_title="Wondercraft - Раскрой ковров",
)

# Add "Clear All" button at the top
col_logo, col_clear = st.columns([4, 1])

with col_logo:
    try:
        st.image("logo.png", width=600, use_container_width=False)
    except FileNotFoundError:
        st.title("Wondercraft - Раскрой ковров")

# Initialize clear counter for file uploaders
if "clear_counter" not in st.session_state:
    st.session_state.clear_counter = 0

with col_clear:
    st.write("")  # Add some spacing
    st.write("")  # Add some spacing
    if st.button(
        "🗑️ Очистить всё", help="Очистить все данные и начать заново", type="secondary"
    ):
        # Increment clear counter to reset all file uploaders
        if "clear_counter" not in st.session_state:
            st.session_state.clear_counter = 0
        st.session_state.clear_counter += 1

        # Clear all session state
        keys_to_clear = [
            "available_sheets",
            "selected_orders",
            "manual_files",
            "file_groups",
            "group_counter",
            "optimization_results",
            "manual_file_settings",
            "current_excel_hash",
        ]

        for key in keys_to_clear:
            if key in st.session_state:
                del st.session_state[key]

        # Clear all order selection states
        keys_to_remove = [
            key
            for key in st.session_state.keys()
            if key.startswith(("order_", "quantity_", "select_", "qty_", "excel_upload", "manual_dxf_"))
        ]
        for key in keys_to_remove:
            del st.session_state[key]

        st.success("✅ Все данные очищены!")
        st.rerun()

# Sheet Inventory Section
st.header("📋 Настройка листов")
st.write("Укажите какие листы у вас есть в наличии и их количество.")

# Initialize session state for sheets
if "available_sheets" not in st.session_state:
    st.session_state.available_sheets = []

# Update existing sheets to have color if missing (for backward compatibility)
for sheet in st.session_state.available_sheets:
    if "color" not in sheet:
        sheet["color"] = "серый"  # Default color for existing sheets

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
            max_value=5000,
            step=1,
            value=140,
            key="custom_width",
        )
        sheet_height = st.number_input(
            "Высота (см)",
            min_value=50,
            max_value=5000,
            step=1,
            value=200,
            key="custom_height",
        )
        selected_size = (sheet_width, sheet_height)
    else:
        selected_size = tuple(map(int, sheet_type_option.split("x")))

with col2:
    sheet_count = st.number_input(
        "Количество листов", min_value=1, max_value=1000, value=5, key="sheet_count"
    )
    # Color selection
    sheet_color = st.selectbox("Цвет листа", ["чёрный", "серый"], key="sheet_color")

    sheet_name = st.text_input(
        "Название типа листа (опционально)",
        value=f"Лист {selected_size[0]}x{selected_size[1]} {sheet_color}",
        key="sheet_name",
    )

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
    st.success(f"Добавлен тип листа: {new_sheet['name']} ({new_sheet['count']} шт.)")
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
        if st.button("🗑️ Удалить все листы", key="clear_sheets"):
            st.session_state.available_sheets = []
            st.rerun()

# Order Loading Section
st.header("📋 Загрузка заказов")

# Initialize session state for orders
if "selected_orders" not in st.session_state:
    st.session_state.selected_orders = []
if "manual_files" not in st.session_state:
    st.session_state.manual_files = []

st.subheader("1. Excel файл")
# Excel file upload with clear_counter in key to reset on clear
excel_file = st.file_uploader(
    "Загрузите файл заказов Excel", type=["xlsx", "xls"], key=f"excel_upload_{st.session_state.clear_counter}"
)

# Track current Excel file to detect changes
if "current_excel_hash" not in st.session_state:
    st.session_state.current_excel_hash = None

if excel_file is not None:
    try:
        with st.spinner("Загрузка Excel файла..."):
            # Read Excel file with caching - use file hash for cache key
            file_content = excel_file.read()
            file_hash = hash(file_content)

            # Check if this is a different Excel file
            if st.session_state.current_excel_hash != file_hash:
                # New file detected - clear all previous selections
                st.session_state.current_excel_hash = file_hash

                # Clear all order selection states
                keys_to_remove = [
                    key
                    for key in st.session_state.keys()
                    if key.startswith(("order_", "quantity_", "select_", "qty_"))
                ]
                for key in keys_to_remove:
                    del st.session_state[key]

                # Clear selected orders
                st.session_state.selected_orders = []

                logger.info("Новый Excel файл загружен, предыдущие выборы очищены")

            excel_data = load_excel_file(file_content)
            logger.info(f"Excel файл загружен. Листы: {list(excel_data.keys())}")

        all_orders = parse_orders_from_excel(excel_data)

        if all_orders:
            st.success(f"✅ Найдено {len(all_orders)} невыполненных заказов")
            logger.info(f"Найдено {len(all_orders)} невыполненных заказов в Excel")

            # Display orders for selection
            st.subheader("📝 Выберите заказы для раскроя")

            # Add dropdown filter options
            # Get unique values from all orders for dynamic filtering
            all_marketplaces = sorted(
                list(
                    set(
                        order.get("marketplace", "")
                        for order in all_orders
                        if order.get("marketplace", "")
                    )
                )
            )
            all_border_colors = sorted(
                list(
                    set(
                        str(order.get("border_color", ""))
                        for order in all_orders
                        if order.get("border_color", "")
                    )
                )
            )

            col_filter1, col_filter2 = st.columns([1, 1])
            with col_filter1:
                selected_marketplace = st.selectbox(
                    "🏪 Маркетплейс:",
                    options=["Все"] + all_marketplaces,
                    index=0,
                    key="filter_marketplace",
                )
            with col_filter2:
                selected_border_color = st.selectbox(
                    "🎨 Кант цвет:",
                    options=["Все"] + all_border_colors,
                    index=0,
                    key="filter_border_color",
                )

            # Filter orders based on dropdown selections
            filtered_orders = all_orders
            if selected_marketplace != "Все":
                filtered_orders = [
                    order
                    for order in filtered_orders
                    if order.get("marketplace", "") == selected_marketplace
                ]
            if selected_border_color != "Все":
                filtered_orders = [
                    order
                    for order in filtered_orders
                    if str(order.get("border_color", "")) == selected_border_color
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
                            "Маркетплейс": order.get("marketplace", ""),
                        }
                    )

                ###########################################33
                with st.container(height=400):
                    cols = st.columns([1, 2, 10, 6, 3, 3, 3])
                    with cols[1]:
                        st.write("**Количество**")
                    with cols[2]:
                        st.write("**Артикул**")
                    with cols[3]:
                        st.write("**Товар**")
                    with cols[4]:
                        st.write("**Изделие**")
                    with cols[5]:
                        st.write("**Кант цвет**")
                    with cols[6]:
                        st.write("**Маркетплейс**")

                    # Create columns for interactive controls
                    for i, order in enumerate(orders_to_show):
                        actual_idx = start_idx + i

                        cols = st.columns([1, 2, 10, 6, 3, 3, 3])

                        # Selection checkbox
                        with cols[0]:
                            is_selected = st.checkbox(
                                f"№{actual_idx + 1}",
                                value=st.session_state.get(
                                    f"order_{actual_idx}", False
                                ),
                                key=f"select_{actual_idx}",
                                label_visibility="collapsed",
                            )
                            st.session_state[f"order_{actual_idx}"] = is_selected

                        # Quantity number input
                        with cols[1]:
                            quantity = st.number_input(
                                f"Количество для заказа {actual_idx + 1}",
                                min_value=1,
                                max_value=1000,
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

                        with cols[6]:
                            st.write(order.get("marketplace", ""))
                ####################################################

                # Bulk controls
                col1, col2 = st.columns([1, 1])
                with col1:
                    if st.button("✅ Выбрать все", key="select_all_orders"):
                        for i in range(len(orders_to_show)):
                            st.session_state[f"order_{start_idx + i}"] = True
                        st.rerun()

                with col2:
                    if st.button("❌ Снять выбор", key="deselect_all_orders"):
                        deselect(orders_to_show, start_idx)

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
        else:
            st.warning("⚠️ Не найдено невыполненных заказов в указанных месяцах")

    except Exception as e:
        st.error(f"❌ Ошибка обработки Excel файла: {e}")
        logger.error(f"Ошибка при обработке Excel: {e}")

# Initialize auto_loaded_files
auto_loaded_files = []

# DXF files will be loaded on demand during optimization
# This section shows what will be processed when optimization starts
if st.session_state.selected_orders:
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


# Additional DXF files section (always available)
st.subheader("2. Загрузить вручную")

# Initialize session state for file groups
if "file_groups" not in st.session_state:
    st.session_state.file_groups = []
if "group_counter" not in st.session_state:
    st.session_state.group_counter = 1

# File uploader for new files - each selection creates a new group
# Use group_counter in key to reset uploader after each group creation
uploader_key = f"manual_dxf_{st.session_state.clear_counter}_{len(st.session_state.file_groups)}"
manual_files = st.file_uploader(
    "Выберите DXF файлы (будет создана новая группа). Каждая группа будет иметь свои настройки цвета и количества.",
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
            max_value=1000,
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
        if st.button("🗑️ Удалить все группы", key="clear_all_groups"):
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

        # Load files from orders
        progress_bar = st.progress(0)
        status_text = st.empty()

        total_orders = len(st.session_state.selected_orders)
        not_found_orders = []

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
                        file_obj = FileObject(file_content, display_name)
                        file_obj.color = order.get("color", "серый")
                        file_obj.order_id = order.get("order_id", "unknown")
                        auto_loaded_files.append(file_obj)
                        logger.debug(
                            f"Загружен файл {display_name} для заказа {file_obj.order_id}"
                        )
                    except Exception as e:
                        st.warning(f"⚠️ Ошибка загрузки {file_path}: {e}")
            else:
                not_found_orders.append(f"{product} (тип: {product_type})")

        # Show single warning for all not found orders
        if not_found_orders:
            st.warning(
                f"⚠️ Не найдены DXF файлы для следующих заказов:\n" +
                "\n".join(f"• {order}" for order in not_found_orders)
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
            status_text.text(
                f"Загрузка полигонов из файла {idx + 1}/{len(dxf_files)}: {display_name}"
            )

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
                # logger.info(f"ДОБАВЛЕН ПОЛИГОН: order_id={carpet.order_id}")
                # Store original DXF data using display_name as key
                original_dxf_data_map[display_name] = parsed_data

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
        # for order_id, count in order_counts.items():
        #    logger.info(f"  • Заказ {order_id}: {count} файлов")

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

        st.header("🔄 Раскладка ковров")
        try:
            # Actual processing with progress tracking
            # st.info("🔄 Запуск процесса раскладки...")
            optimization_progress = st.progress(5)
            optimization_status = st.empty()

            logger.info(
                f"Входные параметры: {len(carpets)} полигонов, {len(st.session_state.available_sheets)} типов листов"
            )

            # Progress callback function with more detailed updates
            def update_progress(percent, status_text):
                adjusted_percent = 5 + (percent * 0.95)  # Scale to 10%-100% range
                optimization_progress.progress(min(95, int(adjusted_percent)))
                optimization_status.text(f"🔄 {status_text}")

            placed_layouts, unplaced_polygons = bin_packing_with_inventory(
                carpets,
                st.session_state.available_sheets,
                verbose=False,
                progress_callback=update_progress,
            )

            logger.info(
                f"Результат bin_packing: {len(placed_layouts)} размещенных листов, {len(unplaced_polygons)} неразмещенных полигонов"
            )

            # Finalize
            optimization_progress.progress(100)
            optimization_status.text("✅ Раскладка завершена.")

            # Clear progress indicators after a moment
            import time

            time.sleep(1)
            optimization_progress.empty()
            optimization_status.empty()

        except ValueError as e:
            # Handle any other ValueError exceptions
            st.error(f"❌ Ошибка при раскладке: {str(e)}")
            st.stop()

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
            results_status.text(f"Создание файла {i + 1}/{total_layouts}")

            # Save and visualize layout with new naming format: length_width_number_color.dxf
            sheet_width = int(layout.sheet_size[0])
            sheet_height = int(layout.sheet_size[1])
            sheet_number = layout.sheet_number

            # Find sheet color from original sheet data
            sheet_color = "не указан"
            color_suffix = "unknown"

            # Try to get sheet color from layout first, then match by name
            sheet_color = layout.sheet_color
            for sheet in st.session_state.available_sheets:
                if sheet["name"] == layout.sheet_type:
                    sheet_color = sheet.get("color", "не указан")
                    break
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
                layout.placed_polygons,
                layout.sheet_size,
                output_file,
                original_dxf_data_map,
            )
            layout_plot = plot_layout(layout.placed_polygons, layout.sheet_size)

            # Store layout info in old format for compatibility
            shapes_count = len(layout.placed_polygons)
            logger.info(
                f"Лист #{layout.sheet_number}: создаем all_layouts запись с {shapes_count} размещенными полигонами"
            )

            # Определяем тип листа с проверкой наличия ключа
            sheet_type = layout.sheet_type
            all_layouts.append(
                {
                    "Sheet": layout.sheet_number,
                    "Sheet Type": sheet_type,
                    "Sheet Color": sheet_color,
                    "Sheet Size": f"{layout.sheet_size[0]}x{layout.sheet_size[1]} см",
                    "Output File": output_file,
                    "Plot": layout_plot,
                    "Shapes Placed": shapes_count,
                    "Material Usage (%)": f"{layout.usage_percent:.2f}",
                    "Placed Polygons": layout.placed_polygons,
                }
            )
            report_data.extend(
                [
                    (p.filename, layout.sheet_number, output_file)
                    for p in layout.placed_polygons
                ]
            )

        # Finalize results processing
        results_progress.progress(100)
        results_status.text("✅ Все файлы созданы.")

        # Update sheet inventory in session state
        for layout in placed_layouts:
            # Определяем тип листа с проверкой наличия ключа

            layout_sheet_type = layout.sheet_type
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
                len(layout.placed_polygons) for layout in placed_layouts
            )
            logger.info(
                f"DEBUG подсчет: raw_from_layouts={raw_count_from_layouts}, calculated_placed={actual_placed_count}, input={total_input_polygons}, unplaced={len(unplaced_polygons)}"
            )

            logger.info(
                f"UI подсчет: actual_placed={actual_placed_count}, total_input={total_input_polygons}, unplaced={len(unplaced_polygons)}"
            )
            logger.info(
                f"Подробности по листам: {[(layout.sheet_number, len(layout.placed_polygons)) for layout in placed_layouts]}"
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
                polygon = placed_tuple.polygon
                angle = placed_tuple.angle
                file_name = placed_tuple.filename
                color = placed_tuple.color

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

        # Group layouts into groups of 4 for four-column display
        for i in range(0, len(all_layouts), 4):
            sheet_col1, sheet_col2, sheet_col3, sheet_col4 = st.columns(4)

            # Display sheets in 4 columns
            columns = [sheet_col1, sheet_col2, sheet_col3, sheet_col4]

            for col_idx in range(4):
                layout_idx = i + col_idx
                if layout_idx < len(all_layouts):
                    with columns[col_idx]:
                        layout = all_layouts[layout_idx]
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

                        st.image(
                            layout["Plot"],
                            caption=f"Раскрой листа №{layout['Sheet']} ({layout['Sheet Type']})",
                            use_container_width=True,
                        )

                        st.write(f"**Тип листа:** {layout['Sheet Type']}")
                        st.write(
                            f"**Цвет листа:** {color_emoji} {layout['Sheet Color']}"
                        )
                        st.write(f"**Размер листа:** {layout['Sheet Size']}")
                        st.write(f"**Размещено объектов:** {layout['Shapes Placed']}")
                        st.write(
                            f"**Расход материала:** {layout['Material Usage (%)']}%"
                        )
                        with open(layout["Output File"], "rb") as f:
                            st.download_button(
                                label="📥 Скачать DXF",
                                data=f,
                                file_name=os.path.basename(layout["Output File"]),
                                mime="application/dxf",
                                key=f"download_{layout['Sheet']}_{col_idx}",
                            )

            st.divider()  # Add visual separator between sheet rows
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
                (carpet.filename, f"{carpet.polygon.area / 100:.2f}", carpet.color)
            )

        unplaced_df = pd.DataFrame(
            unplaced_data, columns=["Файл", "Площадь (см²)", "Цвет"]
        )
        st.dataframe(unplaced_df, use_container_width=True)

    # Save report
    if all_layouts:
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

        with open(zip_path, "rb") as f:
            st.download_button(
                label="📦 Скачать все файлы (ZIP)",
                data=f,
                file_name=zip_filename,
                mime="application/zip",
            )
