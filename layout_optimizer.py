"""Helper functions for EVA mat nesting optimization."""

# Version for cache busting
__version__ = "1.5.0"

# Force module reload for Streamlit Cloud

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
import math

# Настройка логирования
logger = logging.getLogger(__name__)


# Export list for explicit importing
__all__ = [
    "get_color_for_file",
    "parse_dxf_complete",
    "convert_entity_to_polygon_improved",
    "save_dxf_layout_complete",
    "rotate_polygon",
    "translate_polygon",
    "place_polygon_at_origin",
    "check_collision",
    "bin_packing_with_inventory",
    "calculate_usage_percent",
    "bin_packing",
    "save_dxf_layout",
    "plot_layout",
    "plot_single_polygon",
    "plot_input_polygons",
    "scale_polygons_to_fit",
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

    if hasattr(file, "read"):
        # If it's a file-like object (BytesIO), write to temp file first
        with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as tmp_file:
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
        "polygons": [],  # List of Shapely polygons for layout optimization
        "original_entities": [],  # All original entities for reconstruction
        "bounds": None,  # Overall bounds
        "layers": set(),  # All layers
        "doc_header": {},  # Skip header for now to avoid issues
        "real_spline_bounds": None,  # Real bounds of SPLINE elements for accurate transformation
    }

    total_entities = 0
    entity_types = {}

    # Store all original entities
    for entity in msp:
        total_entities += 1
        entity_type = entity.dxftype()
        entity_types[entity_type] = entity_types.get(entity_type, 0) + 1

        # Store original entity with all attributes, but SKIP artifact layers
        layer_name = getattr(entity.dxf, "layer", "0")

        # Skip artifact layers and unwanted entity types
        if any(
            artifact in layer_name
            for artifact in [
                "POLYGON_",
                "SHEET_BOUNDARY", 
                "_black",
                "_gray",
                "_white",
                ".dxf",
            ]
        ):
            continue  # Skip this entity - it's an artifact
            
        # Skip IMAGE entities - they are artifacts from previous processing
        if entity_type == "IMAGE":
            continue
            
        # Skip HATCH entities - they are fill patterns that duplicate geometry
        if entity_type == "HATCH":
            continue  # Skip hatches - they cause duplication with contours

        entity_data = {
            "type": entity_type,
            "entity": entity,  # Store reference to original entity
            "layer": layer_name,
            "color": getattr(entity.dxf, "color", 256),
            "dxf_attribs": entity.dxfattribs(),
        }
        result["original_entities"].append(entity_data)
        result["layers"].add(layer_name)

        # Try to convert to polygon for layout purposes
        try:
            polygon = convert_entity_to_polygon_improved(entity)
            if (
                polygon and polygon.is_valid and polygon.area > 0.1
            ):  # Minimum area threshold
                result["polygons"].append(polygon)
        except Exception as e:
            if verbose:
                st.warning(f"⚠️ Не удалось конвертировать {entity_type} в полигон: {e}")

    if verbose:
        st.info("📊 Парсинг завершен:")
        st.info(f"   • Всего элементов: {total_entities}")
        st.info(f"   • Типы: {entity_types}")
        st.info(f"   • Полигонов для оптимизации: {len(result['polygons'])}")
        st.info(
            f"   • Сохранено исходных элементов: {len(result['original_entities'])}"
        )

    # Calculate overall bounds
    if result["polygons"]:
        all_bounds = [p.bounds for p in result["polygons"]]
        min_x = min(b[0] for b in all_bounds)
        min_y = min(b[1] for b in all_bounds)
        max_x = max(b[2] for b in all_bounds)
        max_y = max(b[3] for b in all_bounds)
        result["bounds"] = (min_x, min_y, max_x, max_y)

        # Create combined polygon for layout optimization (without convex_hull)
        if len(result["polygons"]) == 1:
            result["combined_polygon"] = result["polygons"][0]
        else:
            # Use unary_union but don't simplify to convex_hull
            combined = unary_union(result["polygons"])
            if isinstance(combined, MultiPolygon):
                # Keep as MultiPolygon or take the largest polygon
                largest_polygon = max(combined.geoms, key=lambda p: p.area)
                result["combined_polygon"] = largest_polygon
                if verbose:
                    st.info(
                        f"   • Взят наибольший полигон из {len(combined.geoms)} (без упрощения)"
                    )
            else:
                result["combined_polygon"] = combined
    else:
        if verbose:
            st.warning("⚠️ Не найдено полигонов для оптимизации")
        result["combined_polygon"] = None

    # Calculate real bounds of SPLINE elements for accurate transformation
    spline_entities = [
        entity_data
        for entity_data in result["original_entities"]
        if entity_data["type"] == "SPLINE"
    ]
    if spline_entities:
        all_spline_xs = []
        all_spline_ys = []

        for entity_data in spline_entities:
            entity = entity_data["entity"]
            try:
                control_points = entity.control_points
                if control_points:
                    for cp in control_points:
                        if hasattr(cp, "x") and hasattr(cp, "y"):
                            all_spline_xs.append(cp.x)
                            all_spline_ys.append(cp.y)
                        elif len(cp) >= 2:
                            all_spline_xs.append(float(cp[0]))
                            all_spline_ys.append(float(cp[1]))
            except:
                continue

        if all_spline_xs and all_spline_ys:
            result["real_spline_bounds"] = (
                min(all_spline_xs),
                min(all_spline_ys),
                max(all_spline_xs),
                max(all_spline_ys),
            )
            if verbose:
                st.info(
                    f"✅ Сохранены реальные bounds SPLINE элементов: {result['real_spline_bounds']}"
                )

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
            points = [
                (vertex.dxf.location[0], vertex.dxf.location[1])
                for vertex in entity.vertices
            ]
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
                    if hasattr(entity, "control_points") and entity.control_points:
                        control_points = [
                            (cp[0], cp[1]) for cp in entity.control_points
                        ]
                        if len(control_points) >= 3:
                            return Polygon(control_points)
                    elif hasattr(entity, "fit_points") and entity.fit_points:
                        fit_points = [(fp[0], fp[1]) for fp in entity.fit_points]
                        if len(fit_points) >= 3:
                            return Polygon(fit_points)
                except Exception:
                    pass

        elif entity_type == "ELLIPSE":
            # Improved ELLIPSE with more points
            try:
                sampled_points = []
                for angle in np.linspace(
                    0, 2 * np.pi, 72
                ):  # 72 points for smoother curve
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
            for angle in np.linspace(0, 2 * np.pi, 36):  # 36 points for circle
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
    """COMPLETELY CORRECTED - Use coordinate mapping from original to transformed polygon"""
    
    print(f"🔧 CORRECTED save_dxf_layout_complete called with {len(placed_elements)} elements")
    print(f"🔧 Output path: {output_path}")
    print(f"🔧 Sheet size: {sheet_size}")
    
    # Create new DXF document
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4  # millimeters
    doc.header["$LUNITS"] = 2    # decimal units
    msp = doc.modelspace()
    
    for placed_element in placed_elements:
        if len(placed_element) >= 6:
            (transformed_polygon, x_offset, y_offset, rotation_angle, file_name, color) = placed_element[:6]
        else:
            transformed_polygon, x_offset, y_offset, rotation_angle, file_name = placed_element[:5]
        
        print(f"🔧 Processing {file_name}: transformed bounds = {transformed_polygon.bounds}")
        
        # Get original DXF data
        file_basename = os.path.basename(file_name) if file_name else file_name
        original_data_key = None
        
        if original_dxf_data_map:
            if file_name in original_dxf_data_map:
                original_data_key = file_name
            elif file_basename in original_dxf_data_map:
                original_data_key = file_basename
            else:
                for key in original_dxf_data_map.keys():
                    if os.path.basename(key) == file_basename:
                        original_data_key = key
                        break
        
        if original_data_key:
            original_data = original_dxf_data_map[original_data_key]
            
            if original_data["original_entities"] and original_data["combined_polygon"]:
                original_polygon = original_data["combined_polygon"]
                orig_bounds = original_polygon.bounds
                target_bounds = transformed_polygon.bounds
                
                # Calculate uniform scale factor to avoid distortion
                orig_width = orig_bounds[2] - orig_bounds[0]
                orig_height = orig_bounds[3] - orig_bounds[1]
                target_width = target_bounds[2] - target_bounds[0]
                target_height = target_bounds[3] - target_bounds[1]
                
                # For rotated polygons, dimensions are swapped, so calculate both possibilities
                scale_direct = min(target_width / orig_width, target_height / orig_height) if orig_width > 0 and orig_height > 0 else 1.0
                scale_swapped = min(target_width / orig_height, target_height / orig_width) if orig_width > 0 and orig_height > 0 else 1.0
                
                # Choose the scale that makes more sense based on rotation
                if rotation_angle % 180 == 90:  # 90° or 270° rotation
                    scale_factor = scale_swapped
                else:  # 0° or 180° rotation
                    scale_factor = scale_direct
                
                print(f"🔧 Rotation: {rotation_angle}°, Scale factor: {scale_factor:.3f}")
                print(f"🔧 Original bounds: {orig_bounds}")
                print(f"🔧 Target bounds: {target_bounds}")
                
                # Calculate centers
                orig_center_x = (orig_bounds[0] + orig_bounds[2]) / 2
                orig_center_y = (orig_bounds[1] + orig_bounds[3]) / 2
                target_center_x = (target_bounds[0] + target_bounds[2]) / 2
                target_center_y = (target_bounds[1] + target_bounds[3]) / 2
                
                # For rotation calculations
                rotation_rad = math.radians(rotation_angle) if rotation_angle != 0 else 0
                cos_angle = math.cos(rotation_rad) if rotation_angle != 0 else 1.0
                sin_angle = math.sin(rotation_rad) if rotation_angle != 0 else 0.0
                
                for entity_data in original_data["original_entities"]:
                    entity_type = entity_data["type"]
                    
                    # Skip IMAGE elements to avoid artifacts
                    if entity_type == "IMAGE":
                        continue
                    
                    # Create a copy of the original entity
                    new_entity = entity_data["entity"].copy()
                    
                    # Apply transformation based on entity type
                    if entity_type == "SPLINE":
                        if hasattr(new_entity, 'control_points') and new_entity.control_points:
                            transformed_points = []
                            
                            for cp in new_entity.control_points:
                                if hasattr(cp, "x") and hasattr(cp, "y"):
                                    x, y = cp.x, cp.y
                                    z = getattr(cp, "z", 0.0)
                                elif len(cp) >= 2:
                                    x, y = float(cp[0]), float(cp[1])
                                    z = float(cp[2]) if len(cp) > 2 else 0.0
                                else:
                                    continue
                                
                                # Apply transformation to match the transformed_polygon exactly:
                                # 1. Move to origin relative to original center
                                x_rel = x - orig_center_x
                                y_rel = y - orig_center_y
                                
                                # 2. Apply uniform scaling to preserve aspect ratio
                                x_scaled = x_rel * scale_factor
                                y_scaled = y_rel * scale_factor
                                
                                # 3. Apply rotation around origin
                                if rotation_angle != 0:
                                    x_rotated = x_scaled * cos_angle - y_scaled * sin_angle
                                    y_rotated = x_scaled * sin_angle + y_scaled * cos_angle
                                else:
                                    x_rotated = x_scaled
                                    y_rotated = y_scaled
                                
                                # 4. Translate to final position (target center)
                                final_x = x_rotated + target_center_x
                                final_y = y_rotated + target_center_y
                                
                                transformed_points.append((final_x, final_y, z))
                            
                            if transformed_points:
                                from ezdxf.math import Vec3
                                new_control_points = [Vec3(x, y, z) for x, y, z in transformed_points]
                                new_entity.control_points = new_control_points
                    
                    elif entity_type == "CIRCLE":
                        # Transform circle center
                        orig_center = new_entity.dxf.center
                        x_rel = orig_center[0] - orig_center_x
                        y_rel = orig_center[1] - orig_center_y
                        
                        x_scaled = x_rel * scale_factor
                        y_scaled = y_rel * scale_factor
                        
                        if rotation_angle != 0:
                            x_rotated = x_scaled * cos_angle - y_scaled * sin_angle
                            y_rotated = x_scaled * sin_angle + y_scaled * cos_angle
                        else:
                            x_rotated = x_scaled
                            y_rotated = y_scaled
                        
                        final_x = x_rotated + target_center_x
                        final_y = y_rotated + target_center_y
                        
                        new_entity.dxf.center = (final_x, final_y, orig_center[2] if len(orig_center) > 2 else 0)
                        new_entity.dxf.radius = new_entity.dxf.radius * scale_factor
                    
                    elif entity_type == "ARC":
                        # Transform arc center
                        orig_center = new_entity.dxf.center
                        x_rel = orig_center[0] - orig_center_x
                        y_rel = orig_center[1] - orig_center_y
                        
                        x_scaled = x_rel * scale_factor
                        y_scaled = y_rel * scale_factor
                        
                        if rotation_angle != 0:
                            x_rotated = x_scaled * cos_angle - y_scaled * sin_angle
                            y_rotated = x_scaled * sin_angle + y_scaled * cos_angle
                        else:
                            x_rotated = x_scaled
                            y_rotated = y_scaled
                        
                        final_x = x_rotated + target_center_x
                        final_y = y_rotated + target_center_y
                        
                        new_entity.dxf.center = (final_x, final_y, orig_center[2] if len(orig_center) > 2 else 0)
                        new_entity.dxf.radius = new_entity.dxf.radius * scale_factor
                        
                        # Adjust angles for rotation
                        if rotation_angle != 0:
                            new_entity.dxf.start_angle = (new_entity.dxf.start_angle + rotation_angle) % 360
                            new_entity.dxf.end_angle = (new_entity.dxf.end_angle + rotation_angle) % 360
                    
                    elif entity_type == "LWPOLYLINE":
                        # Transform all points in the polyline
                        points = list(new_entity.get_points())
                        transformed_points = []
                        
                        for point in points:
                            x, y = point[0], point[1]
                            bulge = point[2] if len(point) > 2 else 0
                            start_width = point[3] if len(point) > 3 else 0
                            end_width = point[4] if len(point) > 4 else 0
                            
                            x_rel = x - orig_center_x
                            y_rel = y - orig_center_y
                            
                            x_scaled = x_rel * scale_factor
                            y_scaled = y_rel * scale_factor
                            
                            if rotation_angle != 0:
                                x_rotated = x_scaled * cos_angle - y_scaled * sin_angle
                                y_rotated = x_scaled * sin_angle + y_scaled * cos_angle
                            else:
                                x_rotated = x_scaled
                                y_rotated = y_scaled
                            
                            final_x = x_rotated + target_center_x
                            final_y = y_rotated + target_center_y
                            
                            transformed_points.append((final_x, final_y, bulge, start_width * scale_factor, end_width * scale_factor))
                        
                        # Clear existing points and add transformed ones
                        new_entity.clear()
                        for tp in transformed_points:
                            new_entity.append(tp[:2], format='xyb' if len(tp) > 2 and tp[2] != 0 else 'xy')
                            if len(tp) > 3 and (tp[3] != 0 or tp[4] != 0):
                                new_entity[-1] = (tp[0], tp[1], tp[2], tp[3], tp[4])
                    
                    elif entity_type == "POLYLINE":
                        # Transform all vertices in the polyline
                        for vertex in new_entity.vertices:
                            orig_location = vertex.dxf.location
                            x, y = orig_location[0], orig_location[1]
                            z = orig_location[2] if len(orig_location) > 2 else 0
                            
                            x_rel = x - orig_center_x
                            y_rel = y - orig_center_y
                            
                            x_scaled = x_rel * scale_factor
                            y_scaled = y_rel * scale_factor
                            
                            if rotation_angle != 0:
                                x_rotated = x_scaled * cos_angle - y_scaled * sin_angle
                                y_rotated = x_scaled * sin_angle + y_scaled * cos_angle
                            else:
                                x_rotated = x_scaled
                                y_rotated = y_scaled
                            
                            final_x = x_rotated + target_center_x
                            final_y = y_rotated + target_center_y
                            
                            vertex.dxf.location = (final_x, final_y, z)
                    
                    elif entity_type == "ELLIPSE":
                        # Transform ellipse center and axes
                        orig_center = new_entity.dxf.center
                        x_rel = orig_center[0] - orig_center_x
                        y_rel = orig_center[1] - orig_center_y
                        
                        x_scaled = x_rel * scale_factor
                        y_scaled = y_rel * scale_factor
                        
                        if rotation_angle != 0:
                            x_rotated = x_scaled * cos_angle - y_scaled * sin_angle
                            y_rotated = x_scaled * sin_angle + y_scaled * cos_angle
                        else:
                            x_rotated = x_scaled
                            y_rotated = y_scaled
                        
                        final_x = x_rotated + target_center_x
                        final_y = y_rotated + target_center_y
                        
                        new_entity.dxf.center = (final_x, final_y, orig_center[2] if len(orig_center) > 2 else 0)
                        
                        # Scale and rotate major axis
                        orig_major_axis = new_entity.dxf.major_axis
                        major_x_scaled = orig_major_axis[0] * scale_factor
                        major_y_scaled = orig_major_axis[1] * scale_factor
                        
                        if rotation_angle != 0:
                            major_x_rotated = major_x_scaled * cos_angle - major_y_scaled * sin_angle
                            major_y_rotated = major_x_scaled * sin_angle + major_y_scaled * cos_angle
                        else:
                            major_x_rotated = major_x_scaled
                            major_y_rotated = major_y_scaled
                        
                        new_entity.dxf.major_axis = (major_x_rotated, major_y_rotated, orig_major_axis[2] if len(orig_major_axis) > 2 else 0)
                        new_entity.dxf.ratio = new_entity.dxf.ratio  # Keep ratio unchanged
                    
                    elif entity_type in ["LINE", "POINT", "TEXT", "MTEXT", "DIMENSION"]:
                        # For other common entity types, apply basic transformation
                        # This is a simplified approach - you might need more specific handling
                        if hasattr(new_entity.dxf, 'location'):
                            orig_location = new_entity.dxf.location
                            x, y = orig_location[0], orig_location[1]
                            z = orig_location[2] if len(orig_location) > 2 else 0
                            
                            x_rel = x - orig_center_x
                            y_rel = y - orig_center_y
                            
                            x_scaled = x_rel * scale_factor
                            y_scaled = y_rel * scale_factor
                            
                            if rotation_angle != 0:
                                x_rotated = x_scaled * cos_angle - y_scaled * sin_angle
                                y_rotated = x_scaled * sin_angle + y_scaled * cos_angle
                            else:
                                x_rotated = x_scaled
                                y_rotated = y_scaled
                            
                            final_x = x_rotated + target_center_x
                            final_y = y_rotated + target_center_y
                            
                            new_entity.dxf.location = (final_x, final_y, z)
                        
                        elif hasattr(new_entity.dxf, 'start') and hasattr(new_entity.dxf, 'end'):
                            # Handle LINE entities
                            for attr_name in ['start', 'end']:
                                orig_point = getattr(new_entity.dxf, attr_name)
                                x, y = orig_point[0], orig_point[1]
                                z = orig_point[2] if len(orig_point) > 2 else 0
                                
                                x_rel = x - orig_center_x
                                y_rel = y - orig_center_y
                                
                                x_scaled = x_rel * scale_factor
                                y_scaled = y_rel * scale_factor
                                
                                if rotation_angle != 0:
                                    x_rotated = x_scaled * cos_angle - y_scaled * sin_angle
                                    y_rotated = x_scaled * sin_angle + y_scaled * cos_angle
                                else:
                                    x_rotated = x_scaled
                                    y_rotated = y_scaled
                                
                                final_x = x_rotated + target_center_x
                                final_y = y_rotated + target_center_y
                                
                                setattr(new_entity.dxf, attr_name, (final_x, final_y, z))
                    
                    # Set layer and add to modelspace
                    new_entity.dxf.layer = entity_data["layer"]
                    
                    # Set color: keep red range as is, make everything else black (7)
                    original_color = entity_data.get("color", 256)
                    
                    # Check if color is in red range: 1, 10-19, 240-255
                    is_blue = original_color < 200
                    
                    if is_blue:
                        new_entity.dxf.color = 250               # Make everything else black
                    else:
                        new_entity.dxf.color = original_color  # Keep red colors as is

                    msp.add_entity(new_entity)
    
    # Save the document
    doc.saveas(output_path)


def parse_dxf(file, verbose=True) -> Polygon:
    """Parse a DXF file to extract all shapes and combine them into one polygon."""
    if hasattr(file, "read"):
        # If it's a file-like object (BytesIO), write to temp file first
        with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as tmp_file:
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
                points = [
                    (vertex.dxf.location[0], vertex.dxf.location[1])
                    for vertex in entity.vertices
                ]
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
                except Exception:
                    # Fallback: try to get control points
                    try:
                        control_points = [
                            (cp[0], cp[1]) for cp in entity.control_points
                        ]
                        if len(control_points) >= 3:
                            polygon = Polygon(control_points)
                    except:
                        pass

            elif entity_type == "ELLIPSE":
                # Convert ELLIPSE to polygon by sampling points
                try:
                    sampled_points = []
                    for angle in np.linspace(0, 2 * np.pi, 36):  # Sample 36 points
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
                    for angle in np.linspace(0, 2 * np.pi, 36):
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
        if hasattr(combined, "geoms"):
            # It's a MultiPolygon, take convex hull to get single polygon
            combined = combined.convex_hull
            if verbose:
                st.info(
                    f"Объединено в один полигон (convex hull), площадь: {combined.area:.2f}"
                )
        else:
            if verbose:
                st.info(f"Объединено в один полигон, площадь: {combined.area:.2f}")

        return combined
    else:
        if verbose:
            st.error("Не найдено валидных полигонов для объединения")
        return None


def rotate_polygon(polygon: Polygon, angle: float) -> Polygon:
    """Rotate a polygon by a given angle (in degrees) around its centroid.

    Using centroid rotation for better stability and predictable results.
    """
    if angle == 0:
        return polygon

    # Use centroid as rotation origin for better stability
    centroid = polygon.centroid
    rotation_origin = (centroid.x, centroid.y)

    # Rotate around centroid instead of corner to avoid positioning issues
    rotated = affinity.rotate(polygon, angle, origin=rotation_origin)

    # Ensure the rotated polygon is valid
    if not rotated.is_valid:
        try:
            # Try to fix invalid geometry
            rotated = rotated.buffer(0)
        except Exception:
            # If fixing fails, return original polygon
            return polygon

    return rotated


def translate_polygon(polygon: Polygon, x: float, y: float) -> Polygon:
    """Translate a polygon to a new position."""
    return affinity.translate(polygon, xoff=x, yoff=y)


def place_polygon_at_origin(polygon: Polygon) -> Polygon:
    """Move polygon so its bottom-left corner is at (0,0)."""
    bounds = polygon.bounds
    return translate_polygon(polygon, -bounds[0], -bounds[1])


def apply_placement_transform(
    polygon: Polygon, x_offset: float, y_offset: float, rotation_angle: float
) -> Polygon:
    """Apply the same transformation sequence used in bin_packing.

    This ensures consistency between visualization and DXF output.

    Args:
        polygon: Original polygon
        x_offset: X translation offset
        y_offset: Y translation offset
        rotation_angle: Rotation angle in degrees

    Returns:
        Transformed polygon
    """
    # Step 1: Move to origin
    bounds = polygon.bounds
    normalized = translate_polygon(polygon, -bounds[0], -bounds[1])

    # Step 2: Rotate around centroid if needed
    if rotation_angle != 0:
        rotated = rotate_polygon(normalized, rotation_angle)
    else:
        rotated = normalized

    # Step 3: Apply final translation
    # Note: x_offset and y_offset already account for the original bounds
    final_polygon = translate_polygon(
        rotated, x_offset + bounds[0], y_offset + bounds[1]
    )

    return final_polygon


def check_collision(polygon1: Polygon, polygon2: Polygon, min_gap: float = 2.0) -> bool:
    """Check if two polygons collide with minimum gap requirement.

    Enhanced version with improved collision detection.

    Args:
        polygon1: First polygon
        polygon2: Second polygon
        min_gap: Minimum gap required between polygons in mm (default 2mm)

    Returns:
        True if polygons are too close (collision), False if they have sufficient gap
    """
    # Fast validity check
    if not (polygon1.is_valid and polygon2.is_valid):
        return True  # Treat invalid polygons as collision

    # OPTIMIZATION 1: Enhanced bounding box distance check
    bounds1 = polygon1.bounds
    bounds2 = polygon2.bounds

    # Calculate minimum distance between bounding boxes with safety margin
    dx = max(0, max(bounds1[0] - bounds2[2], bounds2[0] - bounds1[2]))
    dy = max(0, max(bounds1[1] - bounds2[3], bounds2[1] - bounds1[3]))
    bbox_distance = (dx * dx + dy * dy) ** 0.5

    # If bounding boxes are far enough apart, no collision possible
    if bbox_distance >= min_gap + 1.0:  # Extra safety margin
        return False

    # OPTIMIZATION 2: Quick intersection check - if they overlap, it's definitely a collision
    if polygon1.intersects(polygon2):
        return True

    # OPTIMIZATION 3: More accurate distance calculation for close polygons
    try:
        # Use buffered polygon for more conservative collision detection
        buffered_polygon1 = polygon1.buffer(min_gap / 2.0)
        if buffered_polygon1.intersects(polygon2):
            return True

        # Final precise distance check
        distance = polygon1.distance(polygon2)
        return distance < min_gap
    except Exception:
        # If calculation fails, use conservative buffer check
        try:
            buffer1 = polygon1.buffer(min_gap)
            return buffer1.intersects(polygon2)
        except Exception:
            return True  # Be conservative if all methods fail


def bin_packing_with_existing(
    polygons: list[tuple],
    existing_placed: list[tuple],
    sheet_size: tuple[float, float],
    max_attempts: int = 1000,
    verbose: bool = True,
) -> tuple[list[tuple], list[tuple]]:
    """Bin packing that considers already placed polygons on the sheet."""
    # Convert sheet size from cm to mm to match DXF polygon units
    sheet_width_mm, sheet_height_mm = sheet_size[0] * 10, sheet_size[1] * 10

    placed = []
    unplaced = []

    # Start with existing placed polygons as obstacles
    obstacles = [placed_tuple[0] for placed_tuple in existing_placed]

    if verbose:
        st.info(
            f"Дозаполняем лист с {len(obstacles)} существующими деталями, добавляем {len(polygons)} новых"
        )

    # IMPROVEMENT 1: Sort polygons by area and perimeter for better packing
    def get_polygon_priority(polygon_tuple):
        polygon = polygon_tuple[0]
        # Combine area and perimeter for better sorting (larger, more complex shapes first)
        area = polygon.area
        bounds = polygon.bounds
        perimeter_approx = 2 * ((bounds[2] - bounds[0]) + (bounds[3] - bounds[1]))
        return area + perimeter_approx * 0.1

    sorted_polygons = sorted(polygons, key=get_polygon_priority, reverse=True)

    for i, polygon_tuple in enumerate(sorted_polygons):
        if len(polygon_tuple) >= 4:  # Extended format with color and order_id
            polygon, file_name, color, order_id = polygon_tuple[:4]
        elif len(polygon_tuple) >= 3:  # Format with color
            polygon, file_name, color = polygon_tuple[:3]
            order_id = "unknown"
        else:  # Old format without color
            polygon, file_name = polygon_tuple[:2]
            color = "серый"
            order_id = "unknown"

        placed_successfully = False

        # Check if polygon is too large for the sheet
        bounds = polygon.bounds
        poly_width = bounds[2] - bounds[0]
        poly_height = bounds[3] - bounds[1]

        if poly_width > sheet_width_mm or poly_height > sheet_height_mm:
            unplaced.append((polygon, file_name, color, order_id))
            continue

        # Try all allowed orientations (0°, 90°, 180°, 270°) with better placement
        best_placement = None
        best_waste = float("inf")

        # Only allowed rotation angles for cutting machines
        rotation_angles = [0, 90, 180, 270]

        for angle in rotation_angles:
            rotated = rotate_polygon(polygon, angle) if angle != 0 else polygon
            rotated_bounds = rotated.bounds
            rotated_width = rotated_bounds[2] - rotated_bounds[0]
            rotated_height = rotated_bounds[3] - rotated_bounds[1]

            # Skip if doesn't fit
            if rotated_width > sheet_width_mm or rotated_height > sheet_height_mm:
                continue

            # Find position that avoids existing obstacles
            best_x, best_y = find_bottom_left_position_with_obstacles(
                rotated, obstacles, sheet_width_mm, sheet_height_mm
            )

            if best_x is not None and best_y is not None:
                # Calculate waste for this placement
                translated = translate_polygon(
                    rotated, best_x - rotated_bounds[0], best_y - rotated_bounds[1]
                )
                waste = calculate_placement_waste(
                    translated,
                    [(obs, 0, 0, 0, "obstacle") for obs in obstacles],
                    sheet_width_mm,
                    sheet_height_mm,
                )

                if waste < best_waste:
                    best_waste = waste
                    best_placement = {
                        "polygon": translated,
                        "x_offset": best_x - rotated_bounds[0],
                        "y_offset": best_y - rotated_bounds[1],
                        "angle": angle,
                    }

        # Apply best placement if found
        if best_placement:
            placed.append(
                (
                    best_placement["polygon"],
                    best_placement["x_offset"],
                    best_placement["y_offset"],
                    best_placement["angle"],
                    file_name,
                    color,
                    order_id,
                )
            )
            # Add this polygon as an obstacle for subsequent placements
            obstacles.append(best_placement["polygon"])
            placed_successfully = True

        if not placed_successfully:
            unplaced.append((polygon, file_name, color, order_id))

    return placed, unplaced


def bin_packing(
    polygons: list[tuple],
    sheet_size: tuple[float, float],
    max_attempts: int = 1000,
    verbose: bool = True,
) -> tuple[list[tuple], list[tuple]]:
    """Optimize placement of complex polygons on a sheet with improved algorithm."""
    # Convert sheet size from cm to mm to match DXF polygon units
    sheet_width_mm, sheet_height_mm = sheet_size[0] * 10, sheet_size[1] * 10

    placed = []
    unplaced = []

    if verbose:
        st.info(
            f"Начинаем улучшенную упаковку {len(polygons)} полигонов на листе {sheet_size[0]}x{sheet_size[1]} см"
        )

    # IMPROVEMENT 1: Sort polygons by area and perimeter for better packing
    def get_polygon_priority(polygon_tuple):
        polygon = polygon_tuple[0]
        # Combine area and perimeter for better sorting (larger, more complex shapes first)
        area = polygon.area
        bounds = polygon.bounds
        perimeter_approx = 2 * ((bounds[2] - bounds[0]) + (bounds[3] - bounds[1]))
        return area + perimeter_approx * 0.1

    sorted_polygons = sorted(polygons, key=get_polygon_priority, reverse=True)
    if verbose:
        st.info("✨ Сортировка полигонов по площади (сначала крупные)")

    for i, polygon_tuple in enumerate(sorted_polygons):
        logger.debug(
            f"bin_packing: входящий tuple {i}: длина={len(polygon_tuple)}, элементы={polygon_tuple}"
        )

        if len(polygon_tuple) >= 4:  # Extended format with color and order_id
            polygon, file_name, color, order_id = polygon_tuple[:4]
        elif len(polygon_tuple) >= 3:  # Format with color
            polygon, file_name, color = polygon_tuple[:3]
            order_id = "unknown"
        else:  # Old format without color
            polygon, file_name = polygon_tuple[:2]
            color = "серый"
            order_id = "unknown"

        logger.debug(
            f"bin_packing: извлечено file_name='{file_name}' (тип: {type(file_name)}), order_id='{order_id}')"
        )
        placed_successfully = False
        if verbose:
            st.info(
                f"Обрабатываем полигон {i+1}/{len(sorted_polygons)} из файла {file_name}, площадь: {polygon.area:.2f}"
            )

        # Check if polygon is too large for the sheet
        bounds = polygon.bounds
        poly_width = bounds[2] - bounds[0]
        poly_height = bounds[3] - bounds[1]

        if poly_width > sheet_width_mm or poly_height > sheet_height_mm:
            if verbose:
                st.warning(
                    f"Полигон из {file_name} слишком большой: {poly_width/10:.1f}x{poly_height/10:.1f} см > {sheet_size[0]}x{sheet_size[1]} см"
                )
            unplaced.append((polygon, file_name, color, order_id))
            continue

        # IMPROVEMENT 2: Try all allowed orientations (0°, 90°, 180°, 270°) with better placement
        best_placement = None
        best_waste = float("inf")

        # Only allowed rotation angles for cutting machines
        rotation_angles = [0, 90, 180, 270]

        for angle in rotation_angles:
            rotated = rotate_polygon(polygon, angle) if angle != 0 else polygon
            rotated_bounds = rotated.bounds
            rotated_width = rotated_bounds[2] - rotated_bounds[0]
            rotated_height = rotated_bounds[3] - rotated_bounds[1]

            # Skip if doesn't fit
            if rotated_width > sheet_width_mm or rotated_height > sheet_height_mm:
                continue

            # IMPROVEMENT 3: Bottom-Left Fill algorithm for better placement
            best_x, best_y = find_bottom_left_position(
                rotated, placed, sheet_width_mm, sheet_height_mm
            )

            if best_x is not None and best_y is not None:
                # Calculate waste for this placement
                translated = translate_polygon(
                    rotated, best_x - rotated_bounds[0], best_y - rotated_bounds[1]
                )
                waste = calculate_placement_waste(
                    translated, placed, sheet_width_mm, sheet_height_mm
                )

                if waste < best_waste:
                    best_waste = waste
                    best_placement = {
                        "polygon": translated,
                        "x_offset": best_x - rotated_bounds[0],
                        "y_offset": best_y - rotated_bounds[1],
                        "angle": angle,
                    }

        # Apply best placement if found
        if best_placement:
            placed.append(
                (
                    best_placement["polygon"],
                    best_placement["x_offset"],
                    best_placement["y_offset"],
                    best_placement["angle"],
                    file_name,
                    color,
                    order_id,
                )
            )
            placed_successfully = True
            if verbose:
                st.success(
                    f"✅ Размещен {file_name} (угол: {best_placement['angle']}°, waste: {best_waste:.1f})"
                )
        else:
            # Fallback to original grid method if no bottom-left position found
            simple_bounds = polygon.bounds
            simple_width = simple_bounds[2] - simple_bounds[0]
            simple_height = simple_bounds[3] - simple_bounds[1]

            # Optimized grid placement as fallback
            max_grid_attempts = 10  # Reduced for better performance
            if sheet_width_mm > simple_width:
                x_positions = np.linspace(
                    0, sheet_width_mm - simple_width, max_grid_attempts
                )
            else:
                x_positions = [0]

            if sheet_height_mm > simple_height:
                y_positions = np.linspace(
                    0, sheet_height_mm - simple_height, max_grid_attempts
                )
            else:
                y_positions = [0]

            # PERFORMANCE: Pre-compute placed polygon bounds for faster collision checking
            placed_bounds_cache = [placed_poly.bounds for placed_poly, *_ in placed]

            for grid_x in x_positions:
                for grid_y in y_positions:
                    x_offset = grid_x - simple_bounds[0]
                    y_offset = grid_y - simple_bounds[1]

                    # Fast bounds check
                    test_bounds = (
                        simple_bounds[0] + x_offset,
                        simple_bounds[1] + y_offset,
                        simple_bounds[2] + x_offset,
                        simple_bounds[3] + y_offset,
                    )

                    if not (
                        test_bounds[0] >= -0.1
                        and test_bounds[1] >= -0.1
                        and test_bounds[2] <= sheet_width_mm + 0.1
                        and test_bounds[3] <= sheet_height_mm + 0.1
                    ):
                        continue

                    # OPTIMIZATION: Fast bounding box collision check first
                    bbox_collision = False
                    for placed_bounds in placed_bounds_cache:
                        if not (
                            test_bounds[2] + 2.0 <= placed_bounds[0]
                            or test_bounds[0] >= placed_bounds[2] + 2.0
                            or test_bounds[3] + 2.0 <= placed_bounds[1]
                            or test_bounds[1] >= placed_bounds[3] + 2.0
                        ):
                            bbox_collision = True
                            break

                    if bbox_collision:
                        continue

                    # Only create polygon if bounding box check passes
                    translated = translate_polygon(polygon, x_offset, y_offset)

                    # Final precise collision check
                    collision = False
                    for placed_poly, *_ in placed:
                        if check_collision(translated, placed_poly):
                            collision = True
                            break

                    if not collision:
                        placed.append(
                            (
                                translated,
                                x_offset,
                                y_offset,
                                0,
                                file_name,
                                color,
                                order_id,
                            )
                        )
                        placed_successfully = True
                        if verbose:
                            st.success(f"✅ Размещен {file_name} (сетчатое размещение)")
                        break

                if placed_successfully:
                    break

        if not placed_successfully:
            if verbose:
                st.warning(f"❌ Не удалось разместить полигон из {file_name}")
            unplaced.append((polygon, file_name, color, order_id))

    if verbose:
        usage_percent = calculate_usage_percent(placed, sheet_size)
        st.info(
            f"🏁 Упаковка завершена: {len(placed)} размещено, {len(unplaced)} не размещено, использование: {usage_percent:.1f}%"
        )
    return placed, unplaced


def find_bottom_left_position_with_obstacles(
    polygon, obstacles, sheet_width, sheet_height
):
    """Find the bottom-left position for a polygon using Bottom-Left Fill algorithm with existing obstacles."""
    bounds = polygon.bounds
    poly_width = bounds[2] - bounds[0]
    poly_height = bounds[3] - bounds[1]

    # Try positions along bottom and left edges first
    candidate_positions = []

    # Bottom edge positions
    for x in np.arange(0, sheet_width - poly_width + 1, 5):  # 5mm steps
        candidate_positions.append((x, 0))

    # Left edge positions
    for y in np.arange(0, sheet_height - poly_height + 1, 5):  # 5mm steps
        candidate_positions.append((0, y))

    # Positions based on existing obstacles (bottom-left principle)
    for obstacle in obstacles:
        obstacle_bounds = obstacle.bounds

        # Try position to the right of existing obstacle
        x = obstacle_bounds[2] + 3  # 3mm gap for safety
        if x + poly_width <= sheet_width:
            candidate_positions.append((x, obstacle_bounds[1]))  # Same Y as existing
            candidate_positions.append((x, 0))  # Bottom edge

        # Try position above existing obstacle
        y = obstacle_bounds[3] + 3  # 3mm gap for safety
        if y + poly_height <= sheet_height:
            candidate_positions.append((obstacle_bounds[0], y))  # Same X as existing
            candidate_positions.append((0, y))  # Left edge

    # Sort by bottom-left preference (y first, then x)
    candidate_positions.sort(key=lambda pos: (pos[1], pos[0]))

    # Test each position
    for x, y in candidate_positions:
        # OPTIMIZATION: Fast boundary pre-check without polygon creation
        if x + poly_width > sheet_width + 0.1 or y + poly_height > sheet_height + 0.1:
            continue
        if x < -0.1 or y < -0.1:
            continue

        # OPTIMIZATION: Pre-calculate translation offset
        x_offset = x - bounds[0]
        y_offset = y - bounds[1]

        # OPTIMIZATION: Check if bounds would be valid after translation
        test_bounds = (
            bounds[0] + x_offset,
            bounds[1] + y_offset,
            bounds[2] + x_offset,
            bounds[3] + y_offset,
        )
        if (
            test_bounds[0] < -0.1
            or test_bounds[1] < -0.1
            or test_bounds[2] > sheet_width + 0.1
            or test_bounds[3] > sheet_height + 0.1
        ):
            continue

        # Only create translated polygon if all checks pass
        test_polygon = translate_polygon(polygon, x_offset, y_offset)

        # OPTIMIZATION: Early exit on first collision
        collision = False
        for obstacle in obstacles:
            if check_collision(test_polygon, obstacle):
                collision = True
                break

        if not collision:
            return x, y

    return None, None


def find_bottom_left_position(polygon, placed_polygons, sheet_width, sheet_height):
    """Find the bottom-left position for a polygon using optimized Bottom-Left Fill algorithm."""
    bounds = polygon.bounds
    poly_width = bounds[2] - bounds[0]
    poly_height = bounds[3] - bounds[1]

    # PERFORMANCE OPTIMIZATION: Pre-compute placed polygon bounds
    placed_bounds_list = []
    for placed_tuple in placed_polygons:
        placed_polygon = placed_tuple[0]
        placed_bounds_list.append(placed_polygon.bounds)

    # Generate candidate positions more efficiently
    candidate_positions = set()  # Use set to avoid duplicates

    # Bottom and left edge positions with larger steps for faster processing
    step_size = max(5, min(poly_width, poly_height) / 4)  # Adaptive step size

    # Bottom edge positions
    for x in np.arange(0, sheet_width - poly_width + 1, step_size):
        candidate_positions.add((x, 0))

    # Left edge positions
    for y in np.arange(0, sheet_height - poly_height + 1, step_size):
        candidate_positions.add((0, y))

    # OPTIMIZATION: Generate positions based on existing polygons more efficiently
    min_gap = 3.0
    for placed_bounds in placed_bounds_list:
        # Try position to the right of existing polygon
        x = placed_bounds[2] + min_gap
        if x + poly_width <= sheet_width:
            candidate_positions.add((x, placed_bounds[1]))  # Same Y as existing
            candidate_positions.add((x, 0))  # Bottom edge

        # Try position above existing polygon
        y = placed_bounds[3] + min_gap
        if y + poly_height <= sheet_height:
            candidate_positions.add((placed_bounds[0], y))  # Same X as existing
            candidate_positions.add((0, y))  # Left edge

    # Convert to sorted list (bottom-left preference)
    candidate_positions = sorted(candidate_positions, key=lambda pos: (pos[1], pos[0]))

    # PERFORMANCE: Pre-calculate translation offset and test bounds for all candidates
    for x, y in candidate_positions:
        # Fast boundary pre-check
        if (
            x + poly_width > sheet_width + 0.1
            or y + poly_height > sheet_height + 0.1
            or x < -0.1
            or y < -0.1
        ):
            continue

        x_offset = x - bounds[0]
        y_offset = y - bounds[1]

        # Check bounds before expensive polygon creation
        test_bounds = (
            bounds[0] + x_offset,
            bounds[1] + y_offset,
            bounds[2] + x_offset,
            bounds[3] + y_offset,
        )
        if (
            test_bounds[0] < -0.1
            or test_bounds[1] < -0.1
            or test_bounds[2] > sheet_width + 0.1
            or test_bounds[3] > sheet_height + 0.1
        ):
            continue

        # OPTIMIZATION: Fast bounding box collision check before creating polygon
        bbox_collision = False
        for placed_bounds in placed_bounds_list:
            # Check if bounding boxes intersect with minimum gap
            if not (
                test_bounds[2] + 2.0 <= placed_bounds[0]  # test is left of placed
                or test_bounds[0] >= placed_bounds[2] + 2.0  # test is right of placed
                or test_bounds[3] + 2.0 <= placed_bounds[1]  # test is below placed
                or test_bounds[1] >= placed_bounds[3] + 2.0
            ):  # test is above placed
                bbox_collision = True
                break

        if bbox_collision:
            continue

        # Only create polygon and do full collision check if bounding box test passes
        test_polygon = translate_polygon(polygon, x_offset, y_offset)

        # Final collision check with actual polygons
        collision = False
        for p, *_ in placed_polygons:
            if check_collision(test_polygon, p):
                collision = True
                break

        if not collision:
            return x, y

    return None, None


def calculate_placement_waste(polygon, placed_polygons, sheet_width, sheet_height):
    """Calculate waste/inefficiency for a polygon placement."""
    bounds = polygon.bounds

    # Calculate compactness - how close polygon is to other polygons and edges
    edge_distance = min(bounds[0], bounds[1])  # Distance to bottom-left corner

    # Distance to other polygons
    min_neighbor_distance = float("inf")
    for placed_tuple in placed_polygons:
        placed_polygon = placed_tuple[0]
        placed_bounds = placed_polygon.bounds

        # Calculate minimum distance between bounding boxes
        dx = max(0, max(bounds[0] - placed_bounds[2], placed_bounds[0] - bounds[2]))
        dy = max(0, max(bounds[1] - placed_bounds[3], placed_bounds[1] - bounds[3]))
        distance = (dx**2 + dy**2) ** 0.5

        min_neighbor_distance = min(min_neighbor_distance, distance)

    if min_neighbor_distance == float("inf"):
        min_neighbor_distance = 0  # First polygon

    # Waste = edge_distance + average neighbor distance (lower is better)
    waste = edge_distance + min_neighbor_distance * 0.5
    return waste


def bin_packing_with_inventory(
    polygons: list[tuple],
    available_sheets: list[dict],
    verbose: bool = True,
    max_sheets_per_order: int = None,
) -> tuple[list[dict], list[tuple]]:
    """Optimize placement of polygons on available sheets with inventory tracking."""
    logger.info("=== НАЧАЛО bin_packing_with_inventory ===")
    logger.info(
        f"Входные параметры: {len(polygons)} полигонов, {len(available_sheets)} типов листов, max_sheets_per_order={max_sheets_per_order}"
    )

    placed_layouts = []
    all_unplaced = []
    sheet_inventory = [
        sheet.copy() for sheet in available_sheets
    ]  # Copy to avoid modifying original

    if verbose:
        total_available = sum(
            sheet["count"] - sheet["used"] for sheet in sheet_inventory
        )
        st.info(
            f"Начинаем размещение {len(polygons)} полигонов на {total_available} доступных листах"
        )
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
            order_id = "unknown"
        else:  # Old format without color
            polygon, name = polygon_tuple[:2]
            color = "серый"
            order_id = "unknown"

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
                filename = polygon_tuple[1] if len(polygon_tuple) > 1 else "unknown"
                st.write(f"    - {filename}")

    sheet_counter = 0

    # Track sheets used per order for constraint checking
    order_sheet_usage = {order_id: 0 for order_id in order_groups.keys()}

    logger.info(
        f"Используем упрощенный эффективный алгоритм: {len(order_groups)} заказов"
    )

    # Process orders one by one, but allow filling sheets with multiple orders
    remaining_orders = dict(order_groups)  # Copy to modify
    max_iterations = max(100, len(remaining_orders) * 50)  # Safety limit with higher multiplier
    iteration_count = 0

    while remaining_orders and any(
        sheet["count"] - sheet["used"] > 0 for sheet in sheet_inventory
    ):
        iteration_count += 1
        logger.info(f"--- ИТЕРАЦИЯ {iteration_count} ---")
        logger.info(f"Остается заказов: {len(remaining_orders)}")
        for order_id, polygons in remaining_orders.items():
            logger.info(f"  {order_id}: {len(polygons)} полигонов")

        if iteration_count > max_iterations:
            logger.error(
                f"Превышен лимит итераций ({max_iterations}), прерываем выполнение"
            )
            break

        placed_on_current_sheet = False

        # Try each available sheet type
        for sheet_type in sheet_inventory:
            if sheet_type["count"] - sheet_type["used"] <= 0:
                continue  # No more sheets of this type

            sheet_size = (sheet_type["width"], sheet_type["height"])
            sheet_color = sheet_type.get("color", "серый")

            # Collect polygons from orders that can fit on this sheet
            compatible_polygons = []
            orders_to_try = []

            for order_id, order_polygons in remaining_orders.items():
                # Check if this order can still use more sheets
                if (
                    max_sheets_per_order is None
                    or order_id == "additional"
                    or order_id == "unknown"  # Manual uploads are not limited
                    or order_id.startswith("group_")  # Group uploads are not limited
                    or order_sheet_usage[order_id] < max_sheets_per_order
                ):
                    # Filter polygons by color
                    color_matched_polygons = []
                    for polygon_tuple in order_polygons:
                        if len(polygon_tuple) >= 3:
                            color = polygon_tuple[2]
                        else:
                            color = "серый"

                        if color == sheet_color:
                            color_matched_polygons.append(polygon_tuple)

                    if color_matched_polygons:
                        compatible_polygons.extend(color_matched_polygons)
                        orders_to_try.append(order_id)

            if not compatible_polygons:
                logger.debug(f"Нет совместимых полигонов для листа {sheet_type['name']} цвета {sheet_color}")
                continue  # No compatible polygons for this sheet color

            sheet_counter += 1

            if verbose:
                st.info(
                    f"  Лист #{sheet_counter}: {sheet_type['name']} ({sheet_size[0]}x{sheet_size[1]} см, цвет: {sheet_color})"
                )
                st.info(
                    f"  Совместимых полигонов: {len(compatible_polygons)} из заказов: {orders_to_try}"
                )

            logger.info(
                f"Обрабатываем лист #{sheet_counter}: {len(compatible_polygons)} совместимых полигонов из заказов {orders_to_try}"
            )

            # Debug logging before bin_packing call
            logger.debug("=== ПОЛИГОНЫ ПЕРЕД bin_packing ===")
            for idx, poly_tuple in enumerate(compatible_polygons):
                logger.debug(
                    f"  [{idx}] длина={len(poly_tuple)}, элементы={poly_tuple}"
                )
                if len(poly_tuple) > 1:
                    logger.debug(
                        f"      имя файла: '{poly_tuple[1]}' (тип: {type(poly_tuple[1])})"
                    )

            # Try to place compatible polygons on this sheet
            placed, remaining_from_sheet = bin_packing(
                compatible_polygons, sheet_size, verbose=verbose
            )

            # Debug logging after bin_packing call
            logger.debug("=== ПОЛИГОНЫ ПОСЛЕ bin_packing ===")
            logger.debug(f"  Размещено: {len(placed)} полигонов")
            for idx, poly_tuple in enumerate(placed):
                logger.debug(
                    f"  [{idx}] длина={len(poly_tuple)}, элементы={poly_tuple}"
                )
                if len(poly_tuple) >= 5:
                    logger.debug(
                        f"      имя файла: '{poly_tuple[4]}' (тип: {type(poly_tuple[4])})"
                    )  # file_name at index 4
                elif len(poly_tuple) > 1:
                    logger.debug(
                        f"      элемент [1]: '{poly_tuple[1]}' (тип: {type(poly_tuple[1])})"
                    )  # what was mistaken for filename

            if placed:  # If we managed to place something
                sheet_type["used"] += 1

                # Track which orders are represented on this sheet
                orders_on_sheet = set()
                placed_polygon_names = set()

                for polygon_tuple in placed:
                    # bin_packing returns: (polygon, x_offset, y_offset, angle, file_name, color, order_id)
                    if len(polygon_tuple) >= 5:
                        filename = polygon_tuple[4]  # file_name is at index 4
                    else:
                        filename = "unknown"  # fallback

                    placed_polygon_names.add(filename)

                    # Find which order this polygon belongs to
                    found_order = False
                    for order_id, order_polygons in remaining_orders.items():
                        for orig_tuple in order_polygons:
                            if len(orig_tuple) > 1 and orig_tuple[1] == filename:
                                orders_on_sheet.add(order_id)
                                logger.debug(
                                    f"    Полигон {filename} принадлежит заказу {order_id}"
                                )
                                found_order = True
                                break
                        if found_order:
                            break

                    if not found_order:
                        logger.warning(f"    Не найден заказ для полигона {filename}")

                logger.info(
                    f"УСПЕХ: Лист #{sheet_counter} содержит заказы: {orders_on_sheet}"
                )

                # Update order sheet usage
                for order_id in orders_on_sheet:
                    if order_id in order_sheet_usage:
                        order_sheet_usage[order_id] += 1
                        logger.info(
                            f"  Заказ {order_id}: теперь использует {order_sheet_usage[order_id]} листов"
                        )

                placed_layouts.append(
                    {
                        "sheet_number": sheet_counter,
                        "sheet_type": sheet_type["name"],
                        "sheet_size": sheet_size,
                        "placed_polygons": placed,
                        "usage_percent": calculate_usage_percent(placed, sheet_size),
                        "orders_on_sheet": list(orders_on_sheet),
                    }
                )

                # Remove placed polygons from remaining orders
                # We need to match polygons by both filename AND order_id
                placed_polygon_map = {}  # Maps (filename, order_id) -> True
                for polygon_tuple in placed:
                    if len(polygon_tuple) >= 5:
                        filename = polygon_tuple[4]  # file_name is at index 4
                        if len(polygon_tuple) >= 7:
                            order_id = polygon_tuple[6]  # order_id is at index 6
                            placed_polygon_map[(filename, order_id)] = True
                            logger.debug(
                                f"  Размещен полигон: файл='{filename}', заказ='{order_id}'"
                            )

                total_removed = 0
                for order_id in list(remaining_orders.keys()):
                    original_count = len(remaining_orders[order_id])
                    # Only remove polygons that were actually placed from this specific order
                    remaining_orders[order_id] = [
                        p
                        for p in remaining_orders[order_id]
                        if len(p) < 2 or (p[1], order_id) not in placed_polygon_map
                    ]
                    removed_count = original_count - len(remaining_orders[order_id])
                    total_removed += removed_count

                    if removed_count > 0:
                        logger.info(
                            f"  Из заказа {order_id} удалено {removed_count} размещенных полигонов"
                        )

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
                    st.success(
                        f"  ✅ Размещено {len(placed)} объектов на листе {sheet_type['name']}"
                    )
                    st.info(f"  📊 Заказы на листе: {', '.join(orders_on_sheet)}")

                break  # Move to next iteration with remaining orders

        if not placed_on_current_sheet:
            # No sheet type could accommodate any remaining polygons in this iteration
            # Check if we still have available sheets of any type
            sheets_still_available = any(
                sheet["count"] - sheet["used"] > 0 for sheet in sheet_inventory
            )
            
            if not sheets_still_available:
                logger.warning(
                    f"Все листы закончились. Не удалось разместить оставшиеся заказы: {list(remaining_orders.keys())}"
                )
                break
            else:
                # Continue to next iteration - might be color/size mismatch this round
                available_sheets_count = sum(
                    max(0, sheet["count"] - sheet["used"]) for sheet in sheet_inventory
                )
                logger.info(
                    f"Не удалось разместить в этой итерации. Доступно листов: {available_sheets_count}. Продолжаем..."
                )
                continue

    # Check order constraints after placement
    violated_orders = []
    for order_id, sheets_used in order_sheet_usage.items():
        if (
            max_sheets_per_order
            and order_id != "additional"
            and order_id != "unknown"  # Manual uploads are not limited
            and not order_id.startswith("group_")  # Group uploads are not limited
            and sheets_used > max_sheets_per_order
        ):
            violated_orders.append((order_id, sheets_used))
            logger.error(
                f"НАРУШЕНИЕ ОГРАНИЧЕНИЙ: Заказ {order_id} использует {sheets_used} листов (лимит: {max_sheets_per_order})"
            )

    if violated_orders:
        error_msg = "❌ Нарушение ограничений заказов:\n" + "\n".join(
            [
                f"Заказ {order_id}: {sheets_used} листов (лимит: {max_sheets_per_order})"
                for order_id, sheets_used in violated_orders
            ]
        )
        if verbose:
            st.error(error_msg)
        raise ValueError(error_msg)

    # IMPROVEMENT: Try to fit remaining polygons into existing sheets before giving up
    remaining_polygons_list = []
    for order_id, remaining_polygons in remaining_orders.items():
        remaining_polygons_list.extend(remaining_polygons)

    logger.info(
        f"Проверка дозаполнения: remaining_orders={len(remaining_orders)}, remaining_polygons_list={len(remaining_polygons_list)}, placed_layouts={len(placed_layouts)}"
    )

    if remaining_polygons_list and placed_layouts:
        if verbose:
            st.info(
                f"🔄 Пытаемся дозаполнить {len(placed_layouts)} существующих листов {len(remaining_polygons_list)} оставшимися деталями"
            )
    else:
        logger.info(
            f"Дозаполнение не запущено: remaining_polygons_list={len(remaining_polygons_list)}, placed_layouts={len(placed_layouts)}"
        )

        logger.info(
            f"Попытка дозаполнения: {len(remaining_polygons_list)} полигонов на {len(placed_layouts)} листах"
        )

        for layout_idx, layout in enumerate(placed_layouts):
            if not remaining_polygons_list:
                break

            sheet_size = layout["sheet_size"]
            existing_placed = layout["placed_polygons"]
            current_usage = layout["usage_percent"]

            if current_usage >= 95:  # Skip nearly full sheets
                continue

            logger.info(
                f"Пытаемся дозаполнить лист #{layout['sheet_number']} (заполнение: {current_usage:.1f}%)"
            )

            # Try to place remaining polygons on this existing sheet
            try:
                additional_placed, still_remaining = bin_packing_with_existing(
                    remaining_polygons_list, existing_placed, sheet_size, verbose=False
                )

                if additional_placed:
                    # Update the layout with additional polygons
                    placed_layouts[layout_idx]["placed_polygons"] = (
                        existing_placed + additional_placed
                    )
                    placed_layouts[layout_idx]["usage_percent"] = (
                        calculate_usage_percent(
                            placed_layouts[layout_idx]["placed_polygons"], sheet_size
                        )
                    )

                    new_usage = placed_layouts[layout_idx]["usage_percent"]
                    logger.info(
                        f"✅ Дозаполнен лист #{layout['sheet_number']}: +{len(additional_placed)} деталей ({current_usage:.1f}% → {new_usage:.1f}%)"
                    )

                    if verbose:
                        st.success(
                            f"✅ Дозаполнен лист #{layout['sheet_number']}: +{len(additional_placed)} деталей ({current_usage:.1f}% → {new_usage:.1f}%)"
                        )

                    # Update remaining polygons list
                    remaining_polygons_list = still_remaining

                else:
                    logger.info(f"Лист #{layout['sheet_number']} нельзя дозаполнить")
            except Exception as e:
                logger.warning(
                    f"Ошибка при дозаполнении листа #{layout['sheet_number']}: {e}"
                )

    # Add any remaining unplaced polygons to the unplaced list
    all_unplaced.extend(remaining_polygons_list)

    logger.info("=== ОКОНЧАНИЕ bin_packing_with_inventory ===")
    logger.info(
        f"ИТОГОВЫЙ РЕЗУЛЬТАТ: {len(placed_layouts)} листов использовано, {len(all_unplaced)} объектов не размещено"
    )

    logger.info("Финальное распределение по заказам:")
    for order_id, sheets_used in order_sheet_usage.items():
        logger.info(f"  • Заказ {order_id}: {sheets_used} листов")

    if verbose:
        st.info(
            f"Размещение завершено: {len(placed_layouts)} листов использовано, {len(all_unplaced)} объектов не размещено"
        )

        # Show summary by orders using the tracked usage
        if order_sheet_usage:
            st.success("✅ Распределение по заказам:")
            for order_id, sheet_count in order_sheet_usage.items():
                if order_id != "unknown":  # Only show real orders
                    status = (
                        "✅"
                        if sheet_count <= (max_sheets_per_order or float("inf"))
                        else "❌"
                    )
                    st.info(f"  {status} Заказ {order_id}: {sheet_count} листов")

    return placed_layouts, all_unplaced


def calculate_usage_percent(
    placed_polygons: list[tuple], sheet_size: tuple[float, float]
) -> float:
    """Calculate material usage percentage for a sheet."""
    used_area_mm2 = sum(placed_tuple[0].area for placed_tuple in placed_polygons)
    sheet_area_mm2 = (sheet_size[0] * 10) * (sheet_size[1] * 10)
    return (used_area_mm2 / sheet_area_mm2) * 100


def save_dxf_layout(
    placed_polygons: list[tuple[Polygon, float, float, float, str]],
    sheet_size: tuple[float, float],
    output_path: str,
    original_dxf_data_map=None,
):
    """Save the optimized layout using original DXF elements without artifacts."""
    # Redirect to the complete function that handles original entities properly
    if original_dxf_data_map:
        return save_dxf_layout_complete(
            placed_polygons, sheet_size, output_path, original_dxf_data_map
        )
    else:
        # Fallback to simple polygon boundaries if no original data available
        doc = ezdxf.new("R2010")
        doc.header["$INSUNITS"] = 4  # 4 = millimeters
        doc.header["$LUNITS"] = 2  # 2 = decimal units
        msp = doc.modelspace()

        # DO NOT add sheet boundary - it's an artifact

        # Add only the polygon boundaries without artifacts
        for placed_tuple in placed_polygons:
            if len(placed_tuple) >= 6:  # New format with color
                polygon, _, _, _, file_name, color = placed_tuple[:6]
            else:  # Old format without color
                polygon, _, _, _, file_name = placed_tuple[:5]

            # Use simple layer names without file prefixes
            points = list(polygon.exterior.coords)[:-1]
            layer_name = "layer_1"  # Default layer name without artifacts
            msp.add_lwpolyline(points, dxfattribs={"layer": layer_name})

        doc.saveas(output_path)
        return output_path


def plot_layout(
    placed_polygons: list[tuple[Polygon, float, float, float, str]],
    sheet_size: tuple[float, float],
) -> BytesIO:
    """Plot the layout using matplotlib and return as BytesIO."""
    fig, ax = plt.subplots(figsize=(10, 8))

    # Convert sheet size from cm to mm for proper scaling
    sheet_width_mm = sheet_size[0] * 10
    sheet_height_mm = sheet_size[1] * 10

    ax.set_xlim(0, sheet_width_mm)
    ax.set_ylim(0, sheet_height_mm)
    ax.set_aspect("equal")

    # Draw sheet boundary
    sheet_boundary = plt.Rectangle(
        (0, 0),
        sheet_width_mm,
        sheet_height_mm,
        fill=False,
        edgecolor="black",
        linewidth=2,
        linestyle="--",
    )
    ax.add_patch(sheet_boundary)

    # Use consistent colors for each file
    for placed_tuple in placed_polygons:
        if len(placed_tuple) >= 6:  # New format with color
            polygon, _, _, angle, file_name, color = placed_tuple[:6]
        else:  # Old format without color
            polygon, _, _, angle, file_name = placed_tuple[:5]
            color = "серый"
        x, y = polygon.exterior.xy
        # Use file-based color for visualization consistency
        display_color = get_color_for_file(file_name)
        ax.fill(
            x,
            y,
            alpha=0.7,
            color=display_color,
            edgecolor="black",
            linewidth=1,
            label=f"{file_name} ({angle:.0f}°) - {color}",
        )

        # Add file name at polygon centroid
        centroid = polygon.centroid
        ax.annotate(
            file_name.replace(".dxf", ""),
            (centroid.x, centroid.y),
            ha="center",
            va="center",
            fontsize=8,
            weight="bold",
        )

    ax.legend(bbox_to_anchor=(1.05, 1), loc="upper left")
    ax.set_title(f"Раскрой на листе {sheet_size[0]} × {sheet_size[1]} см")
    ax.set_xlabel("Ширина (мм)")
    ax.set_ylabel("Высота (мм)")
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    buf = BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight", dpi=150)
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
        color = "lightblue"

    # Plot the polygon
    x, y = polygon.exterior.xy
    ax.fill(x, y, alpha=0.7, color=color, edgecolor="darkblue", linewidth=2)

    # Add some padding around the polygon
    bounds = polygon.bounds
    padding = 0.1 * max(bounds[2] - bounds[0], bounds[3] - bounds[1])
    ax.set_xlim(bounds[0] - padding, bounds[2] + padding)
    ax.set_ylim(bounds[1] - padding, bounds[3] + padding)
    ax.set_aspect("equal")

    # Add polygon center point
    centroid = polygon.centroid
    ax.plot(centroid.x, centroid.y, "ro", markersize=5, label="Центр")

    # Convert from DXF units (mm) to cm
    width_mm = bounds[2] - bounds[0]
    height_mm = bounds[3] - bounds[1]
    width_cm = width_mm / 10.0
    height_cm = height_mm / 10.0
    area_cm2 = polygon.area / 100.0  # mm² to cm²

    ax.set_title(
        f"{title}\nРеальные размеры: {width_cm:.1f} × {height_cm:.1f} см\nПлощадь: {area_cm2:.2f} см²"
    )
    ax.set_xlabel("X координата (мм)")
    ax.set_ylabel("Y координата (мм)")
    ax.grid(True, alpha=0.3)
    ax.legend()

    plt.tight_layout()
    buf = BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight", dpi=150)
    plt.close()
    buf.seek(0)
    return buf


def plot_input_polygons(
    polygons_with_names: list[tuple[Polygon, str]],
) -> dict[str, BytesIO]:
    """Create individual plots for each DXF file."""
    if not polygons_with_names:
        return {}

    plots = {}
    for polygon_tuple in polygons_with_names:
        if len(polygon_tuple) >= 3:  # New format with color
            polygon, file_name, color = polygon_tuple[:3]
        else:  # Old format without color
            polygon, file_name = polygon_tuple[:2]
            color = "серый"

        plot_buf = plot_single_polygon(
            polygon, f"Файл: {file_name} (цвет: {color})", filename=file_name
        )
        plots[file_name] = plot_buf

    return plots


def scale_polygons_to_fit(
    polygons_with_names: list[tuple],
    sheet_size: tuple[float, float],
    verbose: bool = True,
) -> list[tuple]:
    """Scale polygons to fit better on the sheet if they are too large."""
    if not polygons_with_names:
        return polygons_with_names

    # Convert sheet size from cm to mm to match DXF units
    sheet_width_mm, sheet_height_mm = sheet_size[0] * 10, sheet_size[1] * 10
    scaled_polygons = []

    # First, find the overall scale factor needed (all in mm)
    max_width = max(
        (poly_tuple[0].bounds[2] - poly_tuple[0].bounds[0])
        for poly_tuple in polygons_with_names
    )
    max_height = max(
        (poly_tuple[0].bounds[3] - poly_tuple[0].bounds[1])
        for poly_tuple in polygons_with_names
    )

    # Calculate a global scale factor only if polygons are too large for the sheet
    # Only scale if polygons are larger than 90% of sheet size
    global_scale_x = (
        (sheet_width_mm * 0.9) / max_width if max_width > sheet_width_mm * 0.9 else 1.0
    )
    global_scale_y = (
        (sheet_height_mm * 0.9) / max_height
        if max_height > sheet_height_mm * 0.9
        else 1.0
    )
    global_scale = min(global_scale_x, global_scale_y, 1.0)

    if global_scale < 1.0 and verbose:
        st.info(
            f"Применяем глобальный масштабный коэффициент {global_scale:.4f} ко всем полигонам"
        )

    for polygon_tuple in polygons_with_names:
        if len(polygon_tuple) >= 4:  # Extended format with color and order_id
            polygon, name, color, order_id = polygon_tuple[:4]
        elif len(polygon_tuple) >= 3:  # Format with color
            polygon, name, color = polygon_tuple[:3]
            order_id = "unknown"
        else:  # Old format without color
            polygon, name = polygon_tuple[:2]
            color = "серый"
            order_id = "unknown"
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
            scaled_polygon = affinity.scale(
                polygon,
                xfact=scale_factor,
                yfact=scale_factor,
                origin=(centroid.x, centroid.y),
            )

            # Also translate to origin area to avoid negative coordinates
            scaled_bounds = scaled_polygon.bounds
            if scaled_bounds[0] < 0 or scaled_bounds[1] < 0:
                translate_x = -scaled_bounds[0] if scaled_bounds[0] < 0 else 0
                translate_y = -scaled_bounds[1] if scaled_bounds[1] < 0 else 0
                scaled_polygon = affinity.translate(
                    scaled_polygon, xoff=translate_x, yoff=translate_y
                )

            if verbose:
                # Show dimensions in cm for user-friendly display
                original_width_cm = poly_width / 10.0
                original_height_cm = poly_height / 10.0
                new_width_cm = (
                    scaled_polygon.bounds[2] - scaled_polygon.bounds[0]
                ) / 10.0
                new_height_cm = (
                    scaled_polygon.bounds[3] - scaled_polygon.bounds[1]
                ) / 10.0
                st.info(
                    f"Масштабирован {name}: {original_width_cm:.1f}x{original_height_cm:.1f} см → {new_width_cm:.1f}x{new_height_cm:.1f} см (коэффициент: {scale_factor:.4f})"
                )
            scaled_polygons.append((scaled_polygon, name, color, order_id))
        else:
            scaled_polygons.append((polygon, name, color, order_id))

    return scaled_polygons


# Verification that all functions are properly defined
def _verify_functions():
    """Verify that all required functions are defined in the module."""
    required_functions = [
        "get_color_for_file",
        "parse_dxf",
        "rotate_polygon",
        "translate_polygon",
        "place_polygon_at_origin",
        "check_collision",
        "bin_packing",
        "bin_packing_with_inventory",
        "calculate_usage_percent",
        "save_dxf_layout",
        "plot_layout",
        "plot_single_polygon",
        "plot_input_polygons",
        "scale_polygons_to_fit",
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
