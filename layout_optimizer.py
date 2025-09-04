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

logging.getLogger("ezdxf").setLevel(logging.ERROR)

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


def get_color_for_file(filename):
    """Generate a consistent color for a given filename."""
    # Handle case where filename might be a float64 or other non-string type
    if isinstance(filename, (int, float)):
        filename = str(filename)
    elif filename is None:
        filename = "unknown"
    
    # Use hash of filename to generate consistent color
    hash_object = hashlib.md5(str(filename).encode())
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
            # Enhanced polygon validation and filtering
            if polygon:  # and polygon.area > 0.1:
                # Try to fix invalid polygons using buffer(0)
                if not polygon.is_valid:
                    fixed_polygon = polygon.buffer(0)
                    if fixed_polygon.is_valid:  # and fixed_polygon.area > 0.1:
                        polygon = fixed_polygon
                        if verbose:
                            st.info(
                                "   🔧 Исправлен невалидный полигон с помощью buffer(0)"
                            )
                    else:
                        if verbose:
                            st.warning("   ❌ Не удалось исправить невалидный полигон")
                        continue
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


def save_dxf_layout_complete(
    placed_elements, sheet_size, output_path, original_dxf_data_map=None
):
    """COMPLETELY CORRECTED - Use coordinate mapping from original to transformed polygon"""

    print(
        f"🔧 CORRECTED save_dxf_layout_complete called with {len(placed_elements)} elements"
    )
    print(f"🔧 Output path: {output_path}")
    print(f"🔧 Sheet size: {sheet_size}")

    # Create new DXF document
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4  # millimeters
    doc.header["$LUNITS"] = 2  # decimal units
    msp = doc.modelspace()

    for placed_element in placed_elements:
        if len(placed_element) >= 6:
            (
                transformed_polygon,
                x_offset,
                y_offset,
                rotation_angle,
                file_name,
                color,
            ) = placed_element[:6]
        else:
            transformed_polygon, x_offset, y_offset, rotation_angle, file_name = (
                placed_element[:5]
            )

        print(
            f"🔧 Processing {file_name}: transformed bounds = {transformed_polygon.bounds}"
        )

        # Get original DXF data
        # Handle case where file_name might be a float64 or other non-string type
        if isinstance(file_name, (int, float)):
            file_name = str(file_name)
        file_basename = os.path.basename(file_name) if file_name else str(file_name)
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
                scale_direct = (
                    min(target_width / orig_width, target_height / orig_height)
                    if orig_width > 0 and orig_height > 0
                    else 1.0
                )
                scale_swapped = (
                    min(target_width / orig_height, target_height / orig_width)
                    if orig_width > 0 and orig_height > 0
                    else 1.0
                )

                # Choose the scale that makes more sense based on rotation
                if rotation_angle % 180 == 90:  # 90° or 270° rotation
                    scale_factor = scale_swapped
                else:  # 0° or 180° rotation
                    scale_factor = scale_direct

                print(
                    f"🔧 Rotation: {rotation_angle}°, Scale factor: {scale_factor:.3f}"
                )
                print(f"🔧 Original bounds: {orig_bounds}")
                print(f"🔧 Target bounds: {target_bounds}")

                # Calculate centers
                orig_center_x = (orig_bounds[0] + orig_bounds[2]) / 2
                orig_center_y = (orig_bounds[1] + orig_bounds[3]) / 2
                target_center_x = (target_bounds[0] + target_bounds[2]) / 2
                target_center_y = (target_bounds[1] + target_bounds[3]) / 2

                # For rotation calculations
                rotation_rad = (
                    math.radians(rotation_angle) if rotation_angle != 0 else 0
                )
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
                        if (
                            hasattr(new_entity, "control_points")
                            and new_entity.control_points
                        ):
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
                                    x_rotated = (
                                        x_scaled * cos_angle - y_scaled * sin_angle
                                    )
                                    y_rotated = (
                                        x_scaled * sin_angle + y_scaled * cos_angle
                                    )
                                else:
                                    x_rotated = x_scaled
                                    y_rotated = y_scaled

                                # 4. Translate to final position (target center)
                                final_x = x_rotated + target_center_x
                                final_y = y_rotated + target_center_y

                                transformed_points.append((final_x, final_y, z))

                            if transformed_points:
                                from ezdxf.math import Vec3

                                new_control_points = [
                                    Vec3(x, y, z) for x, y, z in transformed_points
                                ]
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

                        new_entity.dxf.center = (
                            final_x,
                            final_y,
                            orig_center[2] if len(orig_center) > 2 else 0,
                        )
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

                        new_entity.dxf.center = (
                            final_x,
                            final_y,
                            orig_center[2] if len(orig_center) > 2 else 0,
                        )
                        new_entity.dxf.radius = new_entity.dxf.radius * scale_factor

                        # Adjust angles for rotation
                        if rotation_angle != 0:
                            new_entity.dxf.start_angle = (
                                new_entity.dxf.start_angle + rotation_angle
                            ) % 360
                            new_entity.dxf.end_angle = (
                                new_entity.dxf.end_angle + rotation_angle
                            ) % 360

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

                            transformed_points.append(
                                (
                                    final_x,
                                    final_y,
                                    bulge,
                                    start_width * scale_factor,
                                    end_width * scale_factor,
                                )
                            )

                        # Clear existing points and add transformed ones
                        new_entity.clear()
                        for tp in transformed_points:
                            new_entity.append(
                                tp[:2],
                                format="xyb" if len(tp) > 2 and tp[2] != 0 else "xy",
                            )
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

                        new_entity.dxf.center = (
                            final_x,
                            final_y,
                            orig_center[2] if len(orig_center) > 2 else 0,
                        )

                        # Scale and rotate major axis
                        orig_major_axis = new_entity.dxf.major_axis
                        major_x_scaled = orig_major_axis[0] * scale_factor
                        major_y_scaled = orig_major_axis[1] * scale_factor

                        if rotation_angle != 0:
                            major_x_rotated = (
                                major_x_scaled * cos_angle - major_y_scaled * sin_angle
                            )
                            major_y_rotated = (
                                major_x_scaled * sin_angle + major_y_scaled * cos_angle
                            )
                        else:
                            major_x_rotated = major_x_scaled
                            major_y_rotated = major_y_scaled

                        new_entity.dxf.major_axis = (
                            major_x_rotated,
                            major_y_rotated,
                            orig_major_axis[2] if len(orig_major_axis) > 2 else 0,
                        )
                        new_entity.dxf.ratio = (
                            new_entity.dxf.ratio
                        )  # Keep ratio unchanged

                    elif entity_type in ["LINE", "POINT", "TEXT", "MTEXT", "DIMENSION"]:
                        # For other common entity types, apply basic transformation
                        # This is a simplified approach - you might need more specific handling
                        if hasattr(new_entity.dxf, "location"):
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

                        elif hasattr(new_entity.dxf, "start") and hasattr(
                            new_entity.dxf, "end"
                        ):
                            # Handle LINE entities
                            for attr_name in ["start", "end"]:
                                orig_point = getattr(new_entity.dxf, attr_name)
                                x, y = orig_point[0], orig_point[1]
                                z = orig_point[2] if len(orig_point) > 2 else 0

                                x_rel = x - orig_center_x
                                y_rel = y - orig_center_y

                                x_scaled = x_rel * scale_factor
                                y_scaled = y_rel * scale_factor

                                if rotation_angle != 0:
                                    x_rotated = (
                                        x_scaled * cos_angle - y_scaled * sin_angle
                                    )
                                    y_rotated = (
                                        x_scaled * sin_angle + y_scaled * cos_angle
                                    )
                                else:
                                    x_rotated = x_scaled
                                    y_rotated = y_scaled

                                final_x = x_rotated + target_center_x
                                final_y = y_rotated + target_center_y

                                setattr(
                                    new_entity.dxf, attr_name, (final_x, final_y, z)
                                )

                    # Set layer and add to modelspace
                    new_entity.dxf.layer = entity_data["layer"]

                    # Set color: keep red range as is, make everything else black (7)
                    original_color = entity_data.get("color", 256)

                    # Check if color is in red range: 1, 10-19, 240-255
                    is_red = (
                        original_color in [1, 6]
                        or 10 <= original_color <= 26
                        or 190 <= original_color < 250
                    )

                    if is_red:
                        new_entity.dxf.color = 1  # Set the one and only red color
                    else:
                        new_entity.dxf.color = 0  # Make everything else black

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
    max_attempts: int = 100,  # Reduced from 1000 to 100 for speed
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
    max_attempts: int = 100,  # Reduced from 1000 to 100 for speed
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
    progress_callback=None,
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

    # Group polygons by order_id and separate by priority
    logger.info("Группировка полигонов по order_id и приоритету...")
    order_groups = {}
    priority2_polygons = []  # Polygons with priority 2 for later processing

    for polygon_tuple in polygons:
        if (
            len(polygon_tuple) >= 5
        ):  # Extended format with color, order_id, and priority
            polygon, name, color, order_id, priority = polygon_tuple[:5]
        elif len(polygon_tuple) >= 4:  # Format with color and order_id
            polygon, name, color, order_id = polygon_tuple[:4]
            priority = 1  # Default priority
        elif len(polygon_tuple) >= 3:  # Format with color
            polygon, name, color = polygon_tuple[:3]
            order_id = "unknown"
            priority = 1  # Default priority
        else:  # Old format without color
            polygon, name = polygon_tuple[:2]
            color = "серый"
            order_id = "unknown"
            priority = 1  # Default priority

        # Separate priority 2 polygons for later processing
        if priority == 2:
            priority2_polygons.append(polygon_tuple)
            logger.debug(f"Полигон {name} отложен для приоритета 2 (заполнение пустот)")
        else:
            # Process priority 1 and Excel files normally
            if order_id not in order_groups:
                order_groups[order_id] = []
                logger.debug(f"Создана новая группа для заказа: {order_id}")
            order_groups[order_id].append(polygon_tuple)

    logger.info(
        f"Группировка завершена: {len(order_groups)} уникальных заказов, {len(priority2_polygons)} полигонов приоритета 2"
    )
    for order_id, group in order_groups.items():
        logger.info(f"  • Заказ {order_id}: {len(group)} файлов")
    if priority2_polygons:
        logger.info(
            f"  • Приоритет 2 (заполнение пустот): {len(priority2_polygons)} файлов"
        )

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

    # Check if we only have priority 2 polygons
    if not order_groups and priority2_polygons:
        logger.info(
            f"Только файлы приоритета 2: {len(priority2_polygons)} файлов не размещаются (новые листы не создаются)"
        )
        if verbose:
            st.warning(
                f"⚠️ Только файлы приоритета 2: {len(priority2_polygons)} файлов не размещаются (новые листы не создаются)"
            )
        all_unplaced.extend(priority2_polygons)
        
        # Progress update for early return
        if progress_callback:
            progress_callback(100, "Завершено: только файлы приоритета 2 (не размещены)")
        
        return placed_layouts, all_unplaced

    # NEW LOGIC: Priority queue for orders based on MAX_SHEETS_PER_ORDER constraint
    # Track which order was placed first and its starting sheet
    order_first_sheet = {}  # order_id -> first_sheet_number
    
    # Process orders using priority queue logic
    remaining_orders = dict(order_groups)  # Copy to modify
    max_iterations = max(
        100, len(remaining_orders) * 50
    )  # Safety limit with higher multiplier
    iteration_count = 0

    while remaining_orders and any(
        sheet["count"] - sheet["used"] > 0 for sheet in sheet_inventory
    ):
        iteration_count += 1
        logger.info(f"--- ИТЕРАЦИЯ {iteration_count} ---")
        logger.info(f"Остается заказов: {len(remaining_orders)}")
        for order_id, polygons in remaining_orders.items():
            logger.info(f"  {order_id}: {len(polygons)} полигонов")
        
        # ENHANCED STRATEGY: Try to fill existing sheets FIRST before creating new ones
        # ОТКЛЮЧЕНО: старая логика дозаполнения - теперь используем новый алгоритм выше
        if False and placed_layouts:  # Only if we have existing sheets
            logger.info("🔄 ПРОВЕРЯЕМ ДОЗАПОЛНЕНИЕ СУЩЕСТВУЮЩИХ ЛИСТОВ")
            
            # Find single-polygon orders that can be added to existing sheets
            single_polygon_orders = {
                order_id: order_polygons
                for order_id, order_polygons in remaining_orders.items()
                if len(order_polygons) == 1
            }
            
            if single_polygon_orders:
                logger.info(f"Найдено {len(single_polygon_orders)} однополигонных заказов для дозаполнения")
                
                filled_orders = 0
                for order_id, order_polygons in single_polygon_orders.items():
                    polygon_tuple = order_polygons[0]
                    color = polygon_tuple[2] if len(polygon_tuple) >= 3 else "серый"
                    
                    # Try to place this single polygon on existing sheets with same color
                    placed_successfully = False
                    for layout_idx, existing_layout in enumerate(placed_layouts):
                        sheet_color = existing_layout.get("sheet_color", "серый")
                        if color != sheet_color:
                            continue
                            
                        current_usage = existing_layout.get("usage_percent", 0)
                        if current_usage >= 85:  # Skip nearly full sheets
                            continue
                            
                        sheet_size = existing_layout["sheet_size"]
                        existing_placed = existing_layout["placed_polygons"]
                        
                        logger.info(f"Пытаемся дозаполнить лист #{existing_layout['sheet_number']} заказом {order_id}")
                        
                        try:
                            additional_placed, still_remaining = bin_packing_with_existing(
                                [polygon_tuple], existing_placed, sheet_size, verbose=False
                            )
                            
                            if additional_placed:
                                # Update existing layout
                                placed_layouts[layout_idx]["placed_polygons"] = existing_placed + additional_placed
                                new_usage = calculate_usage_percent(
                                    placed_layouts[layout_idx]["placed_polygons"], sheet_size
                                )
                                placed_layouts[layout_idx]["usage_percent"] = new_usage
                                
                                # Update orders_on_sheet set
                                if "orders_on_sheet" not in placed_layouts[layout_idx]:
                                    placed_layouts[layout_idx]["orders_on_sheet"] = set()
                                placed_layouts[layout_idx]["orders_on_sheet"].add(order_id)
                                
                                # Track sheet usage for this order
                                if order_id not in order_sheet_usage:
                                    order_sheet_usage[order_id] = 0
                                order_sheet_usage[order_id] = 1
                                
                                # Track order first sheet
                                if order_id not in order_first_sheet:
                                    order_first_sheet[order_id] = existing_layout['sheet_number']
                                
                                filled_orders += 1
                                placed_successfully = True
                                
                                logger.info(
                                    f"✅ ДОЗАПОЛНЕНИЕ УСПЕШНО: Заказ {order_id} размещен на лист #{existing_layout['sheet_number']} ({current_usage:.1f}% → {new_usage:.1f}%)"
                                )
                                break
                        except Exception as e:
                            logger.debug(f"Не удалось дозаполнить лист #{existing_layout['sheet_number']}: {e}")
                            continue
                    
                    if placed_successfully:
                        # Remove this order from remaining_orders
                        del remaining_orders[order_id]
                
                if filled_orders > 0:
                    logger.info(f"Дозаполнение завершено: {filled_orders} заказов размещено на существующих листах")
                    placed_on_current_sheet = True
                    continue  # Skip to next iteration, don't create new sheets
        
        # If no orders were filled by existing sheets, proceed with normal sheet creation

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
            
            # Calculate which sheet number this would be
            next_sheet_number = sheet_counter + 1

            # NEW APPROACH: Reserve sheets for started orders to guarantee completion
            # Step 1: Check which started orders need priority on this sheet
            priority_orders = []
            blocked_orders = []
            new_orders = []
            
            for order_id, order_polygons in remaining_orders.items():
                # Skip orders that don't apply to MAX_SHEETS_PER_ORDER constraint
                is_constrained = (
                    max_sheets_per_order is not None
                    and order_id != "additional"
                    and order_id != "unknown"  # Manual uploads are not limited
                    and not str(order_id).startswith("group_")  # Group uploads are not limited
                )
                
                if not is_constrained:
                    # Unconstrained orders can be placed anytime
                    new_orders.append((order_id, order_polygons))
                    continue
                
                if order_id in order_first_sheet:
                    # Order already started - check if within range
                    first_sheet = order_first_sheet[order_id]
                    max_allowed_sheet = first_sheet + max_sheets_per_order - 1
                    
                    if next_sheet_number <= max_allowed_sheet:
                        # Within range - MAXIMUM priority (must complete this order)
                        priority_orders.append((order_id, order_polygons))
                        logger.debug(
                            f"Заказ {order_id}: МАКСИМАЛЬНЫЙ приоритет (листы {first_sheet}-{max_allowed_sheet}, текущий {next_sheet_number})"
                        )
                    else:
                        # Outside range - blocked from starting new placement
                        blocked_orders.append(order_id)
                        logger.debug(
                            f"Заказ {order_id}: ЗАБЛОКИРОВАН (вне диапазона {first_sheet}-{max_allowed_sheet}, текущий {next_sheet_number})"
                        )
                else:
                    # New order - can start only if no priority orders need this sheet
                    new_orders.append((order_id, order_polygons))
            
            # PRIORITY STRATEGY: If there are started orders within range, give them ALL the space
            if priority_orders:
                # Only consider priority orders - they get the entire sheet
                orders_to_consider = priority_orders
                logger.info(
                    f"Лист {next_sheet_number}: РЕЖИМ ПРИОРИТЕТА - {len(priority_orders)} начатых заказов"
                )
            else:
                # No priority orders - allow new orders to start  
                # IMPROVED STRATEGY: Sort new orders by carpet count (descending)
                # Orders with more carpets should be processed first as they are harder to fit within MAX_SHEETS_PER_ORDER constraint
                new_orders_sorted = sorted(new_orders, key=lambda x: len(x[1]), reverse=True)
                orders_to_consider = new_orders_sorted
                logger.info(
                    f"Лист {next_sheet_number}: Обычный режим - {len(new_orders_sorted)} новых заказов (отсортированы по убыванию количества ковров)"
                )
                # Log order sorting for debugging
                for order_id, order_polygons in new_orders_sorted[:5]:  # Show top 5
                    logger.debug(f"  Заказ {order_id}: {len(order_polygons)} ковров")
                if len(new_orders_sorted) > 5:
                    logger.debug(f"  ... еще {len(new_orders_sorted) - 5} заказов")

            # Collect polygons from orders that can fit on this sheet
            compatible_polygons = []
            orders_to_try = []

            for order_id, order_polygons in orders_to_consider:
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
                logger.debug(
                    f"Нет совместимых полигонов для листа {sheet_type['name']} цвета {sheet_color}"
                )
                continue  # No compatible polygons for this sheet color

            # NEW STRATEGY: Try to fill existing sheets BEFORE creating a new one
            filled_existing_sheet = False
            logger.info("🚀 НОВЫЙ АЛГОРИТМ: Попытка дозаполнить существующие листы")
            
            # Try to add compatible polygons to existing sheets of the same color first
            for layout_idx, existing_layout in enumerate(placed_layouts):
                if existing_layout.get("sheet_color") == sheet_color:
                    current_usage = existing_layout.get("usage_percent", 0)
                    
                    # Skip nearly full sheets (>90%) to avoid tiny gaps
                    if current_usage >= 90:
                        continue
                        
                    existing_placed = existing_layout["placed_polygons"]
                    sheet_size = existing_layout["sheet_size"]
                    
                    logger.debug(f"Пытаемся дозаполнить лист #{existing_layout['sheet_number']} (заполнение: {current_usage:.1f}%)")
                    
                    try:
                        additional_placed, still_remaining = bin_packing_with_existing(
                            compatible_polygons, existing_placed, sheet_size, verbose=False
                        )
                        
                        if additional_placed:
                            logger.info(f"✅ ДОЗАПОЛНЕНИЕ: Лист #{existing_layout['sheet_number']} получил +{len(additional_placed)} полигонов ({current_usage:.1f}% → {calculate_usage_percent(existing_placed + additional_placed, sheet_size):.1f}%)")
                            
                            # Update existing layout
                            placed_layouts[layout_idx]["placed_polygons"] = existing_placed + additional_placed
                            placed_layouts[layout_idx]["usage_percent"] = calculate_usage_percent(
                                placed_layouts[layout_idx]["placed_polygons"], sheet_size
                            )
                            
                            # Track orders and remove placed polygons from remaining orders
                            additional_orders_on_sheet = set()
                            for placed_tuple in additional_placed:
                                # Handle different tuple structures for order_id
                                if len(placed_tuple) == 7:
                                    # Extended format from bin_packing_with_existing: (polygon, x, y, angle, file_name, color, order_id)
                                    placed_order_id = placed_tuple[6]
                                elif len(placed_tuple) > 3:
                                    # Standard format: (polygon, file_name, color, order_id)
                                    placed_order_id = placed_tuple[3]
                                else:
                                    placed_order_id = "unknown"
                                additional_orders_on_sheet.add(placed_order_id)
                                
                                # Update order sheet tracking
                                if placed_order_id not in order_sheet_usage:
                                    order_sheet_usage[placed_order_id] = 0
                                if placed_order_id not in order_first_sheet:
                                    order_first_sheet[placed_order_id] = existing_layout['sheet_number']
                            
                            # Remove placed polygons from compatible_polygons for next iterations
                            # ИСПРАВЛЕНИЕ: точечное совпадение по 3 полям вместо set-сравнения
                            # Из-за разной длины кортежей (4 vs 7) set-сравнение всегда возвращало False
                            placed_keys = set()
                            for placed_poly in additional_placed:
                                if len(placed_poly) >= 5:
                                    # Полигон из bin_packing_with_existing: (polygon, x, y, angle, filename, color, order_id)
                                    key = (placed_poly[4], placed_poly[5], placed_poly[6])  # filename, color, order_id
                                else:
                                    # Обычный полигон: (polygon, filename, color, order_id)
                                    key = (placed_poly[1], placed_poly[2], placed_poly[3])
                                placed_keys.add(key)
                            
                            # Удаляем полигоны с совпадающими ключами
                            compatible_polygons = [
                                p for p in compatible_polygons 
                                if (p[1], p[2], p[3]) not in placed_keys
                            ]
                            
                            # Update remaining orders - remove empty orders or reduce polygon counts
                            for order_id in list(remaining_orders.keys()):
                                if order_id in additional_orders_on_sheet:
                                    # Count how many polygons from this order were placed
                                    # ИСПРАВЛЕНИЕ: правильно извлекаем order_id из разных форматов кортежей
                                    placed_from_order = []
                                    for p in additional_placed:
                                        poly_order_id = None
                                        if len(p) >= 5:
                                            # Полигон из bin_packing_with_existing: (polygon, x, y, angle, filename, color, order_id)
                                            poly_order_id = p[6] if len(p) > 6 else None
                                        else:
                                            # Обычный полигон: (polygon, filename, color, order_id)
                                            poly_order_id = p[3] if len(p) > 3 else None
                                        
                                        if poly_order_id == order_id:
                                            placed_from_order.append(p)
                                    
                                    # Remove exactly those polygons that were placed
                                    # ИСПРАВЛЕНИЕ: учитываем правильный формат кортежей
                                    for placed_poly in placed_from_order:
                                        # Извлекаем ключ из размещенного полигона
                                        if len(placed_poly) >= 5:
                                            # Полигон из bin_packing_with_existing: (polygon, x, y, angle, filename, color, order_id)
                                            placed_key = (placed_poly[4], placed_poly[5], placed_poly[6])
                                        else:
                                            # Обычный полигон: (polygon, filename, color, order_id)
                                            placed_key = (placed_poly[1], placed_poly[2], placed_poly[3])
                                        
                                        for orig_tuple in remaining_orders[order_id][:]:
                                            # Сравниваем по ключу (filename, color, order_id)
                                            orig_key = (orig_tuple[1], orig_tuple[2], orig_tuple[3])
                                            if orig_key == placed_key:
                                                remaining_orders[order_id].remove(orig_tuple)
                                                break
                                    
                                    # Remove empty orders
                                    if not remaining_orders[order_id]:
                                        logger.info(f"  Заказ {order_id} полностью размещен (дозаполнение)")
                                        del remaining_orders[order_id]
                            
                            # Update orders on this sheet
                            if "orders_on_sheet" not in placed_layouts[layout_idx]:
                                placed_layouts[layout_idx]["orders_on_sheet"] = set()
                            placed_layouts[layout_idx]["orders_on_sheet"].update(additional_orders_on_sheet)
                            
                            filled_existing_sheet = True
                            placed_on_current_sheet = True
                            
                            if verbose:
                                st.success(f"✅ Дозаполнен лист #{existing_layout['sheet_number']}: +{len(additional_placed)} деталей")
                            
                            break  # Found space, don't need to create new sheet yet
                            
                    except Exception as e:
                        logger.debug(f"Не удалось дозаполнить лист #{existing_layout['sheet_number']}: {e}")
                        continue
            
            # If we filled an existing sheet, continue to next iteration without creating new sheet
            if filled_existing_sheet:
                continue

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

                # Update order sheet usage and track first sheet
                for order_id in orders_on_sheet:
                    if order_id in order_sheet_usage:
                        order_sheet_usage[order_id] += 1
                        
                        # Track first sheet for MAX_SHEETS_PER_ORDER constraint
                        if order_id not in order_first_sheet:
                            order_first_sheet[order_id] = sheet_counter
                            logger.info(
                                f"  Заказ {order_id}: начат на листе {sheet_counter}"
                            )
                        
                        logger.info(
                            f"  Заказ {order_id}: теперь использует {order_sheet_usage[order_id]} листов"
                        )

                placed_layouts.append(
                    {
                        "sheet_number": sheet_counter,
                        "sheet_type": sheet_type["name"],
                        "sheet_color": sheet_color,  # Add sheet color directly
                        "sheet_size": sheet_size,
                        "placed_polygons": placed,
                        "usage_percent": calculate_usage_percent(placed, sheet_size),
                        "orders_on_sheet": list(orders_on_sheet),
                    }
                )
                
                # Update progress callback if provided
                if progress_callback:
                    # Better estimate based on actual polygons and sheet capacity
                    total_priority1_polygons = len([p for order_polys in order_groups.values() for p in order_polys])
                    # Estimate sheets needed based on average usage and total polygons
                    estimated_total_sheets = max(1, total_priority1_polygons // 4)  # Assume 4 polygons per sheet on average
                    progress_percent = min(95, 50 + (len(placed_layouts) / max(1, estimated_total_sheets)) * 40)  # 50-95% range
                    progress_callback(progress_percent, f"Создан лист #{sheet_counter} ({sheet_type['name']})")

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
                
                # Enhanced debugging: show what's blocking placement
                logger.info(f"Не удалось разместить в итерации {iteration_count}:")
                logger.info(f"  Доступно листов: {available_sheets_count}")
                logger.info(f"  Осталось заказов: {len(remaining_orders)}")
                
                # Show remaining orders and their polygon counts
                for order_id, order_polygons in remaining_orders.items():
                    colors_in_order = {}
                    for poly_tuple in order_polygons:
                        color = poly_tuple[2] if len(poly_tuple) >= 3 else "серый"
                        colors_in_order[color] = colors_in_order.get(color, 0) + 1
                    logger.info(f"    {order_id}: {len(order_polygons)} полигонов, цвета: {colors_in_order}")
                
                # Show available sheets
                for sheet_type in sheet_inventory:
                    remaining = sheet_type["count"] - sheet_type["used"]
                    if remaining > 0:
                        logger.info(f"    Доступен лист: {sheet_type['name']} цвет {sheet_type.get('color', 'серый')}, осталось: {remaining}")
                
                if verbose:
                    st.info(f"⚠️ Пропуск итерации {iteration_count}: нет совместимых комбинаций полигон/лист")
                    st.info(f"📋 Осталось {len(remaining_orders)} заказов, {available_sheets_count} листов")
                
                continue

    # Check order constraints after placement - both sheet count and adjacency
    violated_orders = []
    adjacency_violations = []
    
    for order_id, sheets_used in order_sheet_usage.items():
        # Check sheet count constraint
        if (
            max_sheets_per_order
            and order_id != "additional"
            and order_id != "unknown"  # Manual uploads are not limited
            and not str(order_id).startswith("group_")  # Group uploads are not limited
            and sheets_used > max_sheets_per_order
        ):
            violated_orders.append((order_id, sheets_used))
            logger.error(
                f"НАРУШЕНИЕ ОГРАНИЧЕНИЙ: Заказ {order_id} использует {sheets_used} листов (лимит: {max_sheets_per_order})"
            )
        
        # Check adjacency constraint
        if (
            max_sheets_per_order
            and order_id != "additional"
            and order_id != "unknown"
            and not str(order_id).startswith("group_")
            and order_id in order_first_sheet
        ):
            first_sheet = order_first_sheet[order_id]
            # Find all sheets where this order appears
            order_sheets = []
            for layout in placed_layouts:
                if order_id in layout["orders_on_sheet"]:
                    order_sheets.append(layout["sheet_number"])
            
            if order_sheets:
                min_sheet = min(order_sheets)
                max_sheet = max(order_sheets)
                expected_max_sheet = first_sheet + max_sheets_per_order - 1
                
                if max_sheet > expected_max_sheet:
                    adjacency_violations.append((order_id, min_sheet, max_sheet, expected_max_sheet))
                    logger.error(
                        f"НАРУШЕНИЕ СМЕЖНОСТИ: Заказ {order_id} размещен на листах {min_sheet}-{max_sheet}, "
                        f"но должен быть в диапазоне {first_sheet}-{expected_max_sheet}"
                    )

    if violated_orders or adjacency_violations:
        warning_parts = []
        if violated_orders:
            warning_parts.append("⚠️ Предупреждение: Нарушение ограничений заказов:")
            for order_id, sheets_used in violated_orders:
                warning_parts.append(f"Заказ {order_id}: {sheets_used} листов (лимит: {max_sheets_per_order})")
        
        if adjacency_violations:
            warning_parts.append("⚠️ Предупреждение: Нарушение смежности листов:")
            for order_id, min_sheet, max_sheet, expected_max in adjacency_violations:
                warning_parts.append(f"Заказ {order_id}: листы {min_sheet}-{max_sheet} (ожидалось до {expected_max})")
        
        warning_msg = "\n".join(warning_parts)
        logger.warning(warning_msg)
        if verbose:
            st.warning(warning_msg)
        # Don't raise error - allow algorithm to continue with warnings

    # NEW: SINGLE-POLYGON ORDER FILL STRATEGY - Try to place remaining single-polygon orders into existing sheets
    if remaining_orders and placed_layouts:
        single_polygon_orders = {
            order_id: order_polygons
            for order_id, order_polygons in remaining_orders.items()
            if len(order_polygons) == 1
        }
        
        if single_polygon_orders:
            logger.info(
                f"=== ДОЗАПОЛНЕНИЕ ОДНОКОМПОНЕНТНЫМИ ЗАКАЗАМИ: {len(single_polygon_orders)} заказов ==="
            )
            if verbose:
                st.info(
                    f"🔄 Дозаполнение листов однокомпонентными заказами: {len(single_polygon_orders)} заказов"
                )
            
            filled_orders = 0
            for order_id, order_polygons in single_polygon_orders.items():
                if len(order_polygons) != 1:
                    continue
                    
                polygon_tuple = order_polygons[0]
                color = polygon_tuple[2] if len(polygon_tuple) >= 3 else "серый"
                
                # Try to place this single polygon on existing sheets with same color
                placed_successfully = False
                for layout_idx, layout in enumerate(placed_layouts):
                    sheet_color = layout.get("sheet_color", "серый")
                    if color != sheet_color:
                        continue
                        
                    current_usage = layout.get("usage_percent", 0)
                    if current_usage >= 95:  # Skip nearly full sheets
                        continue
                        
                    sheet_size = layout["sheet_size"]
                    existing_placed = layout["placed_polygons"]
                    
                    logger.debug(f"Пытаемся добавить {order_id} на лист #{layout['sheet_number']} (заполнение: {current_usage:.1f}%)")
                    
                    try:
                        additional_placed, still_remaining = bin_packing_with_existing(
                            [polygon_tuple], existing_placed, sheet_size, verbose=False
                        )
                        
                        if additional_placed:
                            # Update the layout with the additional polygon
                            placed_layouts[layout_idx]["placed_polygons"] = existing_placed + additional_placed
                            new_usage = calculate_usage_percent(
                                placed_layouts[layout_idx]["placed_polygons"], sheet_size
                            )
                            placed_layouts[layout_idx]["usage_percent"] = new_usage
                            
                            # Update orders_on_sheet set
                            if "orders_on_sheet" not in placed_layouts[layout_idx]:
                                placed_layouts[layout_idx]["orders_on_sheet"] = set()
                            placed_layouts[layout_idx]["orders_on_sheet"].add(order_id)
                            
                            # Track sheet usage for this order
                            if order_id not in order_sheet_usage:
                                order_sheet_usage[order_id] = 0
                            order_sheet_usage[order_id] = 1  # Single polygon order uses 1 sheet
                            
                            filled_orders += 1
                            placed_successfully = True
                            
                            logger.info(
                                f"✅ ДОЗАПОЛНЕНИЕ: Заказ {order_id} размещен на лист #{layout['sheet_number']} ({current_usage:.1f}% → {new_usage:.1f}%)"
                            )
                            if verbose:
                                st.success(
                                    f"✅ Заказ {order_id} добавлен на лист #{layout['sheet_number']} ({current_usage:.1f}% → {new_usage:.1f}%)"
                                )
                            break
                    except Exception as e:
                        logger.debug(f"Не удалось добавить {order_id} на лист #{layout['sheet_number']}: {e}")
                        continue
                
                if placed_successfully:
                    # Remove this order from remaining_orders
                    del remaining_orders[order_id]
                    
            logger.info(f"Дозаполнение завершено: {filled_orders} заказов размещено")
            if verbose:
                st.info(f"📊 Дозаполнение: {filled_orders} однокомпонентных заказов размещено")

    # PRIORITY 2 PROCESSING: Try to fit priority 2 polygons into existing sheets only
    if priority2_polygons and placed_layouts:
        logger.info(
            f"=== ОБРАБОТКА ПРИОРИТЕТА 2: {len(priority2_polygons)} полигонов ==="
        )
        if verbose:
            st.info(
                f"🔄 Размещение файлов приоритета 2: {len(priority2_polygons)} файлов в существующие листы"
            )
        
        # Update progress for priority 2 processing
        if progress_callback:
            progress_callback(96, f"Обработка файлов приоритета 2: {len(priority2_polygons)} файлов")

        priority2_placed = 0
        priority2_remaining = list(priority2_polygons)

        # Try to fill existing sheets with priority 2 polygons
        for layout_idx, layout in enumerate(placed_layouts):
            if not priority2_remaining:
                break

            sheet_size = layout["sheet_size"]
            sheet_color = layout.get("sheet_color", "серый")  # Get color directly from layout

            existing_placed = layout["placed_polygons"]
            current_usage = layout["usage_percent"]

            if current_usage >= 95:  # Skip nearly full sheets
                continue

            logger.info(
                f"Пытаемся добавить приоритет 2 на лист #{layout['sheet_number']} (заполнение: {current_usage:.1f}%, цвет листа: {sheet_color})"
            )

            # Filter priority 2 polygons by color compatibility
            compatible_priority2 = []
            for poly_tuple in priority2_remaining:
                if len(poly_tuple) >= 3:
                    poly_color = poly_tuple[2]
                else:
                    poly_color = "серый"
                    
                # Skip detailed logging for speed
                if poly_color == sheet_color:
                    compatible_priority2.append(poly_tuple)
            
            logger.info(f"Найдено {len(compatible_priority2)} совместимых полигонов приоритета 2 из {len(priority2_remaining)}")

            if not compatible_priority2:
                logger.debug(
                    f"Нет совместимых по цвету приоритет 2 полигонов для листа {sheet_color}"
                )
                continue

            # Try to place compatible priority 2 polygons on this existing sheet
            try:
                additional_placed, still_remaining = bin_packing_with_existing(
                    compatible_priority2, existing_placed, sheet_size, verbose=False
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
                    priority2_placed += len(additional_placed)

                    logger.info(
                        f"✅ Добавлено {len(additional_placed)} файлов приоритета 2 на лист #{layout['sheet_number']} ({current_usage:.1f}% → {new_usage:.1f}%)"
                    )
                    if verbose:
                        st.success(
                            f"✅ Добавлено {len(additional_placed)} файлов приоритета 2 на лист #{layout['sheet_number']}"
                        )

                    # Remove placed polygons from priority2_remaining
                    # ИСПРАВЛЕНИЕ: точное совпадение по 3 полям для правильного удаления
                    placed_keys = set()
                    for placed_poly in additional_placed:
                        if len(placed_poly) >= 5:
                            # Полигон из bin_packing_with_existing: (polygon, x, y, angle, filename, color, order_id)
                            key = (placed_poly[4], placed_poly[5], placed_poly[6])  # filename, color, order_id
                        else:
                            # Обычный полигон: (polygon, filename, color, order_id)
                            key = (placed_poly[1], placed_poly[2], placed_poly[3])
                        placed_keys.add(key)
                    
                    # Удаляем полигоны с совпадающими ключами
                    priority2_remaining = [
                        p for p in priority2_remaining 
                        if (p[1], p[2], p[3]) not in placed_keys
                    ]

            except Exception as e:
                logger.warning(
                    f"Ошибка при добавлении приоритета 2 на лист #{layout['sheet_number']}: {e}"
                )

        logger.info(
            f"Приоритет 2: размещено {priority2_placed}, осталось {len(priority2_remaining)}"
        )
        if priority2_remaining:
            logger.info(
                f"⚠️ {len(priority2_remaining)} файлов приоритета 2 не размещены (новые листы не создаются)"
            )
            if verbose:
                st.warning(
                    f"⚠️ {len(priority2_remaining)} файлов приоритета 2 не удалось разместить в существующие листы"
                )

        # Add remaining priority 2 polygons to unplaced list
        all_unplaced.extend(priority2_remaining)

    # НОВОЕ: Создание дополнительных листов для неразмещенных Excel полигонов
    # Анализируем неразмещенные полигоны и создаем листы если есть доступные
    remaining_excel_polygons = [p for p in all_unplaced if len(p) < 5 or p[4] != 2]  # Не приоритет 2
    
    if remaining_excel_polygons and any(sheet["count"] - sheet["used"] > 0 for sheet in sheet_inventory):
        logger.info(f"Создаем дополнительные листы для {len(remaining_excel_polygons)} неразмещенных Excel полигонов")
        
        # Группируем по цветам
        polygons_by_color = {}
        for poly in remaining_excel_polygons:
            color = poly[2] if len(poly) >= 3 else "серый"
            if color not in polygons_by_color:
                polygons_by_color[color] = []
            polygons_by_color[color].append(poly)
        
        # Пытаемся создать листы для каждого цвета
        additional_created = 0
        for color, color_polygons in polygons_by_color.items():
            # Найти доступные листы этого цвета
            available_count = 0
            for sheet_type in sheet_inventory:
                if sheet_type["color"] == color and sheet_type["used"] < sheet_type["count"]:
                    available_count = sheet_type["count"] - sheet_type["used"]
            
            if available_count > 0:
                logger.info(f"Доступно {available_count} листов цвета {color} для {len(color_polygons)} полигонов")
                
                # Пытаемся разместить полигоны на новых листах
                try:
                    new_layouts, still_unplaced = bin_packing_with_inventory(
                        color_polygons,
                        [sheet for sheet in sheet_inventory if sheet["color"] == color],
                        verbose=False,
                        max_sheets_per_order=max_sheets_per_order,
                    )
                    
                    if new_layouts:
                        # Обновляем номера листов
                        for layout in new_layouts:
                            sheet_counter += 1
                            layout["sheet_number"] = sheet_counter
                        
                        placed_layouts.extend(new_layouts)
                        additional_created += len(new_layouts)
                        
                        # Обновляем использование листов
                        for sheet_type in sheet_inventory:
                            if sheet_type["color"] == color:
                                sheet_type["used"] += len([l for l in new_layouts if l.get("sheet_color") == color])
                                break
                        
                        # Убираем размещенные полигоны из unplaced
                        placed_count = sum(len(layout["placed_polygons"]) for layout in new_layouts)
                        all_unplaced = [p for p in all_unplaced if p not in color_polygons[:placed_count]]
                        
                        logger.info(f"Создано {len(new_layouts)} дополнительных листов цвета {color}")
                    
                except Exception as e:
                    logger.warning(f"Ошибка создания дополнительных листов для {color}: {e}")
        
        if additional_created > 0:
            logger.info(f"✅ Создано {additional_created} дополнительных листов для Excel полигонов")

    elif priority2_polygons and not placed_layouts:
        logger.warning(
            f"Нет существующих листов для размещения {len(priority2_polygons)} файлов приоритета 2"
        )
        if verbose:
            st.warning(
                f"⚠️ Нет размещенных листов для {len(priority2_polygons)} файлов приоритета 2"
            )
        # Add all priority 2 polygons to unplaced list since no sheets were created
        all_unplaced.extend(priority2_polygons)
    elif priority2_polygons and not order_groups:
        # Special case: only priority 2 polygons exist, no priority 1 files
        logger.info(
            f"Только priority 2 файлы без существующих листов: {len(priority2_polygons)} файлов не размещаются"
        )
        if verbose:
            st.warning(
                f"⚠️ Только файлы приоритета 2: {len(priority2_polygons)} файлов не размещаются (новые листы не создаются)"
            )
        all_unplaced.extend(priority2_polygons)

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

    # ======= POST-PROCESSING: AGGRESSIVE REDISTRIBUTION ======
    logger.info("🔧 ФИНАЛЬНОЕ АГРЕССИВНОЕ ПЕРЕРАСПРЕДЕЛЕНИЕ ЛИСТОВ")
    
    # Find low-usage sheets (less than 50% filled) that we can redistribute
    low_usage_sheets = []
    high_usage_sheets = []
    
    for idx, layout in enumerate(placed_layouts):
        usage = layout.get("usage_percent", 0)
        poly_count = len(layout.get("placed_polygons", []))
        
        if usage < 50 and poly_count <= 3:  # Low usage and few polygons
            low_usage_sheets.append((idx, layout, usage))
        elif usage < 85:  # Can potentially accept more polygons
            high_usage_sheets.append((idx, layout, usage))
    
    if low_usage_sheets:
        logger.info(f"Найдено {len(low_usage_sheets)} листов с низким заполнением для перераспределения")
        logger.info(f"Доступно {len(high_usage_sheets)} листов-получателей")
        
        successfully_redistributed = 0
        sheets_to_remove = []
        
        # Sort and limit sheets for faster processing
        low_usage_sheets.sort(key=lambda x: x[2])  # Sort by usage (lowest first)
        high_usage_sheets.sort(key=lambda x: x[2])  # Sort by usage (lowest first) 
        
        # Limit processing to first 5 low-usage sheets and first 10 high-usage sheets for speed
        low_usage_sheets = low_usage_sheets[:5]
        high_usage_sheets = high_usage_sheets[:10]
        
        for low_idx, low_layout, low_usage in low_usage_sheets:
            polygons_to_move = low_layout["placed_polygons"]
            sheet_color = low_layout.get("sheet_color", "серый")
            
            if not polygons_to_move:
                continue
                
            logger.info(f"Пытаемся перераспределить лист #{low_layout['sheet_number']} ({low_usage:.1f}%, {len(polygons_to_move)} полигонов)")
            
            # Try to place all polygons from this sheet onto other sheets
            all_moved = True
            moved_polygons = []
            failed_attempts = 0
            
            for poly_tuple in polygons_to_move:
                # Early exit if too many failures
                if failed_attempts >= 5:
                    all_moved = False
                    break
                moved = False
                
                # Try to place on compatible high-usage sheets
                for high_idx, high_layout, high_usage in high_usage_sheets:
                    if high_idx == low_idx:  # Don't try to move to itself
                        continue
                        
                    target_color = high_layout.get("sheet_color", "серый")
                    if target_color != sheet_color:  # Must be same color
                        continue
                        
                    if high_usage >= 85:  # Skip nearly full sheets
                        continue
                    
                    # Log attempt for debugging  
                    # Handle different tuple structures: (polygon, file_name, color, order_id) vs (polygon, x, y, angle, file_name, color, order_id)
                    if len(poly_tuple) == 7:
                        # Extended format from bin_packing_with_existing: (polygon, x, y, angle, file_name, color, order_id)
                        poly_order_id = poly_tuple[6]
                        poly_filename = poly_tuple[4]
                    else:
                        # Standard format: (polygon, file_name, color, order_id) 
                        poly_order_id = poly_tuple[3] if len(poly_tuple) > 3 else "unknown"
                        poly_filename = poly_tuple[1] if len(poly_tuple) > 1 else "unknown"
                    
                    logger.info(f"    Попытка переместить {poly_order_id} ({poly_filename}) на лист #{high_layout['sheet_number']} ({high_usage:.1f}%)")
                    
                    existing_placed = high_layout["placed_polygons"]
                    sheet_size = high_layout["sheet_size"]
                    
                    try:
                        # Try to add this polygon to the target sheet (fast attempt)
                        additional_placed, still_remaining = bin_packing_with_existing(
                            [poly_tuple], existing_placed, sheet_size, max_attempts=20, verbose=False
                        )
                        
                        if additional_placed:
                            # Successfully moved to target sheet
                            placed_layouts[high_idx]["placed_polygons"] = existing_placed + additional_placed
                            new_usage = calculate_usage_percent(
                                placed_layouts[high_idx]["placed_polygons"], sheet_size
                            )
                            placed_layouts[high_idx]["usage_percent"] = new_usage
                            
                            # Update orders on target sheet
                            if "orders_on_sheet" not in placed_layouts[high_idx]:
                                placed_layouts[high_idx]["orders_on_sheet"] = set()
                            elif isinstance(placed_layouts[high_idx]["orders_on_sheet"], list):
                                # Convert list to set if needed
                                placed_layouts[high_idx]["orders_on_sheet"] = set(placed_layouts[high_idx]["orders_on_sheet"])
                            
                            # Add the order_id with correct indexing based on tuple structure
                            if len(poly_tuple) == 7:
                                # Extended format: order_id is at index 6
                                placed_layouts[high_idx]["orders_on_sheet"].add(poly_tuple[6])
                            elif len(poly_tuple) > 3:
                                # Standard format: order_id is at index 3
                                placed_layouts[high_idx]["orders_on_sheet"].add(poly_tuple[3])
                            
                            moved_polygons.append(poly_tuple)
                            moved = True
                            
                            # Update high_usage in our list for next iterations
                            for i, (h_idx, h_layout, h_usage) in enumerate(high_usage_sheets):
                                if h_idx == high_idx:
                                    high_usage_sheets[i] = (h_idx, h_layout, new_usage)
                                    break
                            
                            logger.info(f"      ✅ Полигон перемещен на лист #{high_layout['sheet_number']} ({high_usage:.1f}% → {new_usage:.1f}%)")
                            break
                        else:
                            logger.info(f"      ❌ Не помещается на лист #{high_layout['sheet_number']}")
                            
                    except Exception as e:
                        logger.info(f"      ❌ Ошибка размещения на лист #{high_layout['sheet_number']}: {e}")
                        continue
                
                if not moved:
                    failed_attempts += 1
                    all_moved = False
                    break
            
            if all_moved and moved_polygons:
                # All polygons successfully moved - mark sheet for removal
                sheets_to_remove.append(low_idx)
                successfully_redistributed += len(moved_polygons)
                logger.info(f"  🎯 УСПЕХ: Лист #{low_layout['sheet_number']} полностью опустошен ({len(moved_polygons)} полигонов перемещено)")
            else:
                # Some polygons couldn't be moved - update the sheet with remaining polygons
                remaining_polygons = [p for p in polygons_to_move if p not in moved_polygons]
                placed_layouts[low_idx]["placed_polygons"] = remaining_polygons
                placed_layouts[low_idx]["usage_percent"] = calculate_usage_percent(
                    remaining_polygons, low_layout["sheet_size"]
                )
                if moved_polygons:
                    logger.info(f"  ⚠️ ЧАСТИЧНО: Лист #{low_layout['sheet_number']} ({len(moved_polygons)} перемещено, {len(remaining_polygons)} осталось)")
                    successfully_redistributed += len(moved_polygons)
        
        # Remove empty sheets (in reverse order to maintain indices)
        for sheet_idx in sorted(sheets_to_remove, reverse=True):
            removed_sheet = placed_layouts.pop(sheet_idx)
            logger.info(f"🗑️ Удален пустой лист #{removed_sheet['sheet_number']}")
        
        logger.info(f"🎯 ПЕРЕРАСПРЕДЕЛЕНИЕ: {successfully_redistributed} полигонов перемещено, {len(sheets_to_remove)} листов удалено")
        logger.info(f"📊 РЕЗУЛЬТАТ: {len(placed_layouts)} листов вместо {len(placed_layouts) + len(sheets_to_remove)}")
    else:
        logger.info("Листов с низким заполнением для перераспределения не найдено")

    # Final progress update
    if progress_callback:
        progress_callback(100, f"Завершено: {len(placed_layouts)} листов создано")

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
        
        # Handle case where file_name might be a float64 or other non-string type
        display_name = str(file_name)
        if display_name.endswith('.dxf'):
            display_name = display_name.replace(".dxf", "")
        
        ax.annotate(
            display_name,
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
        if (
            len(polygon_tuple) >= 5
        ):  # Extended format with color, order_id, and priority
            polygon, name, color, order_id, priority = polygon_tuple[:5]
        elif len(polygon_tuple) >= 4:  # Extended format with color and order_id
            polygon, name, color, order_id = polygon_tuple[:4]
            priority = 1  # Default priority
        elif len(polygon_tuple) >= 3:  # Format with color
            polygon, name, color = polygon_tuple[:3]
            order_id = "unknown"
            priority = 1  # Default priority
        else:  # Old format without color
            polygon, name = polygon_tuple[:2]
            color = "серый"
            order_id = "unknown"
            priority = 1  # Default priority
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
            scaled_polygons.append((scaled_polygon, name, color, order_id, priority))
        else:
            scaled_polygons.append((polygon, name, color, order_id, priority))

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
