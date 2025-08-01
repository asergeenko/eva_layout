import streamlit as st
import pandas as pd
import numpy as np
import os
import uuid
from datetime import datetime
from io import BytesIO
import functools
import zipfile
import logging

# Константы
MAX_SHEETS_PER_ORDER = 5  # Максимальное количество листов на один заказ (номер заказа из колонки O)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('eva_layout_debug.log', mode='w', encoding='utf-8'),
        logging.StreamHandler()  # Также выводить в консоль
    ]
)
logger = logging.getLogger(__name__)

logger.info("=== НАЧАЛО СЕССИИ EVA LAYOUT ===")
logger.info(f"MAX_SHEETS_PER_ORDER = {MAX_SHEETS_PER_ORDER}")

# Clear any cached imports (for Streamlit Cloud)
import sys
if 'layout_optimizer' in sys.modules:
    del sys.modules['layout_optimizer']

# Force cache clear
import importlib
try:
    import layout_optimizer
    importlib.reload(layout_optimizer)
except:
    pass

try:
    from layout_optimizer import (
        parse_dxf_complete, 
        save_dxf_layout_complete,
        parse_dxf, 
        bin_packing, 
        bin_packing_with_inventory, 
        save_dxf_layout, 
        plot_layout, 
        plot_input_polygons, 
        scale_polygons_to_fit
    )
    st.success("✅ Все функции успешно импортированы")
except ImportError as e:
    # Debug information
    st.error(f"Ошибка прямого импорта: {e}")
    
    # Fallback import with debug
    try:
        import layout_optimizer as lo
        st.info(f"Модуль layout_optimizer загружен. Версия: {getattr(lo, '__version__', 'неизвестна')}")
        
        # Show available functions
        available_funcs = [attr for attr in dir(lo) if not attr.startswith('_') and callable(getattr(lo, attr))]
        st.info(f"Доступные функции: {', '.join(available_funcs)}")
        
        # Check specific function
        if hasattr(lo, 'bin_packing_with_inventory'):
            st.success("✅ bin_packing_with_inventory найдена!")
            bin_packing_with_inventory = lo.bin_packing_with_inventory
        else:
            st.error("❌ bin_packing_with_inventory НЕ найдена!")
            
            # Try alternative approach - define the function inline as a workaround
            st.warning("🔧 Применяем обходное решение...")
            
            def bin_packing_with_inventory_fallback(polygons, available_sheets, verbose=True, max_sheets_per_order=None):
                """Fallback implementation if import fails."""
                if verbose:
                    st.info("Используется резервная реализация bin_packing_with_inventory")
                
                placed_layouts = []
                unplaced = polygons.copy()
                sheet_counter = 0
                
                for sheet in available_sheets:
                    if not unplaced:
                        break
                    
                    available_count = sheet['count'] - sheet['used']
                    for _ in range(available_count):
                        if not unplaced:
                            break
                            
                        sheet_counter += 1
                        sheet_size = (sheet['width'], sheet['height'])
                        
                        placed, remaining = lo.bin_packing(unplaced, sheet_size, verbose=verbose)
                        
                        if placed:
                            usage_percent = lo.calculate_usage_percent(placed, sheet_size)
                            placed_layouts.append({
                                'sheet_number': sheet_counter,
                                'sheet_type': sheet['name'],
                                'sheet_size': sheet_size,
                                'placed_polygons': placed,
                                'usage_percent': usage_percent
                            })
                            unplaced = remaining
                        else:
                            break
                
                return placed_layouts, unplaced
                
            bin_packing_with_inventory = bin_packing_with_inventory_fallback
            st.success("✅ Резервная реализация bin_packing_with_inventory создана!")
            
        # Assign other functions
        parse_dxf_complete = lo.parse_dxf_complete
        save_dxf_layout_complete = lo.save_dxf_layout_complete
        parse_dxf = lo.parse_dxf
        bin_packing = lo.bin_packing
        save_dxf_layout = lo.save_dxf_layout
        plot_layout = lo.plot_layout
        plot_input_polygons = lo.plot_input_polygons
        scale_polygons_to_fit = lo.scale_polygons_to_fit
        
    except Exception as e2:
        st.error(f"Критическая ошибка импорта: {e2}")
        st.error("Убедитесь, что файл layout_optimizer.py присутствует и доступен")
        st.stop()

# Configuration
DEFAULT_SHEET_TYPES = [
    (140, 200), (142, 200), (144, 200), (146, 200), (148, 200),
    (140, 195), (142, 195), (144, 195), (146, 195), (148, 195),
    (100, 100), (150, 150), (200, 300)
]
OUTPUT_FOLDER = "output_layouts"
os.makedirs(OUTPUT_FOLDER, exist_ok=True)


# Streamlit App
st.title("Оптимизатор раскроя EVA ковриков")
st.write("Загрузите DXF файлы и укажите размер листа для оптимального размещения ковриков.")

# Sheet Inventory Section
st.header("📋 Настройка доступных листов")
st.write("Укажите какие листы у вас есть в наличии и их количество.")

# Initialize session state for sheets
if 'available_sheets' not in st.session_state:
    st.session_state.available_sheets = []

# Update existing sheets to have color if missing (for backward compatibility)
for sheet in st.session_state.available_sheets:
    if 'color' not in sheet:
        sheet['color'] = 'серый'  # Default color for existing sheets

# Add new sheet type
st.subheader("Добавить тип листа")
col1, col2, col3 = st.columns([2, 2, 1])

with col1:
    sheet_type_option = st.selectbox(
        "Выберите размер листа (см)", 
        ["Произвольный"] + [f"{w}x{h}" for w, h in DEFAULT_SHEET_TYPES],
        key="sheet_type_select"
    )
    
    if sheet_type_option == "Произвольный":
        sheet_width = st.number_input("Ширина (см)", min_value=50.0, max_value=300.0, value=140.0, key="custom_width")
        sheet_height = st.number_input("Высота (см)", min_value=50.0, max_value=300.0, value=200.0, key="custom_height")
        selected_size = (sheet_width, sheet_height)
    else:
        selected_size = tuple(map(float, sheet_type_option.split("x")))
        
    # Color selection
    sheet_color = st.selectbox(
        "Цвет листа", 
        ["чёрный", "серый"],
        key="sheet_color"
    )
        
with col2:
    sheet_count = st.number_input("Количество листов", min_value=1, max_value=100, value=5, key="sheet_count")
    sheet_name = st.text_input("Название типа листа (опционально)", 
                              value=f"Лист {selected_size[0]}x{selected_size[1]} {sheet_color}", 
                              key="sheet_name")

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
            "used": 0
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
        color = sheet.get('color', 'не указан')
        color_emoji = "⚫" if color == "чёрный" else "⚪" if color == "серый" else "🔘"
        color_display = f"{color_emoji} {color}"
        
        sheets_data.append({
            "№": i + 1,
            "Название": sheet['name'],
            "Размер (см)": f"{sheet['width']}x{sheet['height']}",
            "Цвет": color_display,
            "Доступно": f"{sheet['count'] - sheet['used']}/{sheet['count']}",
            "Использовано": sheet['used']
        })
        total_sheets += sheet['count']
    
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
if 'selected_orders' not in st.session_state:
    st.session_state.selected_orders = []
if 'manual_files' not in st.session_state:
    st.session_state.manual_files = []

# Excel file upload
excel_file = st.file_uploader("Загрузите файл заказов Excel", type=["xlsx", "xls"], key="excel_upload")

@st.cache_data(ttl=600)  # Cache for 10 minutes
def load_excel_file(file_content):
    """Load and cache Excel file processing"""
    excel_data = pd.read_excel(BytesIO(file_content), sheet_name=None, header=None, 
                              date_format=None, parse_dates=False)
    return excel_data

if excel_file is not None:
    try:
        with st.spinner("Загрузка Excel файла..."):
            # Read Excel file with caching
            file_content = excel_file.read()
            excel_data = load_excel_file(file_content)
            logger.info(f"Excel файл загружен. Листы: {list(excel_data.keys())}")
        
        # Get current month name and previous month
        from datetime import datetime
        current_date = datetime.now()
        current_month = current_date.strftime("%B %Y").upper()
    
        # Russian month names mapping
        month_mapping = {
            "JANUARY": "ЯНВАРЬ", "FEBRUARY": "ФЕВРАЛЬ", "MARCH": "МАРТ", 
            "APRIL": "АПРЕЛЬ", "MAY": "МАЙ", "JUNE": "ИЮНЬ",
            "JULY": "ИЮЛЬ", "AUGUST": "АВГУСТ", "SEPTEMBER": "СЕНТЯБРЬ",
            "OCTOBER": "ОКТЯБРЬ", "NOVEMBER": "НОЯБРЬ", "DECEMBER": "ДЕКАБРЬ"
        }
        
        current_month_ru = month_mapping.get(current_date.strftime("%B").upper(), "ИЮЛЬ") + " " + str(current_date.year)
        
        # Get previous month (handle day overflow correctly)
        if current_date.month == 1:
            prev_month_ru = "ДЕКАБРЬ " + str(current_date.year - 1)
        else:
            # Use first day of month to avoid day overflow issues
            first_of_current_month = current_date.replace(day=1)
            prev_date = first_of_current_month.replace(month=first_of_current_month.month - 1)
            prev_month_ru = month_mapping.get(prev_date.strftime("%B").upper(), "ИЮНЬ") + " " + str(prev_date.year)
        
        target_sheets = [current_month_ru, prev_month_ru]
        
        st.info(f"🗓️ Ищем листы для: {', '.join(target_sheets)}")
        
        # Process target sheets
        all_orders = []
        for sheet_name in target_sheets:
            if sheet_name in excel_data:
                df = excel_data[sheet_name]
                
                # Skip first 2 rows (headers), start from row 2 (index 2)
                if df.shape[0] > 2:
                    data_rows = df.iloc[2:].copy()
                    
                    # Check for empty "Сделано" column (index 2)
                    if df.shape[1] > 3:  # Make sure we have enough columns
                        pending_orders = data_rows[data_rows.iloc[:, 2].isna() | (data_rows.iloc[:, 2] == '')]
                        
                        for idx, row in pending_orders.iterrows():
                            if pd.notna(row.iloc[3]):  # Check if Артикул (column D) is not empty
                                # Get color from column I (index 8)
                                color = str(row.iloc[8]).lower().strip() if pd.notna(row.iloc[8]) and df.shape[1] > 8 else ''
                                # Normalize color values
                                if 'черн' in color or 'black' in color:
                                    color = 'чёрный'
                                elif 'сер' in color or 'gray' in color or 'grey' in color:
                                    color = 'серый'
                                else:
                                    color = 'серый'  # Default color if not specified
                                
                                order = {
                                    'sheet': sheet_name,
                                    'row_index': idx,
                                    'date': str(row.iloc[0]) if pd.notna(row.iloc[0]) else '',
                                    'article': str(row.iloc[3]),
                                    'product': str(row.iloc[4]) if pd.notna(row.iloc[4]) else '',
                                    'client': str(row.iloc[5]) if pd.notna(row.iloc[5]) else '' if df.shape[1] > 5 else '',
                                    'order_id': str(row.iloc[14]) if pd.notna(row.iloc[14]) and df.shape[1] > 13 else '',
                                    'color': color
                                }
                                all_orders.append(order)
        
        if all_orders:
            st.success(f"✅ Найдено {len(all_orders)} невыполненных заказов")
            logger.info(f"Найдено {len(all_orders)} невыполненных заказов в Excel")
            
            # Display orders for selection
            st.subheader("📝 Выберите заказы для раскроя")
            
            # Add search/filter options
            col_filter1, col_filter2 = st.columns([1, 1])
            with col_filter1:
                search_article = st.text_input("🔍 Поиск по артикулу:", placeholder="Введите часть артикула", key="search_article")
            with col_filter2:
                search_product = st.text_input("🔍 Поиск по товару:", placeholder="Введите часть названия", key="search_product")
            
            # Filter orders based on search
            filtered_orders = all_orders
            if search_article:
                filtered_orders = [order for order in filtered_orders if search_article.lower() in order['article'].lower()]
            if search_product:
                filtered_orders = [order for order in filtered_orders if search_product.lower() in order['product'].lower()]
            
            if filtered_orders != all_orders:
                st.info(f"🔍 Найдено {len(filtered_orders)} заказов из {len(all_orders)} (применены фильтры)")
            
            # Update all_orders with filtered results for display
            display_orders = filtered_orders
        
            # Create selection interface
            selected_indices = []
            
            # Show orders in batches of 10 for better UX
            orders_per_page = 10
            total_pages = (len(display_orders) + orders_per_page - 1) // orders_per_page
            
            if total_pages > 1:
                page = st.selectbox("Страница", range(1, total_pages + 1), key="orders_page") - 1
                start_idx = page * orders_per_page
                end_idx = min(start_idx + orders_per_page, len(display_orders))
                orders_to_show = display_orders[start_idx:end_idx]
            else:
                orders_to_show = display_orders
                start_idx = 0
            
            # Create table data for orders
            table_data = []
            for i, order in enumerate(orders_to_show):
                actual_idx = start_idx + i
                # Get checkbox state
                is_selected = st.session_state.get(f"order_{actual_idx}", False)
                
                # Add color emoji for display
                color = order.get('color', 'серый')
                color_emoji = "⚫" if color == "чёрный" else "⚪" if color == "серый" else "🔘"
                color_display = f"{color_emoji} {color}"
                
                table_data.append({
                    "Выбрать": is_selected,
                    "Артикул": order['article'],
                    "Товар": order['product'][:50] + "..." if len(order['product']) > 50 else order['product'],
                    "Цвет": color_display,
                    "Клиент": order.get('client', '')[:25] + "..." if len(order.get('client', '')) > 25 else order.get('client', ''),
                    "Дата": order.get('date', '')[:10],  # Show only date part
                    "Месяц": order['sheet'],
                    "№ заказа": order.get('order_id', '')
                })
            
            # Display orders table with selection
            if table_data:
                orders_df = pd.DataFrame(table_data)
                
                # Use data_editor for selection
                edited_df = st.data_editor(
                    orders_df,
                    column_config={
                        "Выбрать": st.column_config.CheckboxColumn(
                            "Выбрать",
                            help="Отметьте заказы для раскроя",
                            default=False,
                        ),
                        "Артикул": st.column_config.TextColumn(
                            "Артикул",
                            help="Код артикула для поиска DXF файлов",
                            width="medium"
                        ),
                        "Товар": st.column_config.TextColumn(
                            "Товар",
                            help="Название товара",
                            width="large"
                        ),
                        "Цвет": st.column_config.TextColumn(
                            "Цвет",
                            help="Цвет листа для заказа",
                            width="small"
                        ),
                        "Клиент": st.column_config.TextColumn(
                            "Клиент",
                            help="Название клиента",
                            width="medium"
                        ),
                        "Дата": st.column_config.TextColumn(
                            "Дата",
                            help="Дата заказа",
                            width="small"
                        ),
                        "Месяц": st.column_config.TextColumn(
                            "Месяц",
                            help="Месяц из Excel листа",
                            width="small"
                        ),
                        "№ заказа": st.column_config.TextColumn(
                            "№ заказа",
                            help="Номер заказа",
                            width="small"
                        )
                    },
                    disabled=["Артикул", "Товар", "Цвет", "Клиент", "Дата", "Месяц", "№ заказа"],
                    hide_index=True,
                    use_container_width=True,
                    key=f"orders_table_page_{start_idx}"
                )
                
                # Update session state based on table selections
                for i, row in edited_df.iterrows():
                    actual_idx = start_idx + i
                    st.session_state[f"order_{actual_idx}"] = row["Выбрать"]
            
            # Bulk selection controls
            col1, col2, col3 = st.columns([1, 1, 2])
            with col1:
                if st.button("✅ Выбрать все", key=f"select_all_{start_idx}"):
                    for i in range(len(orders_to_show)):
                        st.session_state[f"order_{start_idx + i}"] = True
                    # Mark that we just performed bulk selection to avoid double processing
                    st.session_state[f"bulk_selected_{start_idx}"] = True
                    st.rerun()
            with col2:
                if st.button("❌ Снять все", key=f"deselect_all_{start_idx}"):
                    for i in range(len(orders_to_show)):
                        st.session_state[f"order_{start_idx + i}"] = False
                    st.rerun()
            
            # Collect all selected orders from all pages
            all_selected_orders = []
            for i in range(len(all_orders)):
                if st.session_state.get(f"order_{i}", False):
                    all_selected_orders.append(all_orders[i])
            
            if all_selected_orders:
                st.success(f"🎯 Выбрано заказов: {len(all_selected_orders)}")
                
                # Show selected orders summary in table format (only for reasonable number of orders)
                if len(all_selected_orders) <= 20:
                    with st.expander("📋 Выбранные заказы", expanded=False):
                        selected_summary = []
                        for order in all_selected_orders:
                            selected_summary.append({
                                "Артикул": order['article'],
                                "Товар": order['product'][:40] + "..." if len(order['product']) > 40 else order['product'],
                                "Месяц": order['sheet']
                                })
                        
                        selected_df = pd.DataFrame(selected_summary)
                        st.dataframe(selected_df, use_container_width=True, hide_index=True)
                else:
                    st.info(f"📋 Выбрано {len(all_selected_orders)} заказов (список слишком большой для отображения)")
                    
                # Store selected orders in session state
                st.session_state.selected_orders = all_selected_orders
                logger.info(f"Выбрано {len(all_selected_orders)} заказов для обработки")
                # Log only first few orders to avoid slowdown
                if len(all_selected_orders) <= 5:
                    for order in all_selected_orders:
                        logger.info(f"  Заказ {order.get('order_id', 'N/A')}: {order.get('article', 'N/A')}")
                else:
                    # Log only first 3 and last 2 for large lists
                    for order in all_selected_orders[:3]:
                        logger.info(f"  Заказ {order.get('order_id', 'N/A')}: {order.get('article', 'N/A')}")
                    logger.info(f"  ... (пропущено {len(all_selected_orders) - 5} заказов) ...")
                    for order in all_selected_orders[-2:]:
                        logger.info(f"  Заказ {order.get('order_id', 'N/A')}: {order.get('article', 'N/A')}")
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
        st.error("• Убедитесь, что в датах нет некорректных значений (например, 30 февраля)")

# Initialize auto_loaded_files
auto_loaded_files = []

# DXF files will be loaded on demand during optimization
# This section shows what will be processed when optimization starts
if st.session_state.selected_orders:
    st.subheader("📋 Готовые к обработке заказы")
    
    st.success(f"✅ Выбрано {len(st.session_state.selected_orders)} заказов")
    st.info("💡 DXF файлы будут загружены при нажатии кнопки 'Оптимизировать раскрой' для ускорения интерфейса.")
    
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

    @st.cache_data(ttl=300)  # Cache for 5 minutes
    def find_dxf_files_for_article(article, product_name=''):
        """Find DXF files for a given article by searching in the dxf_samples directory structure."""
        import re
        found_files = []
        
        logger.info(f"Поиск DXF файлов для артикула: '{article}', товар: '{product_name}'")
        
        # Strategy 1: Search by product name (e.g., "AUDI A6 (C7) 4")
        if product_name and not found_files:
            # Extract brand and model from product name
            product_upper = product_name.upper()
            
            # Handle common brand name mappings
            brand_mapping = {
                'AUDI': 'AUDI',
                'BMW': 'BMW',
                'MERCEDES': 'MERCEDES',
                'VOLKSWAGEN': 'VOLKSWAGEN',
                'FORD': 'FORD',
                'TOYOTA': 'TOYOTA',
                'NISSAN': 'NISSAN',
                'HYUNDAI': 'HYUNDAI',
                'KIA': 'KIA',
                'CHERY': 'CHERY',
                'CHANGAN': 'CHANGAN'
            }
            
            # Find brand in product name
            detected_brand = None
            for brand_key, brand_folder in brand_mapping.items():
                if brand_key in product_upper:
                    detected_brand = brand_folder
                    break
            
            if detected_brand:
                brand_path = f"dxf_samples/{detected_brand}"
                logger.debug(f"Обнаружен бренд: {detected_brand}, путь: {brand_path}")
                if os.path.exists(brand_path):
                    # Create search keywords from product name
                    product_keywords = []
                    
                    # Clean product name and extract model parts
                    model_part = product_upper.replace(detected_brand, '').strip()
                    
                    # Add full product name as keyword
                    product_keywords.append(product_name.lower())
                    
                    # Handle parentheses and extract parts
                    if '(' in model_part and ')' in model_part:
                        parentheses_content = re.findall(r'\((.*?)\)', model_part)
                        base_model = re.sub(r'\s*\([^)]*\)\s*', ' ', model_part).strip()
                        
                        product_keywords.extend([
                            base_model.lower(),
                            model_part.replace('(', '').replace(')', '').lower(),
                        ])
                        
                        for content in parentheses_content:
                            product_keywords.extend([
                                content.lower(),
                                f"{base_model} {content}".lower(),
                            ])
                    
                    # Extract individual parts
                    model_parts = re.sub(r'[^\w\s]', ' ', model_part).split()
                    product_keywords.extend([part.lower() for part in model_parts if len(part) > 1])
                    
                    # Remove duplicates
                    product_keywords = list(set([k.strip() for k in product_keywords if k.strip()]))
                    
                    # Search through brand folders
                    for model_folder in os.listdir(brand_path):
                        model_folder_path = os.path.join(brand_path, model_folder)
                        if os.path.isdir(model_folder_path):
                            folder_name_lower = model_folder.lower()
                            
                            # Calculate match score with Cyrillic/Latin normalization
                            match_score = 0
                            
                            # Normalize folder name for better matching (handle Cyrillic/Latin)
                            normalized_folder = folder_name_lower
                            # Replace common Cyrillic letters with Latin equivalents
                            cyrillic_to_latin = {
                                'а': 'a', 'А': 'A',
                                'с': 'c', 'С': 'C',
                                'е': 'e', 'Е': 'E',
                                'о': 'o', 'О': 'O',
                                'р': 'p', 'Р': 'P',
                                'х': 'x', 'Х': 'X'
                            }
                            for cyrillic, latin in cyrillic_to_latin.items():
                                normalized_folder = normalized_folder.replace(cyrillic, latin)
                            
                            for keyword in product_keywords:
                                if keyword and len(keyword) > 2:
                                    # Direct match in normalized folder name
                                    if keyword in normalized_folder:
                                        match_score += len(keyword) * 2
                                    # Direct match in original folder name
                                    elif keyword in folder_name_lower:
                                        match_score += len(keyword) * 2
                                    else:
                                        # Check partial matches in normalized folder
                                        keyword_parts = keyword.split()
                                        matched_parts = sum(1 for part in keyword_parts 
                                                          if part in normalized_folder or part in folder_name_lower)
                                        if matched_parts > 0:
                                            match_score += matched_parts * 3
                            
                            # If we have a good match, look for DXF files
                            if match_score >= 6:  # Threshold for product name matching
                                dxf_folder = os.path.join(model_folder_path, "DXF")
                                if os.path.exists(dxf_folder):
                                    dxf_files_found = [f for f in os.listdir(dxf_folder) if f.lower().endswith('.dxf')]
                                    for dxf_file in dxf_files_found:
                                        found_files.append(os.path.join(dxf_folder, dxf_file))
                                    if found_files:
                                        logger.debug(f"Найдены DXF файлы в папке {dxf_folder}: {len(dxf_files_found)} файлов")
                                        break
                                else:
                                    # Check for DXF files directly in model folder
                                    dxf_files_found = [f for f in os.listdir(model_folder_path) if f.lower().endswith('.dxf')]
                                    for dxf_file in dxf_files_found:
                                        found_files.append(os.path.join(model_folder_path, dxf_file))
                                    if found_files:
                                        break
        
        # Strategy 2: Direct path mapping (if article matches folder structure)
        if not found_files:
            direct_path = f"dxf_samples/{article}"
            if os.path.exists(direct_path):
                dxf_files = [f for f in os.listdir(direct_path) if f.lower().endswith('.dxf')]
                for dxf_file in dxf_files:
                    found_files.append(os.path.join(direct_path, dxf_file))
        
        # Strategy 2: Parse article and search in brand folders
        if not found_files and '+' in article:
            parts = article.split('+')
            if len(parts) >= 3:
                # Extract brand and model (e.g., EVA_BORT+Chery+Tiggo 4 -> Chery, Tiggo 4)
                brand = parts[1].strip()
                model_info = parts[2].strip() if len(parts) > 2 else ""
                
                # Create search variants for the brand
                brand_variants = [
                    brand.upper(),
                    brand.capitalize(),
                    brand.lower()
                ]
                
                # Find matching brand folder
                for brand_variant in brand_variants:
                    brand_path = f"dxf_samples/{brand_variant}"
                    if os.path.exists(brand_path):
                        # Look for model folders that might match
                        for model_folder in os.listdir(brand_path):
                            model_folder_path = os.path.join(brand_path, model_folder)
                            if os.path.isdir(model_folder_path):
                                # Create search keywords from model info
                                search_keywords = []
                                
                                # Clean model info and create variants
                                if model_info:
                                    # Handle specific transformations
                                    model_variants = [model_info]
                                    
                                    # Handle parentheses (e.g., "A6 (C7) 4" -> "A6", "A6 C7", "A6 4", "A6 C7 4")
                                    if '(' in model_info and ')' in model_info:
                                        # Extract parts from parentheses
                                        parentheses_content = re.findall(r'\((.*?)\)', model_info)
                                        base_model = re.sub(r'\s*\([^)]*\)\s*', ' ', model_info).strip()
                                        
                                        # Create variants with and without parentheses content
                                        model_variants.extend([
                                            base_model,  # "A6 4"
                                            model_info.replace('(', '').replace(')', ''),  # "A6 C7 4"
                                        ])
                                        
                                        # Add variants with parentheses content integrated
                                        for content in parentheses_content:
                                            model_variants.extend([
                                                f"{base_model} {content}",  # "A6 4 C7"
                                                f"{content} {base_model}",  # "C7 A6 4"
                                                content,  # "C7"
                                            ])
                                    
                                    # Handle "CX35PLUS" -> "CS35", "CS35 PLUS" 
                                    if 'CX35PLUS' in model_info:
                                        model_variants.append(model_info.replace('CX35PLUS', 'CS35'))
                                        model_variants.append(model_info.replace('CX35PLUS', 'CS35 PLUS'))
                                    
                                    # Handle "PLUS" variations
                                    if 'PLUS' in model_info:
                                        model_variants.append(model_info.replace('PLUS', ' PLUS'))
                                        model_variants.append(model_info.replace('PLUS', ''))
                                    
                                    # Handle "PRO" variations
                                    if 'PRO' in model_info:
                                        model_variants.append(model_info.replace('PRO', ' PRO'))
                                        model_variants.append(model_info.replace('PRO', ''))
                                    
                                    # Extract individual model parts (e.g., "A6 (C7) 4" -> ["A6", "C7", "4"])
                                    model_parts = re.sub(r'[^\w\s]', ' ', model_info).split()
                                    model_variants.extend(model_parts)
                                    
                                    # Create combinations of model parts
                                    if len(model_parts) >= 2:
                                        for i in range(len(model_parts)):
                                            for j in range(i+1, len(model_parts)+1):
                                                combination = ' '.join(model_parts[i:j])
                                                if len(combination.strip()) > 1:
                                                    model_variants.append(combination)
                                    
                                    # Create search keywords from all variants
                                    for variant in model_variants:
                                        search_keywords.extend([
                                            variant.lower().strip(),
                                            variant.replace(' ', '').lower(),
                                            variant[:10].lower().strip()  # First 10 chars
                                        ])
                                    
                                    # Remove duplicates and empty strings
                                    search_keywords = list(set([k for k in search_keywords if k.strip()]))
                                
                                # Check if this model folder matches our search keywords
                                folder_name_lower = model_folder.lower()
                                match_found = False
                                match_score = 0
                                
                                # Calculate match score for better ranking
                                for keyword in search_keywords:
                                    if keyword and len(keyword) > 1:  # Check even short keywords
                                        keyword_parts = keyword.split()
                                        current_score = 0
                                        
                                        if len(keyword_parts) >= 2:
                                            # Multi-word keyword like "a6 c7" or "a6 4"
                                            matched_parts = sum(1 for part in keyword_parts if part in folder_name_lower)
                                            if matched_parts == len(keyword_parts):
                                                current_score = 10 + len(keyword_parts)  # High score for complete matches
                                                match_found = True
                                            elif matched_parts > 0:
                                                current_score = matched_parts * 2  # Partial match score
                                        else:
                                            # Single word keyword
                                            if keyword in folder_name_lower:
                                                # Exact substring match
                                                current_score = 8 + len(keyword)
                                                match_found = True
                                            elif len(keyword) >= 3:
                                                # Check for partial matches in folder name parts
                                                folder_parts = re.split(r'[\s\-_]', folder_name_lower)
                                                for folder_part in folder_parts:
                                                    if keyword in folder_part or folder_part in keyword:
                                                        current_score = max(current_score, 3)
                                                        match_found = True
                                        
                                        match_score = max(match_score, current_score)
                                
                                # Only proceed if we have a reasonable match
                                if match_found and match_score >= 3:
                                    # Look for DXF folder first
                                    dxf_folder = os.path.join(model_folder_path, "DXF")
                                    if os.path.exists(dxf_folder):
                                        dxf_files = [f for f in os.listdir(dxf_folder) if f.lower().endswith('.dxf')]
                                        for dxf_file in dxf_files:
                                            found_files.append(os.path.join(dxf_folder, dxf_file))
                                        if found_files:
                                            break
                                    else:
                                        # Look for DXF files directly in model folder
                                        dxf_files = [f for f in os.listdir(model_folder_path) if f.lower().endswith('.dxf')]
                                        for dxf_file in dxf_files:
                                            found_files.append(os.path.join(model_folder_path, dxf_file))
                                        if found_files:
                                            break
                        
                        if found_files:
                            break
        
        logger.info(f"Результат поиска для '{article}': найдено {len(found_files)} файлов")
        if found_files:
            logger.debug(f"Найденные файлы: {[os.path.basename(f) for f in found_files]}")
        return found_files

    # Show selected orders without file system search
    st.info(f"📊 Готово к обработке: **{len(st.session_state.selected_orders)}** заказов")
    
    # Show selected orders in a compact format
    with st.expander("📋 Список выбранных заказов", expanded=False):
        for i, order in enumerate(st.session_state.selected_orders, 1):
            st.write(f"{i}. **{order['product']}** (заказ: {order.get('order_id', 'N/A')})")
    
    st.success("✅ DXF файлы будут найдены и загружены при запуске оптимизации")

# Additional DXF files section (shown when orders are selected)
if st.session_state.selected_orders:
    st.subheader("📎 Дополнительные DXF файлы (опционально)")
    manual_files = st.file_uploader("Добавьте дополнительные DXF файлы при необходимости", type=["dxf"], accept_multiple_files=True, key="manual_dxf")
    
    # Store manual files in session state for later processing
    if manual_files:
        st.write("**Выберите цвет для дополнительных файлов:**")
        manual_color = st.selectbox(
            "Цвет листа для дополнительных файлов:",
            options=["серый", "чёрный"],
            index=0,
            key="manual_files_color",
            help="Выберите цвет листа, на который должны быть размещены дополнительные файлы"
        )
        # Store manual files and color in session state
        st.session_state.manual_files = manual_files
        st.session_state.manual_color = manual_color
        st.success(f"✅ Добавлено {len(manual_files)} дополнительных файлов")
    else:
        st.session_state.manual_files = []
else:
    # No orders selected or no files found - show message  
    if st.session_state.selected_orders:
        st.warning("⚠️ Для выбранных заказов не найдены DXF файлы. Проверьте наличие файлов в папке dxf_samples.")
    else:
        st.info("💡 Выберите заказы из Excel таблицы выше для автоматической загрузки DXF файлов.")

if st.button("🚀 Оптимизировать раскрой"):
    logger.info("=== НАЧАЛО ОПТИМИЗАЦИИ РАСКРОЯ ===")
    if not st.session_state.available_sheets:
        logger.error("Нет доступных листов для оптимизации")
        st.error("⚠️ Пожалуйста, добавьте хотя бы один тип листа в наличии.")
    elif not st.session_state.selected_orders:
        logger.error("Нет выбранных заказов для оптимизации")
        st.error("⚠️ Пожалуйста, выберите заказы из Excel таблицы.")
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
            status_text.text(f"Загружаем файлы для заказа {i + 1}/{total_orders}: {order['product'][:50]}...")
            
            article = order['article']
            product = order['product']
            found_dxf_files = find_dxf_files_for_article(article, product)
            
            if found_dxf_files:
                for file_path in found_dxf_files:
                    try:
                        with open(file_path, 'rb') as f:
                            file_content = f.read()
                        
                        display_name = f"{product}_{os.path.basename(file_path)}"
                        file_obj = FileObj(file_content, display_name)
                        file_obj.color = order.get('color', 'серый')
                        file_obj.order_id = order.get('order_id', 'unknown')
                        auto_loaded_files.append(file_obj)
                        logger.debug(f"Загружен файл {display_name} для заказа {file_obj.order_id}")
                    except Exception as e:
                        st.warning(f"⚠️ Ошибка загрузки {file_path}: {e}")
            else:
                st.warning(f"⚠️ Не найдены DXF файлы для заказа: {product}")
        
        # Load manual files if any
        if hasattr(st.session_state, 'manual_files') and st.session_state.manual_files:
            for file in st.session_state.manual_files:
                file.color = getattr(st.session_state, 'manual_color', 'серый')
                file.order_id = 'additional'
                manual_files_with_color.append(file)
        
        # Combine all files
        dxf_files = auto_loaded_files + manual_files_with_color
        
        progress_bar.empty()
        status_text.text(f"✅ Загружено {len(dxf_files)} файлов ({len(auto_loaded_files)} из заказов, {len(manual_files_with_color)} дополнительных)")
        
        logger.info(f"Начинаем оптимизацию с {len(dxf_files)} DXF файлами и {len(st.session_state.available_sheets)} типами листов")
        # Parse DXF files
        st.header("📄 Обработка DXF файлов")
        polygons = []
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
            status_text.text(f"Парсим файл {idx + 1}/{len(dxf_files)}: {file.name}")
            
            file.seek(0)
            file_bytes = BytesIO(file.read())
            parsed_data = parse_dxf_complete(file_bytes, verbose=False)
            if parsed_data and parsed_data['combined_polygon']:
                # Add color and order information to polygon tuple
                file_color = getattr(file, 'color', 'серый')
                file_order_id = getattr(file, 'order_id', 'unknown')
                
                # DEBUG: Log all file attributes to understand the issue
                file_attrs = [attr for attr in dir(file) if not attr.startswith('_')]
                logger.debug(f"ФАЙЛ {file.name}: атрибуты = {file_attrs}")
                logger.debug(f"ФАЙЛ {file.name}: color = {file_color}, order_id = {file_order_id}")
                
                # Use the combined polygon with extended format: (polygon, filename, color, order_id)
                polygon_tuple = (parsed_data['combined_polygon'], file.name, file_color, file_order_id)
                polygons.append(polygon_tuple)
                logger.info(f"ДОБАВЛЕН ПОЛИГОН: tuple длина={len(polygon_tuple)}, order_id={polygon_tuple[3] if len(polygon_tuple) > 3 else 'НЕТ'}")
                # Store original DXF data for this file
                original_dxf_data_map[file.name] = parsed_data
                logger.info(f"СОЗДАН ПОЛИГОН: файл={file.name}, заказ={file_order_id}, цвет={file_color}")
            else:
                logger.warning(f"Не удалось получить полигон из файла {file.name}")
        
        # Clear progress indicators
        progress_bar.empty()
        status_text.text(f"✅ Обработка завершена! Загружено {len(polygons)} полигонов из {len(dxf_files)} файлов")
        
        # Show detailed parsing info in expander
        with st.expander("🔍 Подробная информация о парсинге файлов", expanded=False):
            st.write("Подробная информация об улучшенном парсинге файлов:")
            for file in dxf_files:
                st.write(f"**Анализ файла: {file.name}**")
                file.seek(0)
                file_bytes = BytesIO(file.read())
                parse_dxf_complete(file_bytes, verbose=True)
        
        if not polygons:
            st.error("В загруженных DXF файлах не найдено валидных полигонов!")
            st.stop()
        
        # Show order distribution before optimization
        order_counts = {}
        for polygon_tuple in polygons:
            if len(polygon_tuple) >= 4:
                order_id = polygon_tuple[3]
                order_counts[order_id] = order_counts.get(order_id, 0) + 1
        
        logger.info(f"Анализ заказов: найдено {len(order_counts)} уникальных заказов")
        for order_id, count in order_counts.items():
            logger.info(f"  • Заказ {order_id}: {count} файлов")
        
        st.info(f"📋 Найдено {len(order_counts)} уникальных заказов:")
        for order_id, count in order_counts.items():
            st.write(f"  • Заказ {order_id}: {count} файлов")
        
        # Show input visualization
        st.header("🔍 Визуализация входных файлов")
        input_plots = plot_input_polygons(polygons)
        if input_plots:
            # Show color legend
            with st.expander("🎨 Цветовая схема файлов", expanded=False):
                legend_cols = st.columns(min(5, len(polygons)))
                for i, polygon_tuple in enumerate(polygons):
                    if len(polygon_tuple) >= 3:  # New format with color
                        _, file_name, _ = polygon_tuple[:3]
                    else:  # Old format without color
                        _, file_name = polygon_tuple[:2]
                    with legend_cols[i % len(legend_cols)]:
                        from layout_optimizer import get_color_for_file
                        color = get_color_for_file(file_name)
                        # Convert RGB to hex for HTML
                        color_hex = f"#{int(color[0]*255):02x}{int(color[1]*255):02x}{int(color[2]*255):02x}"
                        st.markdown(f'<div style="background-color: {color_hex}; padding: 10px; border-radius: 5px; text-align: center; margin: 2px;"><b>{file_name}</b></div>', 
                                  unsafe_allow_html=True)
            
            cols = st.columns(min(3, len(input_plots)))
            for i, (file_name, plot_buf) in enumerate(input_plots.items()):
                with cols[i % len(cols)]:
                    st.image(plot_buf, caption=f"{file_name}", use_container_width=True)
        
        # Show polygon statistics with real dimensions
        st.subheader("📊 Статистика исходных файлов")
        
        # Store original dimensions for comparison later
        original_dimensions = {}
        
        # Create a summary table with proper unit conversion
        summary_data = []
        total_area_cm2 = 0
        for polygon_tuple in polygons:
            if len(polygon_tuple) >= 4:  # Extended format with color and order_id
                poly, filename, color, order_id = polygon_tuple[:4]
            elif len(polygon_tuple) >= 3:  # Format with color
                poly, filename, color = polygon_tuple[:3]
                order_id = 'unknown'
            else:  # Old format without color
                poly, filename = polygon_tuple[:2]
                color = 'серый'
                order_id = 'unknown'
            bounds = poly.bounds
            width_mm = bounds[2] - bounds[0]
            height_mm = bounds[3] - bounds[1]
            area_mm2 = poly.area
            
            # Convert from mm to cm
            width_cm = width_mm / 10.0
            height_cm = height_mm / 10.0
            area_cm2 = area_mm2 / 100.0
            
            # Store original dimensions
            original_dimensions[filename] = {
                "width_cm": width_cm,
                "height_cm": height_cm,
                "area_cm2": area_cm2
            }
            
            total_area_cm2 += area_cm2
            # Add color emoji for display
            color_emoji = "⚫" if color == "чёрный" else "⚪" if color == "серый" else "🔘"
            color_display = f"{color_emoji} {color}"
            
            summary_data.append({
                "Файл": filename,
                "Ширина (см)": f"{width_cm:.1f}",
                "Высота (см)": f"{height_cm:.1f}",
                "Площадь (см²)": f"{area_cm2:.2f}",
                "Цвет": color_display,
                "Заказ": order_id if order_id != 'unknown' else '-'
            })
        
        summary_df = pd.DataFrame(summary_data)
        st.dataframe(summary_df, use_container_width=True)
        
        # Calculate theoretical minimum using largest available sheet
        largest_sheet_area = max(sheet['width'] * sheet['height'] for sheet in st.session_state.available_sheets)
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Всего объектов", len(polygons))
        with col2:
            st.metric("Общая площадь", f"{total_area_cm2:.2f} см²")
        with col3:
            st.metric("Теоретический минимум листов", max(1, int(np.ceil(total_area_cm2 / largest_sheet_area))))
        
        # Auto-scale polygons if needed (use largest available sheet for scaling reference)
        st.header("📐 Масштабирование полигонов")
        
        # Find largest sheet for scaling reference
        max_sheet_area = 0
        reference_sheet_size = (140, 200)  # default fallback
        for sheet in st.session_state.available_sheets:
            area = sheet['width'] * sheet['height']
            if area > max_sheet_area:
                max_sheet_area = area
                reference_sheet_size = (sheet['width'], sheet['height'])
        
        # Scale quietly first
        scaled_polygons = scale_polygons_to_fit(polygons, reference_sheet_size, verbose=False)
        
        # Show scaling details in expander
        with st.expander("🔍 Подробная информация о масштабировании", expanded=False):
            st.info(f"Используем самый большой лист ({reference_sheet_size[0]}x{reference_sheet_size[1]} см) как эталон для масштабирования")
            scale_polygons_to_fit(polygons, reference_sheet_size, verbose=True)
        
        polygons = scaled_polygons
        
        st.header("🔄 Процесс оптимизации")

        try:
            # Debug processing with detailed info
            with st.expander("🔍 Подробная информация об оптимизации", expanded=False):
                debug_layouts, debug_unplaced = bin_packing_with_inventory(polygons, st.session_state.available_sheets, verbose=True, max_sheets_per_order=MAX_SHEETS_PER_ORDER)
            
            # Actual processing (quiet)
            logger.info(f"Вызываем bin_packing_with_inventory с MAX_SHEETS_PER_ORDER={MAX_SHEETS_PER_ORDER}")
            logger.info(f"Входные параметры: {len(polygons)} полигонов, {len(st.session_state.available_sheets)} типов листов")
            
            # DEBUG: Log what polygons we're sending
            logger.info("ПОЛИГОНЫ ПЕРЕД ОТПРАВКОЙ В bin_packing_with_inventory:")
            for i, polygon_tuple in enumerate(polygons):
                if len(polygon_tuple) >= 4:
                    logger.info(f"  Полигон {i}: файл={polygon_tuple[1]}, order_id={polygon_tuple[3]}")
                else:
                    logger.warning(f"  Полигон {i}: неполный tuple (длина={len(polygon_tuple)})")
            
            placed_layouts, unplaced_polygons = bin_packing_with_inventory(polygons, st.session_state.available_sheets, verbose=False, max_sheets_per_order=MAX_SHEETS_PER_ORDER)
            logger.info(f"Результат bin_packing: {len(placed_layouts)} размещенных листов, {len(unplaced_polygons)} неразмещенных полигонов")
        
        except ValueError as e:
            # Handle order constraint violations
            if "Нарушение ограничений заказов" in str(e):
                st.error(f"❌ {str(e)}")
                st.info(f"💡 **Решение**: Увеличьте константу MAX_SHEETS_PER_ORDER (сейчас: {MAX_SHEETS_PER_ORDER}) или разделите файлы заказа на несколько частей.")
                st.stop()
            else:
                # Re-raise other ValueError exceptions
                raise
        
        # Convert to old format for compatibility with existing display code
        all_layouts = []
        report_data = []
        
        for i, layout in enumerate(placed_layouts):
            # Save and visualize layout with new naming format: length_width_number.dxf
            sheet_width = int(layout['sheet_size'][0])
            sheet_height = int(layout['sheet_size'][1]) 
            sheet_number = layout['sheet_number']
            output_filename = f"{sheet_height}_{sheet_width}_{sheet_number}.dxf"
            output_file = os.path.join(OUTPUT_FOLDER, output_filename)
            save_dxf_layout_complete(layout['placed_polygons'], layout['sheet_size'], output_file, original_dxf_data_map)
            layout_plot = plot_layout(layout['placed_polygons'], layout['sheet_size'])

            # Find sheet color from original sheet data
            sheet_color = "не указан"
            for sheet in st.session_state.available_sheets:
                if sheet['name'] == layout['sheet_type']:
                    sheet_color = sheet.get('color', 'не указан')
                    break
            
            # Store layout info in old format for compatibility
            all_layouts.append({
                "Sheet": layout['sheet_number'],
                "Sheet Type": layout['sheet_type'],
                "Sheet Color": sheet_color,
                "Sheet Size": f"{layout['sheet_size'][0]}x{layout['sheet_size'][1]} см",
                "Output File": output_file,
                "Plot": layout_plot,
                "Shapes Placed": len(layout['placed_polygons']),
                "Material Usage (%)": f"{layout['usage_percent']:.2f}",
                "Placed Polygons": layout['placed_polygons']
            })
            report_data.extend([(p[4], layout['sheet_number'], output_file) for p in layout['placed_polygons']])
        
        # Update sheet inventory in session state
        for layout in placed_layouts:
            for original_sheet in st.session_state.available_sheets:
                if layout['sheet_type'] == original_sheet['name']:
                    original_sheet['used'] += 1
                    break

        # Display Results
        st.header("📊 Результаты")
        if all_layouts:
            st.success(f"✅ Успешно использовано листов: {len(all_layouts)}")
            
            # Summary statistics
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Всего листов", len(all_layouts))
            with col2:
                total_placed = sum(layout["Shapes Placed"] for layout in all_layouts)
                st.metric("Размещено объектов", f"{total_placed}/{len(polygons)}")
            with col3:
                avg_usage = sum(float(layout["Material Usage (%)"].replace('%', '')) for layout in all_layouts) / len(all_layouts)
                st.metric("Средний расход материала", f"{avg_usage:.1f}%")
            with col4:
                if unplaced_polygons:
                    st.metric("Не размещено", len(unplaced_polygons), delta=f"-{len(unplaced_polygons)}", delta_color="inverse")
                else:
                    st.metric("Не размещено", 0, delta="Все размещено ✅")
            
            # Show updated inventory
            st.subheader("📦 Обновленный инвентарь листов")
            updated_sheets_data = []
            for sheet in st.session_state.available_sheets:
                # Add color indicator
                color = sheet.get('color', 'не указан')
                color_emoji = "⚫" if color == "чёрный" else "⚪" if color == "серый" else "🔘"
                color_display = f"{color_emoji} {color}"
                
                updated_sheets_data.append({
                    "Тип листа": sheet['name'],
                    "Размер (см)": f"{sheet['width']}x{sheet['height']}",
                    "Цвет": color_display,
                    "Было": sheet['count'],
                    "Использовано": sheet['used'],
                    "Осталось": sheet['count'] - sheet['used']
                })
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
                        color = 'серый'
                    bounds = polygon.bounds
                    width_cm = (bounds[2] - bounds[0]) / 10
                    height_cm = (bounds[3] - bounds[1]) / 10
                    area_cm2 = polygon.area / 100
                    
                    # Compare with original dimensions
                    original = original_dimensions.get(file_name, {})
                    original_width = original.get("width_cm", 0)
                    original_height = original.get("height_cm", 0)
                    original_area = original.get("area_cm2", 0)
                    
                    scale_factor = (width_cm / original_width) if original_width > 0 else 1.0
                    
                    size_comparison = f"{width_cm:.1f}×{height_cm:.1f}"
                    if abs(scale_factor - 1.0) > 0.01:  # If scaled
                        size_comparison += f" (было {original_width:.1f}×{original_height:.1f})"
                    
                    enhanced_report_data.append({
                        "DXF файл": file_name,
                        "Номер листа": layout["Sheet"],
                        "Размер (см)": size_comparison,
                        "Площадь (см²)": f"{area_cm2:.2f}",
                        "Поворот (°)": f"{angle:.0f}",
                        "Выходной файл": layout["Output File"]
                    })
            
            if enhanced_report_data:
                enhanced_df = pd.DataFrame(enhanced_report_data)
                st.dataframe(enhanced_df, use_container_width=True)
                # Also create simple report_df for export
                report_df = pd.DataFrame(report_data, columns=["DXF файл", "Номер листа", "Выходной файл"])
            else:
                report_df = pd.DataFrame(report_data, columns=["DXF файл", "Номер листа", "Выходной файл"])
                st.dataframe(report_df, use_container_width=True)

            # Sheet visualizations
            st.subheader("📐 Схемы раскроя листов")
            for layout in all_layouts:
                # Add color indicator emoji
                color_emoji = "⚫" if layout['Sheet Color'] == "чёрный" else "⚪" if layout['Sheet Color'] == "серый" else "🔘"
                
                st.write(f"**Лист №{layout['Sheet']}: {color_emoji} {layout['Sheet Type']} ({layout['Sheet Size']}) - {layout['Shapes Placed']} объектов - {layout['Material Usage (%)']}% расход**")
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.image(layout["Plot"], caption=f"Раскрой листа №{layout['Sheet']} ({layout['Sheet Type']})", use_container_width=True)
                with col2:
                    st.write(f"**Тип листа:** {layout['Sheet Type']}")
                    st.write(f"**Цвет листа:** {color_emoji} {layout['Sheet Color']}")
                    st.write(f"**Размер листа:** {layout['Sheet Size']}")
                    st.write(f"**Размещено объектов:** {layout['Shapes Placed']}")
                    st.write(f"**Расход материала:** {layout['Material Usage (%)']}%")
                    with open(layout["Output File"], "rb") as f:
                        st.download_button(
                            label=f"📥 Скачать DXF",
                            data=f,
                            file_name=os.path.basename(layout["Output File"]),
                            mime="application/dxf",
                            key=f"download_{layout['Sheet']}"
                        )
                st.divider()  # Add visual separator between sheets
        else:
            st.error("❌ Не было создано ни одного листа. Проверьте отладочную информацию выше.")
        
        # Show unplaced polygons if any
        if unplaced_polygons:
            st.warning(f"⚠️ {len(unplaced_polygons)} объектов не удалось разместить.")
            st.subheader("🚫 Неразмещенные объекты")
            unplaced_data = []
            for polygon_tuple in unplaced_polygons:
                if len(polygon_tuple) >= 3:  # New format with color
                    poly, name, color = polygon_tuple[:3]
                else:  # Old format without color
                    poly, name = polygon_tuple[:2]
                    color = 'серый'
                unplaced_data.append((name, f"{poly.area/100:.2f}", color))
            
            unplaced_df = pd.DataFrame(unplaced_data, columns=["Файл", "Площадь (см²)", "Цвет"])
            st.dataframe(unplaced_df, use_container_width=True)

        # Save report
        if all_layouts:
            report_file = os.path.join(OUTPUT_FOLDER, f"layout_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx")
            
            # Use enhanced report if available, otherwise simple report
            if enhanced_report_data:
                enhanced_df.to_excel(report_file, index=False)
            elif 'report_df' in locals():
                report_df.to_excel(report_file, index=False)
            else:
                # Fallback: create simple report from report_data
                fallback_df = pd.DataFrame(report_data, columns=["DXF файл", "Номер листа", "Выходной файл"])
                fallback_df.to_excel(report_file, index=False)
            
            # Create ZIP archive with all DXF files
            zip_filename = f"layout_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
            zip_path = os.path.join(OUTPUT_FOLDER, zip_filename)
            
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
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
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
            
            with col2:
                with open(zip_path, "rb") as f:
                    st.download_button(
                        label="📦 Скачать все файлы (ZIP)",
                        data=f,
                        file_name=zip_filename,
                        mime="application/zip"
                    )

# Footer
#st.write("Примечание: Приложение использует простой алгоритм упаковки. Для лучшей оптимизации рассмотрите продвинутые методы, такие как BL-NFP.")