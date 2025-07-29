import streamlit as st
import pandas as pd
import numpy as np
import os
import uuid
from datetime import datetime
from io import BytesIO

from layout_optimizer import parse_dxf, bin_packing, bin_packing_with_inventory, save_dxf_layout, plot_layout, plot_input_polygons, scale_polygons_to_fit

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
        
with col2:
    sheet_count = st.number_input("Количество листов", min_value=1, max_value=100, value=5, key="sheet_count")
    sheet_name = st.text_input("Название типа листа (опционально)", 
                              value=f"Лист {selected_size[0]}x{selected_size[1]}", 
                              key="sheet_name")

with col3:
    st.write("")
    st.write("")
    if st.button("➕ Добавить", key="add_sheet"):
        new_sheet = {
            "name": sheet_name,
            "width": selected_size[0],
            "height": selected_size[1], 
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
        sheets_data.append({
            "№": i + 1,
            "Название": sheet['name'],
            "Размер (см)": f"{sheet['width']}x{sheet['height']}",
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

# DXF Files Section
st.header("📄 Файлы для раскроя")
dxf_files = st.file_uploader("Загрузите DXF файлы", type=["dxf"], accept_multiple_files=True)

if st.button("🚀 Оптимизировать раскрой"):
    if not st.session_state.available_sheets:
        st.error("⚠️ Пожалуйста, добавьте хотя бы один тип листа в наличии.")
    elif not dxf_files:
        st.error("⚠️ Пожалуйста, загрузите хотя бы один DXF файл.")
    else:
        # Parse DXF files
        st.header("📄 Обработка DXF файлов")
        polygons = []
        
        # Parse files quietly first
        for file in dxf_files:
            file.seek(0)
            file_bytes = BytesIO(file.read())
            file_polygon = parse_dxf(file_bytes, verbose=False)
            if file_polygon:
                polygons.append((file_polygon, file.name))
        
        # Show detailed parsing info in expander
        with st.expander("🔍 Подробная информация о парсинге файлов", expanded=False):
            st.write("Повторный анализ файлов с подробной информацией:")
            for file in dxf_files:
                st.write(f"**Анализ файла: {file.name}**")
                file.seek(0)
                file_bytes = BytesIO(file.read())
                parse_dxf(file_bytes, verbose=True)
        
        if not polygons:
            st.error("В загруженных DXF файлах не найдено валидных полигонов!")
            st.stop()
        
        # Show input visualization
        st.header("🔍 Визуализация входных файлов")
        input_plots = plot_input_polygons(polygons)
        if input_plots:
            # Show color legend
            with st.expander("🎨 Цветовая схема файлов", expanded=False):
                legend_cols = st.columns(min(5, len(polygons)))
                for i, (_, file_name) in enumerate(polygons):
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
        for poly, filename in polygons:
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
            summary_data.append({
                "Файл": filename,
                "Ширина (см)": f"{width_cm:.1f}",
                "Высота (см)": f"{height_cm:.1f}",
                "Площадь (см²)": f"{area_cm2:.2f}"
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

        # Debug processing with detailed info
        with st.expander("🔍 Подробная информация об оптимизации", expanded=False):
            debug_layouts, debug_unplaced = bin_packing_with_inventory(polygons, st.session_state.available_sheets, verbose=True)
        
        # Actual processing (quiet)
        placed_layouts, unplaced_polygons = bin_packing_with_inventory(polygons, st.session_state.available_sheets, verbose=False)
        
        # Convert to old format for compatibility with existing display code
        all_layouts = []
        report_data = []
        
        for i, layout in enumerate(placed_layouts):
            # Save and visualize layout
            output_file = os.path.join(OUTPUT_FOLDER, f"layout_{layout['sheet_type'].replace(' ', '_')}_{layout['sheet_number']}_{uuid.uuid4()}.dxf")
            save_dxf_layout(layout['placed_polygons'], layout['sheet_size'], output_file)
            layout_plot = plot_layout(layout['placed_polygons'], layout['sheet_size'])

            # Store layout info in old format for compatibility
            all_layouts.append({
                "Sheet": layout['sheet_number'],
                "Sheet Type": layout['sheet_type'],
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
                updated_sheets_data.append({
                    "Тип листа": sheet['name'],
                    "Размер (см)": f"{sheet['width']}x{sheet['height']}",
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
                for polygon, _, _, angle, file_name in layout["Placed Polygons"]:
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
                        "Масштаб": f"{scale_factor:.3f}" if abs(scale_factor - 1.0) > 0.01 else "1.000",
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
                st.write(f"**Лист №{layout['Sheet']}: {layout['Sheet Type']} ({layout['Sheet Size']}) - {layout['Shapes Placed']} объектов - {layout['Material Usage (%)']}% расход**")
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.image(layout["Plot"], caption=f"Раскрой листа №{layout['Sheet']} ({layout['Sheet Type']})", use_container_width=True)
                with col2:
                    st.write(f"**Тип листа:** {layout['Sheet Type']}")
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
            unplaced_df = pd.DataFrame([(name, f"{poly.area/100:.2f}") for poly, name in unplaced_polygons], 
                                     columns=["Файл", "Площадь (см²)"])
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
            
            with open(report_file, "rb") as f:
                st.download_button(
                    label="📊 Скачать отчет",
                    data=f,
                    file_name=os.path.basename(report_file),
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

# Footer
#st.write("Примечание: Приложение использует простой алгоритм упаковки. Для лучшей оптимизации рассмотрите продвинутые методы, такие как BL-NFP.")