"""Helper functions for EVA mat nesting optimization."""

# Version for cache busting
__version__ = "1.2.0"

# Force module reload for Streamlit Cloud
import importlib

import numpy as np
from shapely.geometry import Polygon, MultiPolygon
from shapely import affinity
from shapely.ops import unary_union
import ezdxf
import matplotlib.pyplot as plt
from io import BytesIO
import streamlit as st
import tempfile
import os
import hashlib
import logging

# Настройка логирования
logger = logging.getLogger(__name__)


# Export list for explicit importing
__all__ = [
    'get_color_for_file',
    'parse_dxf_complete', 
    'convert_entity_to_polygon_improved',
    'save_dxf_layout_complete',
    'rotate_polygon',
    'translate_polygon',
    'place_polygon_at_origin',
    'check_collision',
    'bin_packing_with_inventory',
    'calculate_usage_percent',
    'bin_packing',
    'save_dxf_layout',
    'plot_layout',
    'plot_single_polygon',
    'plot_input_polygons',
    'scale_polygons_to_fit'
]


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


def parse_dxf_complete(file, verbose=True):
    """Parse DXF file preserving all elements without loss."""
    
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
    
    result = {
        'polygons': [],           # List of Shapely polygons for layout optimization
        'original_entities': [],  # All original entities for reconstruction
        'bounds': None,          # Overall bounds
        'layers': set(),         # All layers
        'doc_header': {}  # Skip header for now to avoid issues
    }
    
    total_entities = 0
    entity_types = {}
    
    # Store all original entities
    for entity in msp:
        total_entities += 1
        entity_type = entity.dxftype()
        entity_types[entity_type] = entity_types.get(entity_type, 0) + 1
        
        # Store original entity with all attributes
        entity_data = {
            'type': entity_type,
            'entity': entity,  # Store reference to original entity
            'layer': getattr(entity.dxf, 'layer', '0'),
            'color': getattr(entity.dxf, 'color', 256),
            'dxf_attribs': entity.dxfattribs()
        }
        result['original_entities'].append(entity_data)
        result['layers'].add(entity_data['layer'])
        
        # Try to convert to polygon for layout purposes
        try:
            polygon = convert_entity_to_polygon_improved(entity)
            if polygon and polygon.is_valid and polygon.area > 0.1:  # Minimum area threshold
                result['polygons'].append(polygon)
        except Exception as e:
            if verbose:
                st.warning(f"⚠️ Не удалось конвертировать {entity_type} в полигон: {e}")
    
    if verbose:
        st.info(f"📊 Парсинг завершен:")
        st.info(f"   • Всего элементов: {total_entities}")
        st.info(f"   • Типы: {entity_types}")
        st.info(f"   • Полигонов для оптимизации: {len(result['polygons'])}")
        st.info(f"   • Сохранено исходных элементов: {len(result['original_entities'])}")
    
    # Calculate overall bounds
    if result['polygons']:
        all_bounds = [p.bounds for p in result['polygons']]
        min_x = min(b[0] for b in all_bounds)
        min_y = min(b[1] for b in all_bounds)
        max_x = max(b[2] for b in all_bounds)
        max_y = max(b[3] for b in all_bounds)
        result['bounds'] = (min_x, min_y, max_x, max_y)
        
        # Create combined polygon for layout optimization (without convex_hull)
        if len(result['polygons']) == 1:
            result['combined_polygon'] = result['polygons'][0]
        else:
            # Use unary_union but don't simplify to convex_hull
            combined = unary_union(result['polygons'])
            if isinstance(combined, MultiPolygon):
                # Keep as MultiPolygon or take the largest polygon
                largest_polygon = max(combined.geoms, key=lambda p: p.area)
                result['combined_polygon'] = largest_polygon
                if verbose:
                    st.info(f"   • Взят наибольший полигон из {len(combined.geoms)} (без упрощения)")
            else:
                result['combined_polygon'] = combined
    else:
        if verbose:
            st.warning("⚠️ Не найдено полигонов для оптимизации")
        result['combined_polygon'] = None
    
    # Store original data separately since Shapely polygons don't allow attribute assignment
    # We'll pass this data through function parameters instead
    
    return result


def convert_entity_to_polygon_improved(entity):
    """Improved entity to polygon conversion with better SPLINE handling."""
    entity_type = entity.dxftype()
    
    try:
        if entity_type == "LWPOLYLINE":
            points = [(p[0], p[1]) for p in entity.get_points()]
            if len(points) >= 3:
                return Polygon(points)
                
        elif entity_type == "POLYLINE":
            points = [(vertex.dxf.location[0], vertex.dxf.location[1]) for vertex in entity.vertices]
            if len(points) >= 3:
                return Polygon(points)
                
        elif entity_type == "SPLINE":
            # Improved SPLINE handling
            try:
                # Try to get more points for better accuracy
                sampled_points = []
                construction_tool = entity.construction_tool()
                # Sample more points (100 instead of 50) for better accuracy
                for t in np.linspace(0, 1, 100):
                    point = construction_tool.point(t)
                    sampled_points.append((point.x, point.y))
                
                if len(sampled_points) >= 3:
                    return Polygon(sampled_points)
            except Exception:
                # Fallback: use control points or fit points
                try:
                    if hasattr(entity, 'control_points') and entity.control_points:
                        control_points = [(cp[0], cp[1]) for cp in entity.control_points]
                        if len(control_points) >= 3:
                            return Polygon(control_points)
                    elif hasattr(entity, 'fit_points') and entity.fit_points:
                        fit_points = [(fp[0], fp[1]) for fp in entity.fit_points]
                        if len(fit_points) >= 3:
                            return Polygon(fit_points)
                except Exception:
                    pass
                    
        elif entity_type == "ELLIPSE":
            # Improved ELLIPSE with more points
            try:
                sampled_points = []
                for angle in np.linspace(0, 2*np.pi, 72):  # 72 points for smoother curve
                    point = entity.construction_tool().point(angle)
                    sampled_points.append((point.x, point.y))
                if len(sampled_points) >= 3:
                    return Polygon(sampled_points)
            except Exception:
                pass
                
        elif entity_type == "CIRCLE":
            center = entity.dxf.center
            radius = entity.dxf.radius
            points = []
            for angle in np.linspace(0, 2*np.pi, 36):  # 36 points for circle
                x = center[0] + radius * np.cos(angle)
                y = center[1] + radius * np.sin(angle)
                points.append((x, y))
            return Polygon(points)
            
        elif entity_type == "ARC":
            center = entity.dxf.center
            radius = entity.dxf.radius
            start_angle = np.radians(entity.dxf.start_angle)
            end_angle = np.radians(entity.dxf.end_angle)
            
            # Create arc as polygon (sector)
            points = [center[:2]]  # Start from center
            angles = np.linspace(start_angle, end_angle, 20)
            for angle in angles:
                x = center[0] + radius * np.cos(angle)
                y = center[1] + radius * np.sin(angle)
                points.append((x, y))
            points.append(center[:2])  # Back to center
            
            if len(points) >= 3:
                return Polygon(points)
                
    except Exception as e:
        print(f"⚠️ Ошибка конвертации {entity_type}: {e}")
        
    return None


def save_dxf_layout_complete(placed_elements, sheet_size, output_path, original_dxf_data_map=None):
    """Save layout preserving all original elements from source DXF files.
    
    Args:
        placed_elements: List of placed polygon tuples
        sheet_size: Sheet dimensions
        output_path: Output file path
        original_dxf_data_map: Dictionary mapping filenames to original DXF data
    """
    
    # Create new DXF document
    doc = ezdxf.new('R2010')  # Use R2010 for better compatibility
    
    # Set DXF units to millimeters
    doc.header['$INSUNITS'] = 4  # 4 = millimeters
    doc.header['$LUNITS'] = 2    # 2 = decimal units
    
    msp = doc.modelspace()
    
    # Add sheet boundary
    sheet_width_mm = sheet_size[0] * 10
    sheet_height_mm = sheet_size[1] * 10
    sheet_corners = [(0, 0), (sheet_width_mm, 0), (sheet_width_mm, sheet_height_mm), (0, sheet_height_mm), (0, 0)]
    msp.add_lwpolyline(sheet_corners, dxfattribs={"layer": "SHEET_BOUNDARY", "color": 1})
    
    # Process each placed element
    for placed_element in placed_elements:
        if len(placed_element) >= 6:  # New format with color
            transformed_polygon, x_offset, y_offset, rotation_angle, file_name, color = placed_element[:6]
        else:  # Old format without color
            transformed_polygon, x_offset, y_offset, rotation_angle, file_name = placed_element[:5]
            color = 'серый'
        
        # If we have original DXF data for this file, use it
        if original_dxf_data_map and file_name in original_dxf_data_map:
            # Reconstruct from original elements
            original_data = original_dxf_data_map[file_name]
            
            for entity_data in original_data['original_entities']:
                try:
                    # Clone the original entity
                    new_entity = entity_data['entity'].copy()
                    
                    # Calculate the transformation needed to match the final polygon position
                    
                    if original_data['combined_polygon']:
                        original_polygon = original_data['combined_polygon']
                        
                        # The transformed_polygon represents where the polygon ended up
                        # We need to calculate what transformation gets us from original to final
                        
                        # Step 1: Move to origin from original position
                        original_bounds = original_polygon.bounds
                        origin_offset_x = -original_bounds[0]
                        origin_offset_y = -original_bounds[1]
                        new_entity.transform(ezdxf.math.Matrix44.translate(origin_offset_x, origin_offset_y, 0))
                        
                        # Calculate the polygon after moving to origin (needed for both rotation and final translation)
                        origin_placed_polygon = translate_polygon(original_polygon, origin_offset_x, origin_offset_y)
                        
                        # Step 2: Apply rotation if needed
                        if rotation_angle != 0:
                            # Get the centroid after moving to origin
                            origin_centroid = origin_placed_polygon.centroid
                            
                            # Rotate around this centroid
                            new_entity.transform(ezdxf.math.Matrix44.chain(
                                ezdxf.math.Matrix44.translate(-origin_centroid.x, -origin_centroid.y, 0),
                                ezdxf.math.Matrix44.z_rotate(np.radians(rotation_angle)),
                                ezdxf.math.Matrix44.translate(origin_centroid.x, origin_centroid.y, 0)
                            ))
                        
                        # Step 3: Now calculate where we need to move to match the final position
                        # After rotation, what would be the polygon's position?
                        if rotation_angle != 0:
                            intermediate_polygon = rotate_polygon(origin_placed_polygon, rotation_angle)
                        else:
                            intermediate_polygon = origin_placed_polygon
                        
                        # Calculate the final translation needed
                        intermediate_bounds = intermediate_polygon.bounds
                        final_bounds = transformed_polygon.bounds
                        
                        final_translation_x = final_bounds[0] - intermediate_bounds[0]
                        final_translation_y = final_bounds[1] - intermediate_bounds[1]
                        
                        # Apply this final translation
                        new_entity.transform(ezdxf.math.Matrix44.translate(final_translation_x, final_translation_y, 0))
                    
                    # Update layer name to include file name
                    base_layer = entity_data['layer']
                    new_layer = f"{file_name.replace('.dxf', '').replace('..', '_')}_{base_layer}"
                    new_entity.dxf.layer = new_layer
                    
                    # Add to modelspace
                    msp.add_entity(new_entity)
                    
                except Exception as e:
                    st.warning(f"⚠️ Ошибка добавления элемента {entity_data['type']}: {e}")
                    # Fallback: add as simple polyline
                    if hasattr(transformed_polygon, 'exterior'):
                        points = list(transformed_polygon.exterior.coords)[:-1]
                        layer_name = file_name.replace('.dxf', '').replace('..', '_')
                        msp.add_lwpolyline(points, dxfattribs={"layer": layer_name})
        else:
            # Fallback: save as simple polyline (current method)
            if hasattr(transformed_polygon, 'exterior'):
                points = list(transformed_polygon.exterior.coords)[:-1]
                layer_name = file_name.replace('.dxf', '').replace('..', '_')
                msp.add_lwpolyline(points, dxfattribs={"layer": layer_name})
                
                # Add interior holes if any
                for interior in transformed_polygon.interiors:
                    hole_points = list(interior.coords)[:-1]
                    msp.add_lwpolyline(hole_points, dxfattribs={"layer": f"{layer_name}_HOLE"})
    
    # Save the document
    doc.saveas(output_path)
    #st.success(f"💾 Сохранен улучшенный выходной DXF файл: {output_path}")


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


def bin_packing(polygons: list[tuple], sheet_size: tuple[float, float], max_attempts: int = 1000, verbose: bool = True) -> tuple[list[tuple], list[tuple]]:
    """Optimize placement of complex polygons on a sheet."""
    # Convert sheet size from cm to mm to match DXF polygon units
    sheet_width_mm, sheet_height_mm = sheet_size[0] * 10, sheet_size[1] * 10
    sheet = Polygon([(0, 0), (sheet_width_mm, 0), (sheet_width_mm, sheet_height_mm), (0, sheet_height_mm)])
    placed = []
    unplaced = []
    
    if verbose:
        st.info(f"Начинаем упаковку {len(polygons)} полигонов на листе {sheet_size[0]}x{sheet_size[1]} см")
    
    for i, polygon_tuple in enumerate(polygons):
        logger.debug(f"bin_packing: входящий tuple {i}: длина={len(polygon_tuple)}, элементы={polygon_tuple}")
        
        if len(polygon_tuple) >= 4:  # Extended format with color and order_id
            polygon, file_name, color, order_id = polygon_tuple[:4]
        elif len(polygon_tuple) >= 3:  # Format with color
            polygon, file_name, color = polygon_tuple[:3]
            order_id = 'unknown'  
        else:  # Old format without color
            polygon, file_name = polygon_tuple[:2]
            color = 'серый'
            order_id = 'unknown'
        
        logger.debug(f"bin_packing: извлечено file_name='{file_name}' (тип: {type(file_name)}), order_id='{order_id}')")
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
            unplaced.append((polygon, file_name, color, order_id))
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
                placed.append((origin_polygon, 0, 0, 0, file_name, color, order_id))
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
                            placed.append((translated, grid_x - simple_bounds[0], grid_y - simple_bounds[1], 0, file_name, color, order_id))
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
                            placed.append((origin_rotated, 0, 0, angle, file_name, color, order_id))
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
                                        placed.append((translated, grid_x - rotated_bounds[0], grid_y - rotated_bounds[1], angle, file_name, color, order_id))
                                        placed_successfully = True
                                        if verbose:
                                            st.success(f"Успешно размещен полигон из {file_name} (поворот {angle}°, позиция {grid_x:.1f}, {grid_y:.1f})")
                                        break
                            if placed_successfully:
                                break
        
        if not placed_successfully:
            if verbose:
                st.warning(f"Не удалось разместить полигон из {file_name}")
            unplaced.append((polygon, file_name, color, order_id))
    
    if verbose:
        st.info(f"Упаковка завершена: {len(placed)} размещено, {len(unplaced)} не размещено")
    return placed, unplaced


def bin_packing_with_inventory(polygons: list[tuple], available_sheets: list[dict], verbose: bool = True, max_sheets_per_order: int = None) -> tuple[list[dict], list[tuple]]:
    """Optimize placement of polygons on available sheets with inventory tracking."""
    logger.info(f"=== НАЧАЛО bin_packing_with_inventory ===")
    logger.info(f"Входные параметры: {len(polygons)} полигонов, {len(available_sheets)} типов листов, max_sheets_per_order={max_sheets_per_order}")
    
    placed_layouts = []
    all_unplaced = []
    sheet_inventory = [sheet.copy() for sheet in available_sheets]  # Copy to avoid modifying original
    
    if verbose:
        total_available = sum(sheet['count'] - sheet['used'] for sheet in sheet_inventory)
        st.info(f"Начинаем размещение {len(polygons)} полигонов на {total_available} доступных листах")
        if max_sheets_per_order:
            st.info(f"Ограничение: максимум {max_sheets_per_order} листов на заказ")
    
    # Group polygons by order_id
    logger.info("Группировка полигонов по order_id...")
    order_groups = {}
    for polygon_tuple in polygons:
        if len(polygon_tuple) >= 4:  # Extended format with color and order_id
            polygon, name, color, order_id = polygon_tuple[:4]
        elif len(polygon_tuple) >= 3:  # Format with color
            polygon, name, color = polygon_tuple[:3]
            order_id = 'unknown'
        else:  # Old format without color
            polygon, name = polygon_tuple[:2]
            color = 'серый'
            order_id = 'unknown'
        
        if order_id not in order_groups:
            order_groups[order_id] = []
            logger.debug(f"Создана новая группа для заказа: {order_id}")
        order_groups[order_id].append(polygon_tuple)
    
    logger.info(f"Группировка завершена: {len(order_groups)} уникальных заказов")
    for order_id, group in order_groups.items():
        logger.info(f"  • Заказ {order_id}: {len(group)} файлов")
    
    if verbose:
        st.info(f"Найдено {len(order_groups)} уникальных заказов для размещения:")
        for order_id, group in order_groups.items():
            st.info(f"  • Заказ {order_id}: {len(group)} файлов")
            # Show filenames for debugging
            for polygon_tuple in group:
                filename = polygon_tuple[1] if len(polygon_tuple) > 1 else 'unknown'
                st.write(f"    - {filename}")
    
    sheet_counter = 0
    
    # Track sheets used per order for constraint checking
    order_sheet_usage = {order_id: 0 for order_id in order_groups.keys()}
    
    logger.info(f"Используем упрощенный эффективный алгоритм: {len(order_groups)} заказов")
    
    # Process orders one by one, but allow filling sheets with multiple orders
    remaining_orders = dict(order_groups)  # Copy to modify
    max_iterations = len(remaining_orders) * 10  # Safety limit
    iteration_count = 0
    
    while remaining_orders and any(sheet['count'] - sheet['used'] > 0 for sheet in sheet_inventory):
        iteration_count += 1
        logger.info(f"--- ИТЕРАЦИЯ {iteration_count} ---")
        logger.info(f"Остается заказов: {len(remaining_orders)}")
        for order_id, polygons in remaining_orders.items():
            logger.info(f"  {order_id}: {len(polygons)} полигонов")
        
        if iteration_count > max_iterations:
            logger.error(f"Превышен лимит итераций ({max_iterations}), прерываем выполнение")
            break
            
        placed_on_current_sheet = False
        
        # Try each available sheet type
        for sheet_type in sheet_inventory:
            if sheet_type['count'] - sheet_type['used'] <= 0:
                continue  # No more sheets of this type
            
            sheet_size = (sheet_type['width'], sheet_type['height'])
            sheet_color = sheet_type.get('color', 'серый')
            
            # Collect polygons from orders that can fit on this sheet
            compatible_polygons = []
            orders_to_try = []
            
            for order_id, order_polygons in remaining_orders.items():
                # Check if this order can still use more sheets
                if max_sheets_per_order is None or order_id == 'additional' or order_sheet_usage[order_id] < max_sheets_per_order:
                    # Filter polygons by color
                    color_matched_polygons = []
                    for polygon_tuple in order_polygons:
                        if len(polygon_tuple) >= 3:
                            color = polygon_tuple[2]
                        else:
                            color = 'серый'
                        
                        if color == sheet_color:
                            color_matched_polygons.append(polygon_tuple)
                    
                    if color_matched_polygons:
                        compatible_polygons.extend(color_matched_polygons)
                        orders_to_try.append(order_id)
            
            if not compatible_polygons:
                continue  # No compatible polygons for this sheet color
            
            sheet_counter += 1
            
            if verbose:
                st.info(f"  Лист #{sheet_counter}: {sheet_type['name']} ({sheet_size[0]}x{sheet_size[1]} см, цвет: {sheet_color})")
                st.info(f"  Совместимых полигонов: {len(compatible_polygons)} из заказов: {orders_to_try}")
            
            logger.info(f"Обрабатываем лист #{sheet_counter}: {len(compatible_polygons)} совместимых полигонов из заказов {orders_to_try}")
            
            # Debug logging before bin_packing call
            logger.debug(f"=== ПОЛИГОНЫ ПЕРЕД bin_packing ===")
            for idx, poly_tuple in enumerate(compatible_polygons):
                logger.debug(f"  [{idx}] длина={len(poly_tuple)}, элементы={poly_tuple}")
                if len(poly_tuple) > 1:
                    logger.debug(f"      имя файла: '{poly_tuple[1]}' (тип: {type(poly_tuple[1])})")
            
            # Try to place compatible polygons on this sheet
            placed, remaining_from_sheet = bin_packing(compatible_polygons, sheet_size, verbose=verbose)
            
            # Debug logging after bin_packing call
            logger.debug(f"=== ПОЛИГОНЫ ПОСЛЕ bin_packing ===")
            logger.debug(f"  Размещено: {len(placed)} полигонов")
            for idx, poly_tuple in enumerate(placed):
                logger.debug(f"  [{idx}] длина={len(poly_tuple)}, элементы={poly_tuple}")
                if len(poly_tuple) >= 5:
                    logger.debug(f"      имя файла: '{poly_tuple[4]}' (тип: {type(poly_tuple[4])})")  # file_name at index 4
                elif len(poly_tuple) > 1:
                    logger.debug(f"      элемент [1]: '{poly_tuple[1]}' (тип: {type(poly_tuple[1])})")  # what was mistaken for filename
            
            if placed:  # If we managed to place something
                sheet_type['used'] += 1
                
                # Track which orders are represented on this sheet
                orders_on_sheet = set()
                placed_polygon_names = set()
                
                for polygon_tuple in placed:
                    # bin_packing returns: (polygon, x_offset, y_offset, angle, file_name, color, order_id)
                    if len(polygon_tuple) >= 5:
                        filename = polygon_tuple[4]  # file_name is at index 4
                    else:
                        filename = 'unknown'  # fallback
                    
                    placed_polygon_names.add(filename)
                    
                    # Find which order this polygon belongs to
                    found_order = False
                    for order_id, order_polygons in remaining_orders.items():
                        for orig_tuple in order_polygons:
                            if len(orig_tuple) > 1 and orig_tuple[1] == filename:
                                orders_on_sheet.add(order_id)
                                logger.debug(f"    Полигон {filename} принадлежит заказу {order_id}")
                                found_order = True
                                break
                        if found_order:
                            break
                    
                    if not found_order:
                        logger.warning(f"    Не найден заказ для полигона {filename}")
                
                logger.info(f"УСПЕХ: Лист #{sheet_counter} содержит заказы: {orders_on_sheet}")
                
                # Update order sheet usage
                for order_id in orders_on_sheet:
                    if order_id in order_sheet_usage:
                        order_sheet_usage[order_id] += 1
                        logger.info(f"  Заказ {order_id}: теперь использует {order_sheet_usage[order_id]} листов")
                
                placed_layouts.append({
                    'sheet_number': sheet_counter,
                    'sheet_type': sheet_type['name'],
                    'sheet_size': sheet_size,
                    'placed_polygons': placed,
                    'usage_percent': calculate_usage_percent(placed, sheet_size),
                    'orders_on_sheet': list(orders_on_sheet)
                })
                
                # Remove placed polygons from remaining orders
                # We need to match polygons by both filename AND order_id
                placed_polygon_map = {}  # Maps (filename, order_id) -> True
                for polygon_tuple in placed:
                    if len(polygon_tuple) >= 5:
                        filename = polygon_tuple[4]  # file_name is at index 4
                        if len(polygon_tuple) >= 7:
                            order_id = polygon_tuple[6]  # order_id is at index 6
                            placed_polygon_map[(filename, order_id)] = True
                            logger.debug(f"  Размещен полигон: файл='{filename}', заказ='{order_id}'")
                
                total_removed = 0
                for order_id in list(remaining_orders.keys()):
                    original_count = len(remaining_orders[order_id])
                    # Only remove polygons that were actually placed from this specific order
                    remaining_orders[order_id] = [
                        p for p in remaining_orders[order_id] 
                        if len(p) < 2 or (p[1], order_id) not in placed_polygon_map
                    ]
                    removed_count = original_count - len(remaining_orders[order_id])
                    total_removed += removed_count
                    
                    if removed_count > 0:
                        logger.info(f"  Из заказа {order_id} удалено {removed_count} размещенных полигонов")
                    
                    # Remove empty orders
                    if not remaining_orders[order_id]:
                        logger.info(f"  Заказ {order_id} полностью размещен")
                        del remaining_orders[order_id]
                
                logger.info(f"Общее количество удаленных полигонов: {total_removed}")
                logger.info(f"Оставшиеся заказы: {list(remaining_orders.keys())}")
                for order_id, polygons in remaining_orders.items():
                    logger.info(f"  {order_id}: {len(polygons)} полигонов")
                
                placed_on_current_sheet = True
                
                if verbose:
                    st.success(f"  ✅ Размещено {len(placed)} объектов на листе {sheet_type['name']}")
                    st.info(f"  📊 Заказы на листе: {', '.join(orders_on_sheet)}")
                
                break  # Move to next iteration with remaining orders
        
        if not placed_on_current_sheet:
            # No sheet type could accommodate any remaining polygons
            logger.warning(f"Не удалось разместить оставшиеся заказы: {list(remaining_orders.keys())}")
            break
    
    # Check order constraints after placement
    violated_orders = []
    for order_id, sheets_used in order_sheet_usage.items():
        if max_sheets_per_order and order_id != 'additional' and sheets_used > max_sheets_per_order:
            violated_orders.append((order_id, sheets_used))
            logger.error(f"НАРУШЕНИЕ ОГРАНИЧЕНИЙ: Заказ {order_id} использует {sheets_used} листов (лимит: {max_sheets_per_order})")
    
    if violated_orders:
        error_msg = "❌ Нарушение ограничений заказов:\n" + "\n".join([
            f"Заказ {order_id}: {sheets_used} листов (лимит: {max_sheets_per_order})" 
            for order_id, sheets_used in violated_orders
        ])
        if verbose:
            st.error(error_msg)
        raise ValueError(error_msg)
    
    # Add any completely unplaced polygons to the unplaced list
    for order_id, remaining_polygons in remaining_orders.items():
        all_unplaced.extend(remaining_polygons)
    
    
    logger.info(f"=== ОКОНЧАНИЕ bin_packing_with_inventory ===")
    logger.info(f"ИТОГОВЫЙ РЕЗУЛЬТАТ: {len(placed_layouts)} листов использовано, {len(all_unplaced)} объектов не размещено")
    
    logger.info("Финальное распределение по заказам:")
    for order_id, sheets_used in order_sheet_usage.items():
        logger.info(f"  • Заказ {order_id}: {sheets_used} листов")
    
    if verbose:
        st.info(f"Размещение завершено: {len(placed_layouts)} листов использовано, {len(all_unplaced)} объектов не размещено")
        
        # Show summary by orders using the tracked usage
        if order_sheet_usage:
            st.success("✅ Распределение по заказам:")
            for order_id, sheet_count in order_sheet_usage.items():
                if order_id != 'unknown':  # Only show real orders
                    status = "✅" if sheet_count <= (max_sheets_per_order or float('inf')) else "❌"
                    st.info(f"  {status} Заказ {order_id}: {sheet_count} листов")
    
    return placed_layouts, all_unplaced


def calculate_usage_percent(placed_polygons: list[tuple], sheet_size: tuple[float, float]) -> float:
    """Calculate material usage percentage for a sheet."""
    used_area_mm2 = sum(placed_tuple[0].area for placed_tuple in placed_polygons)
    sheet_area_mm2 = (sheet_size[0] * 10) * (sheet_size[1] * 10)
    return (used_area_mm2 / sheet_area_mm2) * 100


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
    for placed_tuple in placed_polygons:
        if len(placed_tuple) >= 6:  # New format with color
            polygon, _, _, _, file_name, color = placed_tuple[:6]
        else:  # Old format without color
            polygon, _, _, _, file_name = placed_tuple[:5]
            color = 'серый'
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
    for placed_tuple in placed_polygons:
        if len(placed_tuple) >= 6:  # New format with color
            polygon, _, _, angle, file_name, color = placed_tuple[:6]
        else:  # Old format without color
            polygon, _, _, angle, file_name = placed_tuple[:5]
            color = 'серый'
        x, y = polygon.exterior.xy
        # Use file-based color for visualization consistency
        display_color = get_color_for_file(file_name)
        ax.fill(x, y, alpha=0.7, color=display_color, edgecolor='black', linewidth=1, 
                label=f"{file_name} ({angle:.0f}°) - {color}")
        
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
    for polygon_tuple in polygons_with_names:
        if len(polygon_tuple) >= 3:  # New format with color
            polygon, file_name, color = polygon_tuple[:3]
        else:  # Old format without color
            polygon, file_name = polygon_tuple[:2]
            color = 'серый'
        
        plot_buf = plot_single_polygon(polygon, f"Файл: {file_name} (цвет: {color})", filename=file_name)
        plots[file_name] = plot_buf
    
    return plots


def scale_polygons_to_fit(polygons_with_names: list[tuple], sheet_size: tuple[float, float], verbose: bool = True) -> list[tuple]:
    """Scale polygons to fit better on the sheet if they are too large."""
    if not polygons_with_names:
        return polygons_with_names
    
    # Convert sheet size from cm to mm to match DXF units
    sheet_width_mm, sheet_height_mm = sheet_size[0] * 10, sheet_size[1] * 10
    scaled_polygons = []
    
    # First, find the overall scale factor needed (all in mm)
    max_width = max((poly_tuple[0].bounds[2] - poly_tuple[0].bounds[0]) for poly_tuple in polygons_with_names)
    max_height = max((poly_tuple[0].bounds[3] - poly_tuple[0].bounds[1]) for poly_tuple in polygons_with_names)
    
    # Calculate a global scale factor only if polygons are too large for the sheet
    # Only scale if polygons are larger than 90% of sheet size
    global_scale_x = (sheet_width_mm * 0.9) / max_width if max_width > sheet_width_mm * 0.9 else 1.0
    global_scale_y = (sheet_height_mm * 0.9) / max_height if max_height > sheet_height_mm * 0.9 else 1.0
    global_scale = min(global_scale_x, global_scale_y, 1.0)
    
    if global_scale < 1.0 and verbose:
        st.info(f"Применяем глобальный масштабный коэффициент {global_scale:.4f} ко всем полигонам")
    
    for polygon_tuple in polygons_with_names:
        if len(polygon_tuple) >= 4:  # Extended format with color and order_id
            polygon, name, color, order_id = polygon_tuple[:4]
        elif len(polygon_tuple) >= 3:  # Format with color
            polygon, name, color = polygon_tuple[:3]
            order_id = 'unknown'
        else:  # Old format without color
            polygon, name = polygon_tuple[:2]
            color = 'серый'
            order_id = 'unknown'
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
            scaled_polygons.append((scaled_polygon, name, color, order_id))
        else:
            scaled_polygons.append((polygon, name, color, order_id))
    
    return scaled_polygons


# Verification that all functions are properly defined
def _verify_functions():
    """Verify that all required functions are defined in the module."""
    required_functions = [
        'get_color_for_file',
        'parse_dxf', 
        'rotate_polygon',
        'translate_polygon',
        'place_polygon_at_origin',
        'check_collision',
        'bin_packing',
        'bin_packing_with_inventory',
        'calculate_usage_percent',
        'save_dxf_layout',
        'plot_layout',
        'plot_single_polygon',
        'plot_input_polygons',
        'scale_polygons_to_fit'
    ]
    
    import sys
    current_module = sys.modules[__name__]
    
    missing_functions = []
    for func_name in required_functions:
        if not hasattr(current_module, func_name):
            missing_functions.append(func_name)
    
    if missing_functions:
        raise ImportError(f"Missing functions in layout_optimizer: {missing_functions}")
    
    return True

# Run verification
_verify_functions()