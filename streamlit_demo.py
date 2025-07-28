import streamlit as st
import pandas as pd
import numpy as np
import os
import uuid
from datetime import datetime
from io import BytesIO

from layout_optimizer import parse_dxf, bin_packing, save_dxf_layout, plot_layout, plot_input_polygons, scale_polygons_to_fit

# Configuration
DEFAULT_SHEET_SIZES = [
    (140, 200), (142, 200), (144, 200), (146, 200), (148, 200),
    (140, 195), (142, 195), (144, 195), (146, 195), (148, 195)
]
OUTPUT_FOLDER = "output_layouts"
os.makedirs(OUTPUT_FOLDER, exist_ok=True)


# Streamlit App
st.title("Оптимизатор раскроя EVA ковриков")
st.write("Загрузите DXF файлы и укажите размер листа для оптимального размещения ковриков.")

# Input Section
st.header("Параметры входных данных")
sheet_size_option = st.selectbox("Выберите размер листа (см)", ["Произвольный"] + [f"{w}x{h}" for w, h in DEFAULT_SHEET_SIZES])
if sheet_size_option == "Произвольный":
    sheet_width = st.number_input("Ширина листа (см)", min_value=50.0, max_value=300.0, value=140.0)
    sheet_height = st.number_input("Высота листа (см)", min_value=50.0, max_value=300.0, value=200.0)
    sheet_size = (sheet_width, sheet_height)
else:
    sheet_size = tuple(map(float, sheet_size_option.split("x")))
dxf_files = st.file_uploader("Загрузите DXF файлы", type=["dxf"], accept_multiple_files=True)

if st.button("Оптимизировать раскрой"):
    if not dxf_files:
        st.error("Пожалуйста, загрузите хотя бы один DXF файл.")
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
        
        sheet_area = sheet_size[0] * sheet_size[1]
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Всего объектов", len(polygons))
        with col2:
            st.metric("Общая площадь", f"{total_area_cm2:.2f} см²")
        with col3:
            st.metric("Теоретический минимум листов", max(1, int(np.ceil(total_area_cm2 / sheet_area))))
        
        # Auto-scale polygons if needed
        st.header("📐 Масштабирование полигонов")
        
        # Scale quietly first
        scaled_polygons = scale_polygons_to_fit(polygons, sheet_size, verbose=False)
        
        # Show scaling details in expander
        with st.expander("🔍 Подробная информация о масштабировании", expanded=False):
            scale_polygons_to_fit(polygons, sheet_size, verbose=True)
        
        polygons = scaled_polygons
        
        st.header("🔄 Процесс оптимизации")

        # Process layouts
        all_layouts = []
        remaining_polygons = polygons
        sheet_count = 0
        report_data = []

        with st.expander("🔍 Подробная информация об оптимизации", expanded=False):
            remaining_polygons_debug = remaining_polygons.copy()
            sheet_count_debug = 0
            
            while remaining_polygons_debug:
                sheet_count_debug += 1
                st.write(f"**Обработка листа {sheet_count_debug}**")
                placed_debug, unplaced_debug = bin_packing(remaining_polygons_debug, sheet_size, verbose=True)
                if not placed_debug:
                    st.warning(f"Не удалось разместить оставшиеся {len(unplaced_debug)} объектов.")
                    break
                remaining_polygons_debug = unplaced_debug
                if not remaining_polygons_debug:
                    break
        
        # Actual processing (quiet)
        while remaining_polygons:
            sheet_count += 1
            placed, unplaced = bin_packing(remaining_polygons, sheet_size, verbose=False)
            if not placed:
                st.warning(f"Не удалось разместить оставшиеся {len(unplaced)} объектов.")
                break

            # Save and visualize layout
            output_file = os.path.join(OUTPUT_FOLDER, f"layout_sheet_{sheet_count}_{uuid.uuid4()}.dxf")
            save_dxf_layout(placed, sheet_size, output_file)
            layout_plot = plot_layout(placed, sheet_size)

            # Calculate material usage (convert areas to same units)
            used_area_mm2 = sum(p[0].area for p in placed)  # Area in mm²
            sheet_area_mm2 = (sheet_size[0] * 10) * (sheet_size[1] * 10)  # Convert cm² to mm²
            usage_percent = (used_area_mm2 / sheet_area_mm2) * 100

            # Store layout info
            all_layouts.append({
                "Sheet": sheet_count,
                "Output File": output_file,
                "Plot": layout_plot,
                "Shapes Placed": len(placed),
                "Material Usage (%)": f"{usage_percent:.2f}",
                "Placed Polygons": placed  # Store placed polygons for detailed report
            })
            report_data.extend([(p[4], sheet_count, output_file) for p in placed])
            remaining_polygons = unplaced

        # Display Results
        st.header("📊 Результаты")
        if all_layouts:
            st.success(f"✅ Успешно создано листов: {sheet_count}")
            
            # Summary statistics
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Всего листов", sheet_count)
            with col2:
                total_placed = sum(layout["Shapes Placed"] for layout in all_layouts)
                st.metric("Размещено объектов", f"{total_placed}/{len(polygons)}")
            with col3:
                avg_usage = sum(float(layout["Material Usage (%)"].replace('%', '')) for layout in all_layouts) / len(all_layouts)
                st.metric("Средний расход материала", f"{avg_usage:.1f}%")
            
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
                st.write(f"**Лист {layout['Sheet']} - {layout['Shapes Placed']} объектов - {layout['Material Usage (%)']} расход**")
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.image(layout["Plot"], caption=f"Раскрой листа {layout['Sheet']}", use_container_width=True)
                with col2:
                    st.write(f"**Размещено объектов:** {layout['Shapes Placed']}")
                    st.write(f"**Расход материала:** {layout['Material Usage (%)']}")
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
            if remaining_polygons:
                st.warning(f"⚠️ {len(remaining_polygons)} объектов не удалось разместить.")
                unplaced_df = pd.DataFrame([(name, f"{poly.area:.2f}") for poly, name in remaining_polygons], 
                                         columns=["Файл", "Площадь"])
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