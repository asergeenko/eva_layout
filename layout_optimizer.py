"""Helper functions for EVA mat nesting optimization."""

import numpy as np
from shapely.geometry import Polygon
from shapely import affinity
import ezdxf
import matplotlib.pyplot as plt
from io import BytesIO
import streamlit as st
import tempfile
import os
import hashlib


def get_color_for_file(filename: str):
    """Generate a consistent color for a given filename."""
    # Use hash of filename to generate consistent color
    hash_object = hashlib.md5(filename.encode())
    hash_hex = hash_object.hexdigest()
    
    # Convert first 6 characters of hash to RGB
    r = int(hash_hex[0:2], 16) / 255.0
    g = int(hash_hex[2:4], 16) / 255.0  
    b = int(hash_hex[4:6], 16) / 255.0
    
    # Ensure colors are not too dark or too light
    r = max(0.2, min(0.9, r))
    g = max(0.2, min(0.9, g))
    b = max(0.2, min(0.9, b))
    
    return (r, g, b)


def parse_dxf(file, verbose=True) -> Polygon:
    """Parse a DXF file to extract all shapes and combine them into one polygon."""
    if hasattr(file, 'read'):
        # If it's a file-like object (BytesIO), write to temp file first
        with tempfile.NamedTemporaryFile(suffix='.dxf', delete=False) as tmp_file:
            file.seek(0)  # Ensure we're at the beginning
            tmp_file.write(file.read())
            tmp_file.flush()
            temp_path = tmp_file.name
        
        try:
            doc = ezdxf.readfile(temp_path)
        finally:
            # Clean up temp file
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    else:
        # If it's a file path string
        doc = ezdxf.readfile(file)
    msp = doc.modelspace()
    polygons = []
    total_entities = 0
    lwpolyline_count = 0
    
    entity_types = {}
    
    for entity in msp:
        total_entities += 1
        entity_type = entity.dxftype()
        entity_types[entity_type] = entity_types.get(entity_type, 0) + 1
        
        try:
            polygon = None
            
            if entity_type == "LWPOLYLINE":
                lwpolyline_count += 1
                points = [(p[0], p[1]) for p in entity.get_points()]
                if len(points) >= 3:
                    polygon = Polygon(points)
                    
            elif entity_type == "POLYLINE":
                points = [(vertex.dxf.location[0], vertex.dxf.location[1]) for vertex in entity.vertices]
                if len(points) >= 3:
                    polygon = Polygon(points)
                    
            elif entity_type == "SPLINE":
                # Convert SPLINE to polygon by sampling points
                try:
                    # Sample points along the spline
                    sampled_points = []
                    for t in np.linspace(0, 1, 50):  # Sample 50 points
                        point = entity.construction_tool().point(t)
                        sampled_points.append((point.x, point.y))
                    if len(sampled_points) >= 3:
                        polygon = Polygon(sampled_points)
                except Exception as spline_error:
                    # Fallback: try to get control points
                    try:
                        control_points = [(cp[0], cp[1]) for cp in entity.control_points]
                        if len(control_points) >= 3:
                            polygon = Polygon(control_points)
                    except:
                        pass
                        
            elif entity_type == "ELLIPSE":
                # Convert ELLIPSE to polygon by sampling points
                try:
                    sampled_points = []
                    for angle in np.linspace(0, 2*np.pi, 36):  # Sample 36 points
                        point = entity.construction_tool().point(angle)
                        sampled_points.append((point.x, point.y))
                    if len(sampled_points) >= 3:
                        polygon = Polygon(sampled_points)
                except:
                    pass
                    
            elif entity_type == "CIRCLE":
                # Convert CIRCLE to polygon
                try:
                    center = entity.dxf.center
                    radius = entity.dxf.radius
                    sampled_points = []
                    for angle in np.linspace(0, 2*np.pi, 36):
                        x = center[0] + radius * np.cos(angle)
                        y = center[1] + radius * np.sin(angle)
                        sampled_points.append((x, y))
                    polygon = Polygon(sampled_points)
                except:
                    pass
                    
            elif entity_type == "ARC":
                # Convert ARC to polygon (as a sector or just the arc line)
                try:
                    center = entity.dxf.center
                    radius = entity.dxf.radius
                    start_angle = np.radians(entity.dxf.start_angle)
                    end_angle = np.radians(entity.dxf.end_angle)
                    
                    sampled_points = [center[:2]]  # Start from center for sector
                    angles = np.linspace(start_angle, end_angle, 20)
                    for angle in angles:
                        x = center[0] + radius * np.cos(angle)
                        y = center[1] + radius * np.sin(angle)
                        sampled_points.append((x, y))
                    sampled_points.append(center[:2])  # Close the sector
                    polygon = Polygon(sampled_points)
                except:
                    pass
                    
            # Check if we got a valid polygon
            if polygon and polygon.is_valid and polygon.area > 0:
                polygons.append(polygon)
                
        except Exception as e:
            if verbose:
                st.warning(f"Ошибка обработки {entity_type}: {e}")
    
    if verbose:
        st.info(f"Всего объектов: {total_entities}")
        st.info(f"Найденные типы объектов: {entity_types}")
        st.info(f"Создано валидных полигонов: {len(polygons)}")
    
    # Combine all polygons into one using unary_union
    if polygons:
        from shapely.ops import unary_union
        combined = unary_union(polygons)
        
        # If result is MultiPolygon, get the convex hull to make it a single polygon
        if hasattr(combined, 'geoms'):
            # It's a MultiPolygon, take convex hull to get single polygon
            combined = combined.convex_hull
            if verbose:
                st.info(f"Объединено в один полигон (convex hull), площадь: {combined.area:.2f}")
        else:
            if verbose:
                st.info(f"Объединено в один полигон, площадь: {combined.area:.2f}")
            
        return combined
    else:
        if verbose:
            st.error("Не найдено валидных полигонов для объединения")
        return None


def rotate_polygon(polygon: Polygon, angle: float) -> Polygon:
    """Rotate a polygon by a given angle (in degrees)."""
    return affinity.rotate(polygon, angle, origin="centroid")


def translate_polygon(polygon: Polygon, x: float, y: float) -> Polygon:
    """Translate a polygon to a new position."""
    return affinity.translate(polygon, xoff=x, yoff=y)


def place_polygon_at_origin(polygon: Polygon) -> Polygon:
    """Move polygon so its bottom-left corner is at (0,0)."""
    bounds = polygon.bounds
    return translate_polygon(polygon, -bounds[0], -bounds[1])


def check_collision(polygon1: Polygon, polygon2: Polygon) -> bool:
    """Check if two polygons collide."""
    return polygon1.intersects(polygon2) and not polygon1.touches(polygon2)


def bin_packing_with_inventory(polygons: list[tuple[Polygon, str]], available_sheets: list[dict], verbose: bool = True) -> tuple[list[dict], list[tuple[Polygon, str]]]:
    """Optimize placement of polygons on available sheets with inventory tracking."""
    placed_layouts = []
    unplaced = polygons.copy()
    sheet_inventory = [sheet.copy() for sheet in available_sheets]  # Copy to avoid modifying original
    
    if verbose:
        total_available = sum(sheet['count'] - sheet['used'] for sheet in sheet_inventory)
        st.info(f"Начинаем размещение {len(polygons)} полигонов на {total_available} доступных листах")
    
    sheet_counter = 0
    
    while unplaced and any(sheet['count'] - sheet['used'] > 0 for sheet in sheet_inventory):
        placed_on_current_sheet = False
        
        # Try each available sheet type
        for sheet_type in sheet_inventory:
            if sheet_type['count'] - sheet_type['used'] <= 0:
                continue  # No more sheets of this type
            
            sheet_size = (sheet_type['width'], sheet_type['height'])
            sheet_counter += 1
            
            if verbose:
                st.info(f"Пробуем лист #{sheet_counter}: {sheet_type['name']} ({sheet_size[0]}x{sheet_size[1]} см)")
            
            # Try to place polygons on this sheet
            placed, remaining = bin_packing(unplaced, sheet_size, verbose=verbose)
            
            if placed:  # If we managed to place something
                sheet_type['used'] += 1
                placed_layouts.append({
                    'sheet_number': sheet_counter,
                    'sheet_type': sheet_type['name'],
                    'sheet_size': sheet_size,
                    'placed_polygons': placed,
                    'usage_percent': calculate_usage_percent(placed, sheet_size)
                })
                unplaced = remaining
                placed_on_current_sheet = True
                
                if verbose:
                    st.success(f"Размещено {len(placed)} объектов на листе {sheet_type['name']}")
                break  # Move to next iteration with remaining polygons
        
        if not placed_on_current_sheet:
            # No sheet type could accommodate any remaining polygons
            break
    
    if verbose:
        st.info(f"Размещение завершено: {len(placed_layouts)} листов использовано, {len(unplaced)} объектов не размещено")
    
    return placed_layouts, unplaced


def calculate_usage_percent(placed_polygons: list[tuple[Polygon, float, float, float, str]], sheet_size: tuple[float, float]) -> float:
    """Calculate material usage percentage for a sheet."""
    used_area_mm2 = sum(p[0].area for p in placed_polygons)
    sheet_area_mm2 = (sheet_size[0] * 10) * (sheet_size[1] * 10)
    return (used_area_mm2 / sheet_area_mm2) * 100


def bin_packing(polygons: list[tuple[Polygon, str]], sheet_size: tuple[float, float], max_attempts: int = 1000, verbose: bool = True) -> tuple[list[tuple[Polygon, float, float, float, str]], list[tuple[Polygon, str]]]:
    """Optimize placement of complex polygons on a sheet."""
    # Convert sheet size from cm to mm to match DXF polygon units
    sheet_width_mm, sheet_height_mm = sheet_size[0] * 10, sheet_size[1] * 10
    sheet = Polygon([(0, 0), (sheet_width_mm, 0), (sheet_width_mm, sheet_height_mm), (0, sheet_height_mm)])
    placed = []
    unplaced = []
    
    if verbose:
        st.info(f"Начинаем упаковку {len(polygons)} полигонов на листе {sheet_size[0]}x{sheet_size[1]} см")
    
    for i, (polygon, file_name) in enumerate(polygons):
        placed_successfully = False
        if verbose:
            st.info(f"Обрабатываем полигон {i+1}/{len(polygons)} из файла {file_name}, площадь: {polygon.area:.2f}")
        
        # Check if polygon is too large for the sheet
        bounds = polygon.bounds
        poly_width = bounds[2] - bounds[0]
        poly_height = bounds[3] - bounds[1]
        
        if poly_width > sheet_width_mm or poly_height > sheet_height_mm:
            if verbose:
                st.warning(f"Полигон из {file_name} слишком большой: {poly_width/10:.1f}x{poly_height/10:.1f} см > {sheet_size[0]}x{sheet_size[1]} см")
            unplaced.append((polygon, file_name))
            continue
        
        # First try simple placement without rotation
        simple_bounds = polygon.bounds
        simple_width = simple_bounds[2] - simple_bounds[0]
        simple_height = simple_bounds[3] - simple_bounds[1]
        
        if verbose:
            st.info(f"Размеры полигона: {simple_width/10:.1f}x{simple_height/10:.1f} см, размеры листа: {sheet_size[0]}x{sheet_size[1]} см")
        
        # First try simple placement at origin
        if len(placed) == 0:  # First polygon - try to place at origin
            origin_polygon = place_polygon_at_origin(polygon)
            origin_bounds = origin_polygon.bounds
            
            if (origin_bounds[2] <= sheet_width_mm and origin_bounds[3] <= sheet_height_mm):
                placed.append((origin_polygon, 0, 0, 0, file_name))
                placed_successfully = True
                if verbose:
                    st.success(f"Успешно размещен полигон из {file_name} в начале координат")
        
        # If origin placement failed or not first polygon, try systematic grid placement
        if not placed_successfully:
            max_grid_attempts = 10
            x_positions = np.linspace(0, max(0, sheet_width_mm - simple_width), max_grid_attempts) if sheet_width_mm > simple_width else [0]
            y_positions = np.linspace(0, max(0, sheet_height_mm - simple_height), max_grid_attempts) if sheet_height_mm > simple_height else [0]
            
            for grid_x in x_positions:
                for grid_y in y_positions:
                    # Move polygon to grid position
                    translated = translate_polygon(polygon, grid_x - simple_bounds[0], grid_y - simple_bounds[1])
                    
                    # Check if polygon is within sheet bounds with small tolerance
                    translated_bounds = translated.bounds
                    if (translated_bounds[0] >= -0.01 and translated_bounds[1] >= -0.01 and 
                        translated_bounds[2] <= sheet_width_mm + 0.01 and translated_bounds[3] <= sheet_height_mm + 0.01):
                        
                        # Check for collisions with already placed polygons
                        collision = any(check_collision(translated, p[0]) for p in placed)
                        if not collision:
                            placed.append((translated, grid_x - simple_bounds[0], grid_y - simple_bounds[1], 0, file_name))
                            placed_successfully = True
                            if verbose:
                                st.success(f"Успешно размещен полигон из {file_name} (сетчатое размещение в позиции {grid_x:.1f}, {grid_y:.1f})")
                            break
                
                if placed_successfully:
                    break
        
        # If grid placement failed, try random placement with rotations
        if not placed_successfully:
            if verbose:
                st.info(f"Сетчатое размещение не удалось, пробуем случайное размещение с поворотами")
            
            # Try basic 4 orientations first
            for angle in [0, 90, 180, 270]:
                if placed_successfully:
                    break
                    
                rotated = rotate_polygon(polygon, angle)
                rotated_bounds = rotated.bounds
                rotated_width = rotated_bounds[2] - rotated_bounds[0]
                rotated_height = rotated_bounds[3] - rotated_bounds[1]
                
                if verbose:
                    st.info(f"Проверяем поворот на {angle}°: размеры {rotated_width/10:.1f}x{rotated_height/10:.1f} см")
                
                if rotated_width <= sheet_width_mm and rotated_height <= sheet_height_mm:
                    # Try placing at origin first
                    origin_rotated = place_polygon_at_origin(rotated)
                    origin_bounds = origin_rotated.bounds
                    
                    if (origin_bounds[2] <= sheet_width_mm and origin_bounds[3] <= sheet_height_mm):
                        collision = any(check_collision(origin_rotated, p[0]) for p in placed)
                        if not collision:
                            placed.append((origin_rotated, 0, 0, angle, file_name))
                            placed_successfully = True
                            if verbose:
                                st.success(f"Успешно размещен полигон из {file_name} (поворот {angle}°, начало координат)")
                            break
                    
                    # If origin placement failed, try grid positions
                    if not placed_successfully:
                        for grid_x in np.linspace(0, sheet_width_mm - rotated_width, 10):
                            for grid_y in np.linspace(0, sheet_height_mm - rotated_height, 10):
                                translated = translate_polygon(rotated, grid_x - rotated_bounds[0], grid_y - rotated_bounds[1])
                                
                                final_bounds = translated.bounds
                                if (final_bounds[0] >= -0.01 and final_bounds[1] >= -0.01 and 
                                    final_bounds[2] <= sheet_width_mm + 0.01 and final_bounds[3] <= sheet_height_mm + 0.01):
                                    
                                    collision = any(check_collision(translated, p[0]) for p in placed)
                                    if not collision:
                                        placed.append((translated, grid_x - rotated_bounds[0], grid_y - rotated_bounds[1], angle, file_name))
                                        placed_successfully = True
                                        if verbose:
                                            st.success(f"Успешно размещен полигон из {file_name} (поворот {angle}°, позиция {grid_x:.1f}, {grid_y:.1f})")
                                        break
                            if placed_successfully:
                                break
        
        if not placed_successfully:
            if verbose:
                st.warning(f"Не удалось разместить полигон из {file_name}")
            unplaced.append((polygon, file_name))
    
    if verbose:
        st.info(f"Упаковка завершена: {len(placed)} размещено, {len(unplaced)} не размещено")
    return placed, unplaced


def save_dxf_layout(placed_polygons: list[tuple[Polygon, float, float, float, str]], sheet_size: tuple[float, float], output_path: str):
    """Save the optimized layout as a DXF file."""
    doc = ezdxf.new()
    
    # Set DXF units to millimeters
    doc.header['$INSUNITS'] = 4  # 4 = millimeters
    doc.header['$LUNITS'] = 2    # 2 = decimal units
    
    msp = doc.modelspace()
    
    # Add sheet boundary as a rectangle
    sheet_width_mm = sheet_size[0] * 10
    sheet_height_mm = sheet_size[1] * 10
    sheet_corners = [(0, 0), (sheet_width_mm, 0), (sheet_width_mm, sheet_height_mm), (0, sheet_height_mm), (0, 0)]
    msp.add_lwpolyline(sheet_corners, dxfattribs={"layer": "SHEET_BOUNDARY", "color": 1})
    
    # Add placed polygons
    for polygon, _, _, _, file_name in placed_polygons:
        points = list(polygon.exterior.coords)[:-1]
        # Create layer name from file name (remove .dxf extension)
        layer_name = file_name.replace('.dxf', '').replace('..', '_')
        msp.add_lwpolyline(points, dxfattribs={"layer": layer_name})
    
    doc.saveas(output_path)
    return output_path


def plot_layout(placed_polygons: list[tuple[Polygon, float, float, float, str]], sheet_size: tuple[float, float]) -> BytesIO:
    """Plot the layout using matplotlib and return as BytesIO."""
    fig, ax = plt.subplots(figsize=(10, 8))
    
    # Convert sheet size from cm to mm for proper scaling
    sheet_width_mm = sheet_size[0] * 10
    sheet_height_mm = sheet_size[1] * 10
    
    ax.set_xlim(0, sheet_width_mm)
    ax.set_ylim(0, sheet_height_mm)
    ax.set_aspect("equal")
    
    # Draw sheet boundary
    sheet_boundary = plt.Rectangle((0, 0), sheet_width_mm, sheet_height_mm, 
                                 fill=False, edgecolor='black', linewidth=2, linestyle='--')
    ax.add_patch(sheet_boundary)
    
    # Use consistent colors for each file
    for polygon, _, _, angle, file_name in placed_polygons:
        x, y = polygon.exterior.xy
        color = get_color_for_file(file_name)
        ax.fill(x, y, alpha=0.7, color=color, edgecolor='black', linewidth=1, 
                label=f"{file_name} ({angle:.0f}°)")
        
        # Add file name at polygon centroid
        centroid = polygon.centroid
        ax.annotate(file_name.replace('.dxf', ''), (centroid.x, centroid.y), 
                   ha='center', va='center', fontsize=8, weight='bold')
    
    ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    ax.set_title(f"Раскрой на листе {sheet_size[0]} × {sheet_size[1]} см")
    ax.set_xlabel("Ширина (мм)")
    ax.set_ylabel("Высота (мм)")
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    buf = BytesIO()
    plt.savefig(buf, format="png", bbox_inches='tight', dpi=150)
    plt.close()
    buf.seek(0)
    return buf


def plot_single_polygon(polygon: Polygon, title: str, filename: str = None) -> BytesIO:
    """Plot a single polygon."""
    if not polygon:
        return None
    
    fig, ax = plt.subplots(figsize=(8, 6))
    
    # Get consistent color for this file
    if filename:
        color = get_color_for_file(filename)
    else:
        color = 'lightblue'
    
    # Plot the polygon
    x, y = polygon.exterior.xy
    ax.fill(x, y, alpha=0.7, color=color, edgecolor='darkblue', linewidth=2)
    
    # Add some padding around the polygon
    bounds = polygon.bounds
    padding = 0.1 * max(bounds[2] - bounds[0], bounds[3] - bounds[1])
    ax.set_xlim(bounds[0] - padding, bounds[2] + padding)
    ax.set_ylim(bounds[1] - padding, bounds[3] + padding)
    ax.set_aspect("equal")
    
    # Add polygon center point
    centroid = polygon.centroid
    ax.plot(centroid.x, centroid.y, 'ro', markersize=5, label='Центр')
    
    # Convert from DXF units (mm) to cm
    width_mm = bounds[2] - bounds[0]
    height_mm = bounds[3] - bounds[1]
    width_cm = width_mm / 10.0
    height_cm = height_mm / 10.0
    area_cm2 = polygon.area / 100.0  # mm² to cm²
    
    ax.set_title(f"{title}\nРеальные размеры: {width_cm:.1f} × {height_cm:.1f} см\nПлощадь: {area_cm2:.2f} см²")
    ax.set_xlabel("X координата (мм)")
    ax.set_ylabel("Y координата (мм)")
    ax.grid(True, alpha=0.3)
    ax.legend()
    
    plt.tight_layout()
    buf = BytesIO()
    plt.savefig(buf, format="png", bbox_inches='tight', dpi=150)
    plt.close()
    buf.seek(0)
    return buf


def plot_input_polygons(polygons_with_names: list[tuple[Polygon, str]]) -> dict[str, BytesIO]:
    """Create individual plots for each DXF file."""
    if not polygons_with_names:
        return {}
    
    plots = {}
    for polygon, file_name in polygons_with_names:
        plot_buf = plot_single_polygon(polygon, f"Файл: {file_name}", filename=file_name)
        plots[file_name] = plot_buf
    
    return plots


def scale_polygons_to_fit(polygons_with_names: list[tuple[Polygon, str]], sheet_size: tuple[float, float], verbose: bool = True) -> list[tuple[Polygon, str]]:
    """Scale polygons to fit better on the sheet if they are too large."""
    if not polygons_with_names:
        return polygons_with_names
    
    # Convert sheet size from cm to mm to match DXF units
    sheet_width_mm, sheet_height_mm = sheet_size[0] * 10, sheet_size[1] * 10
    scaled_polygons = []
    
    # First, find the overall scale factor needed (all in mm)
    max_width = max((poly.bounds[2] - poly.bounds[0]) for poly, _ in polygons_with_names)
    max_height = max((poly.bounds[3] - poly.bounds[1]) for poly, _ in polygons_with_names)
    
    # Calculate a global scale factor only if polygons are too large for the sheet
    # Only scale if polygons are larger than 90% of sheet size
    global_scale_x = (sheet_width_mm * 0.9) / max_width if max_width > sheet_width_mm * 0.9 else 1.0
    global_scale_y = (sheet_height_mm * 0.9) / max_height if max_height > sheet_height_mm * 0.9 else 1.0
    global_scale = min(global_scale_x, global_scale_y, 1.0)
    
    if global_scale < 1.0 and verbose:
        st.info(f"Применяем глобальный масштабный коэффициент {global_scale:.4f} ко всем полигонам")
    
    for polygon, name in polygons_with_names:
        bounds = polygon.bounds
        poly_width = bounds[2] - bounds[0]
        poly_height = bounds[3] - bounds[1]
        
        # Apply global scale first
        scale_factor = global_scale
        
        # Then check if individual scaling is needed (all in mm)
        # Only scale individual polygons if they don't fit on the sheet
        if poly_width > sheet_width_mm or poly_height > sheet_height_mm:
            scale_x = (sheet_width_mm * 0.95) / poly_width
            scale_y = (sheet_height_mm * 0.95) / poly_height
            individual_scale = min(scale_x, scale_y)
            scale_factor = min(scale_factor, individual_scale)
        
        if scale_factor < 0.99:  # Only scale if significant change
            # Scale the polygon around its centroid
            centroid = polygon.centroid
            scaled_polygon = affinity.scale(polygon, xfact=scale_factor, yfact=scale_factor, origin=(centroid.x, centroid.y))
            
            # Also translate to origin area to avoid negative coordinates
            scaled_bounds = scaled_polygon.bounds
            if scaled_bounds[0] < 0 or scaled_bounds[1] < 0:
                translate_x = -scaled_bounds[0] if scaled_bounds[0] < 0 else 0
                translate_y = -scaled_bounds[1] if scaled_bounds[1] < 0 else 0
                scaled_polygon = affinity.translate(scaled_polygon, xoff=translate_x, yoff=translate_y)
            
            if verbose:
                # Show dimensions in cm for user-friendly display
                original_width_cm = poly_width / 10.0
                original_height_cm = poly_height / 10.0
                new_width_cm = (scaled_polygon.bounds[2]-scaled_polygon.bounds[0]) / 10.0
                new_height_cm = (scaled_polygon.bounds[3]-scaled_polygon.bounds[1]) / 10.0
                st.info(f"Масштабирован {name}: {original_width_cm:.1f}x{original_height_cm:.1f} см → {new_width_cm:.1f}x{new_height_cm:.1f} см (коэффициент: {scale_factor:.4f})")
            scaled_polygons.append((scaled_polygon, name))
        else:
            scaled_polygons.append((polygon, name))
    
    return scaled_polygons