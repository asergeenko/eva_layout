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
from dataclasses import dataclass

# from line_profiler import profile

@dataclass
class Carpet:
    polygon: Polygon
    filename: str = "unknown"
    color: str = "серый"
    order_id: str = "unknown"
    priority: int = 1


# Настройка логирования
logger = logging.getLogger(__name__)

# Import improved packing algorithms after logger is defined
try:
    from improved_packing import improved_bin_packing
    IMPROVED_PACKING_AVAILABLE = True
    logger.info("✨ Улучшенный алгоритм размещения загружен")
except ImportError:
    IMPROVED_PACKING_AVAILABLE = False
    logger.warning("⚠️  Улучшенный алгоритм недоступен, используем стандартный")

try:
    from polygonal_packing import polygonal_bin_packing
    POLYGONAL_PACKING_AVAILABLE = True
    logger.info("🔷 Полигональный алгоритм размещения загружен")
except ImportError:
    POLYGONAL_PACKING_AVAILABLE = False
    logger.warning("⚠️  Полигональный алгоритм недоступен")

# Настройки алгоритмов
USE_IMPROVED_PACKING_BY_DEFAULT = True  # Улучшенный алгоритм по умолчанию (лучший баланс)
USE_POLYGONAL_PACKING_BY_DEFAULT = False  # Полигональный алгоритм отключен (слишком сложный)

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
]


def get_color_for_file(filename: str) -> tuple[float, float, float]:
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


def parse_dxf_complete(file: BytesIO | str, verbose: bool = True):
    """Parse DXF file preserving all elements without loss."""

    if isinstance(file, BytesIO):
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


# @profile
def bin_packing_with_existing(
    polygons: list[Carpet],
    existing_placed: list[tuple],
    sheet_size: tuple[float, float],
    verbose: bool = True,
) -> tuple[list[tuple], list[tuple]]:
    """Bin packing that considers already placed polygons on the sheet."""
    # Try improved algorithm for existing placement if available and enabled
    if IMPROVED_PACKING_AVAILABLE and USE_IMPROVED_PACKING_BY_DEFAULT and len(existing_placed) > 0:
        if verbose:
            st.info(f"🚀 Дозаполняем лист улучшенным алгоритмом: +{len(polygons)} к {len(existing_placed)} существующим")
        try:
            # Create a packer with existing polygons pre-placed
            from improved_packing import AdvancedCarpetPacker
            sheet_width_mm = sheet_size[0] * 10
            sheet_height_mm = sheet_size[1] * 10
            
            packer = AdvancedCarpetPacker(sheet_width_mm, sheet_height_mm)
            # Add existing polygons to packer
            packer.placed_polygons = [placed_tuple[0] for placed_tuple in existing_placed]
            packer.placed_positions = [(placed_tuple[1], placed_tuple[2]) for placed_tuple in existing_placed]
            
            # Pack new polygons
            placed, unplaced = packer.pack_carpets(polygons)
            return placed, unplaced
            
        except Exception as e:
            logger.warning(f"Ошибка в улучшенном алгоритме дозаполнения: {e}, используем стандартный")
            if verbose:
                st.warning("⚠️ Используем стандартный алгоритм дозаполнения")
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
    def get_polygon_priority(polygon_tuple: Carpet):
        polygon = polygon_tuple.polygon
        # Combine area and perimeter for better sorting (larger, more complex shapes first)
        area = polygon.area
        bounds = polygon.bounds
        perimeter_approx = 2 * ((bounds[2] - bounds[0]) + (bounds[3] - bounds[1]))
        return area + perimeter_approx * 0.1

    sorted_polygons = sorted(polygons, key=get_polygon_priority, reverse=True)

    for i, carpet in enumerate(sorted_polygons):
        # ПРОФИЛИРОВАНИЕ: Измеряем время обработки каждого полигона
        import time

        polygon_start_time = time.time()

        polygon = carpet.polygon
        file_name = carpet.filename
        color = carpet.color
        order_id = carpet.order_id

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
            # ПРОФИЛИРОВАНИЕ: Измеряем время поиска позиции
            pos_start_time = time.time()
            best_x, best_y = find_bottom_left_position_with_obstacles(
                rotated, obstacles, sheet_width_mm, sheet_height_mm
            )
            pos_elapsed = time.time() - pos_start_time
            if pos_elapsed > 1.0:  # Логируем медленные поиски позиций
                logger.warning(
                    f"⏱️ Медленный поиск позиции: {pos_elapsed:.2f}s для {len(obstacles)} препятствий"
                )

            if best_x is not None and best_y is not None:
                # Calculate waste for this placement
                translated = translate_polygon(
                    rotated, best_x - rotated_bounds[0], best_y - rotated_bounds[1]
                )
                # ПРОФИЛИРОВАНИЕ: Измеряем время расчета waste
                waste_start_time = time.time()
                waste = calculate_placement_waste(
                    translated,
                    [(obs, 0, 0, 0, "obstacle") for obs in obstacles],
                    sheet_width_mm,
                    sheet_height_mm,
                )
                waste_elapsed = time.time() - waste_start_time
                if waste_elapsed > 0.5:  # Логируем медленные расчеты waste
                    logger.warning(
                        f"⏱️ Медленный расчет waste: {waste_elapsed:.2f}s для {len(obstacles)} препятствий"
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

        # ПРОФИЛИРОВАНИЕ: Логируем время обработки медленных полигонов
        polygon_elapsed = time.time() - polygon_start_time
        if polygon_elapsed > 2.0:  # Логируем полигоны, обрабатывающиеся дольше 2 секунд
            logger.warning(
                f"⏱️ Медленный полигон {file_name}: {polygon_elapsed:.2f}s, размещен={placed_successfully}"
            )

    return placed, unplaced


# @profile
def bin_packing(
    polygons: list[tuple],
    sheet_size: tuple[float, float],
    verbose: bool = True,
) -> tuple[list[tuple], list[tuple]]:
    """Optimize placement of complex polygons on a sheet with polygonal/improved algorithms."""
    # Try to use polygonal algorithm first if enabled
    if POLYGONAL_PACKING_AVAILABLE and USE_POLYGONAL_PACKING_BY_DEFAULT:
        if verbose:
            st.info(f"🔷 Используем полигональный алгоритм размещения для {len(polygons)} полигонов")
        try:
            return polygonal_bin_packing(polygons, sheet_size, verbose)
        except Exception as e:
            logger.warning(f"Ошибка в полигональном алгоритме: {e}, переключаемся на улучшенный")
            if verbose:
                st.warning("⚠️ Переключение на улучшенный алгоритм из-за ошибки")
    
    # Try to use improved algorithm as fallback
    if IMPROVED_PACKING_AVAILABLE and (USE_IMPROVED_PACKING_BY_DEFAULT or not POLYGONAL_PACKING_AVAILABLE):
        if verbose:
            st.info(f"🚀 Используем улучшенный алгоритм размещения для {len(polygons)} полигонов")
        try:
            return improved_bin_packing(polygons, sheet_size, verbose)
        except Exception as e:
            logger.warning(f"Ошибка в улучшенном алгоритме: {e}, переключаемся на стандартный")
            if verbose:
                st.warning("⚠️ Переключение на стандартный алгоритм из-за ошибки")
    
    # Fallback to standard algorithm
    # Convert sheet size from cm to mm to match DXF polygon units
    sheet_width_mm, sheet_height_mm = sheet_size[0] * 10, sheet_size[1] * 10

    placed = []
    unplaced = []

    if verbose:
        st.info(
            f"Начинаем стандартную упаковку {len(polygons)} полигонов на листе {sheet_size[0]}x{sheet_size[1]} см"
        )

    # IMPROVEMENT 1: Sort polygons by area and perimeter for better packing
    def get_polygon_priority(carpet: Carpet):
        polygon = carpet.polygon
        # Combine area and perimeter for better sorting (larger, more complex shapes first)
        area = polygon.area
        bounds = polygon.bounds
        perimeter_approx = 2 * ((bounds[2] - bounds[0]) + (bounds[3] - bounds[1]))
        return area + perimeter_approx * 0.1

    sorted_polygons = sorted(polygons, key=get_polygon_priority, reverse=True)
    if verbose:
        st.info("✨ Сортировка полигонов по площади (сначала крупные)")

    for i, carpet in enumerate(sorted_polygons):
        placed_successfully = False
        if verbose:
            st.info(
                f"Обрабатываем полигон {i+1}/{len(sorted_polygons)} из файла {carpet.filename}, площадь: {carpet.polygon.area:.2f}"
            )

        # Check if polygon is too large for the sheet
        bounds = carpet.polygon.bounds
        poly_width = bounds[2] - bounds[0]
        poly_height = bounds[3] - bounds[1]

        if poly_width > sheet_width_mm or poly_height > sheet_height_mm:
            if verbose:
                st.warning(
                    f"Полигон из {carpet.filename} слишком большой: {poly_width/10:.1f}x{poly_height/10:.1f} см > {sheet_size[0]}x{sheet_size[1]} см"
                )
            unplaced.append(carpet)
            continue

        # IMPROVEMENT 2: Try all allowed orientations (0°, 90°, 180°, 270°) with better placement
        best_placement = None
        best_waste = float("inf")

        # Only allowed rotation angles for cutting machines
        rotation_angles = [0, 90, 180, 270]

        for angle in rotation_angles:
            rotated = (
                rotate_polygon(carpet.polygon, angle) if angle != 0 else carpet.polygon
            )
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
                    carpet.filename,
                    carpet.color,
                    carpet.order_id,
                )
            )
            placed_successfully = True
            if verbose:
                st.success(
                    f"✅ Размещен {carpet.filename} (угол: {best_placement['angle']}°, waste: {best_waste:.1f})"
                )
        else:
            # Fallback to original grid method if no bottom-left position found
            simple_bounds = carpet.polygon.bounds
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
                    translated = translate_polygon(carpet.polygon, x_offset, y_offset)

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
                                carpet.filename,
                                carpet.color,
                                carpet.order_id,
                            )
                        )
                        placed_successfully = True
                        if verbose:
                            st.success(
                                f"✅ Размещен {carpet.filename} (сетчатое размещение)"
                            )
                        break

                if placed_successfully:
                    break

        if not placed_successfully:
            if verbose:
                st.warning(f"❌ Не удалось разместить полигон из {carpet.filename}")
            unplaced.append(carpet)

    if verbose:
        usage_percent = calculate_usage_percent(placed, sheet_size)
        st.info(
            f"🏁 Упаковка завершена: {len(placed)} размещено, {len(unplaced)} не размещено, использование: {usage_percent:.1f}%"
        )
    return placed, unplaced


def find_bottom_left_position_with_obstacles(
    polygon: Polygon, obstacles: list[Polygon], sheet_width: float, sheet_height: float
) -> tuple[float | None, float | None]:
    """Find the bottom-left position for a polygon using Bottom-Left Fill algorithm with existing obstacles."""
    bounds = polygon.bounds
    poly_width = bounds[2] - bounds[0]
    poly_height = bounds[3] - bounds[1]

    # Try positions along bottom and left edges first
    candidate_positions = []

    # ОПТИМИЗАЦИЯ: Увеличиваем шаг сетки для ускорения поиска
    grid_step = 15  # Увеличено с 5mm до 15mm для 3x ускорения

    # Bottom edge positions
    for x in np.arange(0, sheet_width - poly_width + 1, grid_step):
        candidate_positions.append((x, 0))

    # Left edge positions
    for y in np.arange(0, sheet_height - poly_height + 1, grid_step):
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

    # ОПТИМИЗАЦИЯ: Ограничиваем количество кандидатов для предотвращения взрывного роста
    candidate_positions = list(set(candidate_positions))  # Удаляем дубликаты
    candidate_positions.sort(
        key=lambda pos: (pos[1], pos[0])
    )  # Sort by bottom-left preference

    # Ограничиваем до 100 лучших позиций для ускорения
    # max_candidates = 100
    # if len(candidate_positions) > max_candidates:
    #    candidate_positions = candidate_positions[:max_candidates]

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


def find_bottom_left_position(
    polygon: Polygon, placed_polygons, sheet_width: float, sheet_height: float
):
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


# @profile
def bin_packing_with_inventory(
    carpets: list[Carpet],
    available_sheets: list[dict],
    verbose: bool = True,
    progress_callback=None,
) -> tuple[list[dict], list[tuple]]:
    """Optimize placement of polygons on available sheets with inventory tracking.

    NEW ALGORITHM: Priority-based placement for maximum density:
    1. Place all Excel orders and priority 1 items first (can use new sheets)
    2. Place priority 2 items only on remaining space (no new sheets allowed)
    """
    logger.info("=== НАЧАЛО bin_packing_with_inventory (АЛГОРИТМ МАКСИМАЛЬНОЙ ПЛОТНОСТИ) ===")
    logger.info(
        f"Входные параметры: {len(carpets)} полигонов, {len(available_sheets)} типов листов"
    )

    placed_layouts = []
    all_unplaced = []
    sheet_inventory = [sheet.copy() for sheet in available_sheets]
    sheet_counter = 0

    if verbose:
        total_available = sum(
            sheet["count"] - sheet["used"] for sheet in sheet_inventory
        )
        st.info(
            f"Начинаем размещение {len(carpets)} полигонов на {total_available} доступных листах"
        )
        st.info("Работаем без ограничений на диапазон листов - максимальная плотность")

    # Step 1: Group carpets by priority
    logger.info("Группировка полигонов по приоритету...")
    priority1_carpets = []  # Excel orders and additional priority 1
    priority2_carpets = []  # Priority 2 carpets

    for carpet in carpets:
        if carpet.priority == 2:
            priority2_carpets.append(carpet)
        else:
            # All Excel orders (ZAKAZ_*) and priority 1 items go together
            priority1_carpets.append(carpet)

    logger.info(
        f"Группировка завершена: {len(priority1_carpets)} приоритет 1 + Excel, {len(priority2_carpets)} приоритет 2"
    )

    if verbose:
        st.info("Разделение выполнено:")
        st.info(f"  • Приоритет 1 + Excel заказы: {len(priority1_carpets)}")
        st.info(f"  • Приоритет 2: {len(priority2_carpets)}")

    # Helper functions
    def find_available_sheet_of_color(color, sheet_inventory):
        """Find an available sheet of the specified color."""
        for sheet_type in sheet_inventory:
            if (
                sheet_type.get("color", "серый") == color
                and sheet_type["count"] - sheet_type["used"] > 0
            ):
                return sheet_type
        return None

    def create_new_sheet(sheet_type, sheet_number, color):
        """Create a new sheet layout."""
        sheet_size = (sheet_type["width"], sheet_type["height"])
        return {
            "sheet_number": sheet_number,
            "sheet_type": sheet_type["name"],
            "sheet_color": color,
            "sheet_size": sheet_size,
            "placed_polygons": [],
            "usage_percent": 0.0,
            "orders_on_sheet": [],
        }

    # Early return if nothing to place
    if not priority1_carpets and not priority2_carpets:
        logger.info("Нет полигонов для размещения")
        return placed_layouts, all_unplaced

    # STEP 2: Place priority 1 items (Excel orders + manual priority 1) with new sheets allowed
    logger.info(
        f"\n=== ЭТАП 2: РАЗМЕЩЕНИЕ {len(priority1_carpets)} ПРИОРИТЕТ 1 + EXCEL ЗАКАЗОВ ==="
    )

    # Group priority 1 carpets by color for efficient processing
    remaining_priority1 = list(priority1_carpets)
    
    # First try to fill existing sheets with priority 1 carpets
    for layout_idx, layout in enumerate(placed_layouts):
        if not remaining_priority1:
            break
        if layout.get("usage_percent", 0) >= 85:
            continue

        # Group remaining by color matching this sheet
        matching_carpets = [
            c for c in remaining_priority1 if c.color == layout["sheet_color"]
        ]
        if not matching_carpets:
            continue

        try:
            additional_placed, remaining_tuples = bin_packing_with_existing(
                matching_carpets,
                layout["placed_polygons"],
                layout["sheet_size"],
                verbose=False,
            )

            if additional_placed:
                # Update layout
                placed_layouts[layout_idx]["placed_polygons"].extend(additional_placed)
                placed_layouts[layout_idx]["usage_percent"] = calculate_usage_percent(
                    placed_layouts[layout_idx]["placed_polygons"], layout["sheet_size"]
                )

                # Update remaining
                remaining_carpet_map = {
                    (c.polygon, c.filename, c.color, c.order_id): c
                    for c in matching_carpets
                }
                newly_remaining = []
                for remaining_tuple in remaining_tuples:
                    key = (
                        remaining_tuple[0],
                        remaining_tuple[1],
                        remaining_tuple[2],
                        remaining_tuple[3],
                    )
                    if key in remaining_carpet_map:
                        newly_remaining.append(remaining_carpet_map[key])

                # Remove placed carpets from remaining list
                placed_carpet_set = set(
                    (c.polygon, c.filename, c.color, c.order_id)
                    for c in matching_carpets
                    if c not in newly_remaining
                )
                remaining_priority1 = [
                    c
                    for c in remaining_priority1
                    if (c.polygon, c.filename, c.color, c.order_id)
                    not in placed_carpet_set
                ]

                logger.info(
                    f"    Дозаполнен лист #{layout['sheet_number']}: +{len(additional_placed)} приоритет1+Excel"
                )
        except Exception as e:
            logger.debug(f"Не удалось дозаполнить лист приоритетом 1: {e}")
            continue

    # Create new sheets for remaining priority 1 carpets
    carpets_by_color = {}
    for carpet in remaining_priority1:
        color = carpet.color
        if color not in carpets_by_color:
            carpets_by_color[color] = []
        carpets_by_color[color].append(carpet)

    for color, color_carpets in carpets_by_color.items():
        remaining_carpets = list(color_carpets)

        while remaining_carpets:
            sheet_type = find_available_sheet_of_color(color, sheet_inventory)
            if not sheet_type:
                logger.warning(f"Нет доступных листов цвета {color} для приоритета 1")
                all_unplaced.extend(remaining_carpets)
                break

            sheet_counter += 1
            sheet_type["used"] += 1
            sheet_size = (sheet_type["width"], sheet_type["height"])

            placed, remaining = bin_packing(
                remaining_carpets, sheet_size, verbose=False
            )

            if placed:
                new_layout = create_new_sheet(sheet_type, sheet_counter, color)
                new_layout["placed_polygons"] = placed
                new_layout["usage_percent"] = calculate_usage_percent(
                    placed, sheet_size
                )
                new_layout["orders_on_sheet"] = list(
                    set(
                        carpet.order_id
                        for carpet in remaining_carpets
                        if carpet not in remaining
                    )
                )
                placed_layouts.append(new_layout)

                remaining_carpets = remaining
                logger.info(
                    f"    Создан лист #{sheet_counter}: {len(placed)} приоритет1+Excel"
                )

                if verbose:
                    st.success(
                        f"✅ Лист #{sheet_counter} ({sheet_type['name']}): {len(placed)} приоритет1+Excel"
                    )
            else:
                logger.warning(
                    f"Не удалось разместить приоритет 1 на новом листе {color}"
                )
                all_unplaced.extend(remaining_carpets)
                sheet_type["used"] -= 1
                sheet_counter -= 1
                break

        if progress_callback:
            progress = min(70, int(70 * len(placed_layouts) / (len(placed_layouts) + len(priority2_carpets))))
            progress_callback(progress, f"Размещение приоритет 1+Excel: {len(placed_layouts)} листов")

    # STEP 3: Place priority 2 on remaining space only (no new sheets)
    logger.info(
        f"\n=== ЭТАП 3: РАЗМЕЩЕНИЕ {len(priority2_carpets)} ПРИОРИТЕТ2 НА СВОБОДНОМ МЕСТЕ ==="
    )

    remaining_priority2 = list(priority2_carpets)

    for layout_idx, layout in enumerate(placed_layouts):
        if not remaining_priority2:
            break
        if layout.get("usage_percent", 0) >= 85:
            continue

        # Try to place carpets of matching color
        matching_carpets = [
            c for c in remaining_priority2 if c.color == layout["sheet_color"]
        ]
        if not matching_carpets:
            continue

        try:
            additional_placed, remaining_tuples = bin_packing_with_existing(
                matching_carpets,
                layout["placed_polygons"],
                layout["sheet_size"],
                verbose=False,
            )

            if additional_placed:
                # Update layout
                placed_layouts[layout_idx]["placed_polygons"].extend(additional_placed)
                placed_layouts[layout_idx]["usage_percent"] = calculate_usage_percent(
                    placed_layouts[layout_idx]["placed_polygons"], layout["sheet_size"]
                )

                # Update remaining
                remaining_carpet_map = {
                    (c.polygon, c.filename, c.color, c.order_id): c
                    for c in matching_carpets
                }
                newly_remaining = []
                for remaining_tuple in remaining_tuples:
                    key = (
                        remaining_tuple[0],
                        remaining_tuple[1],
                        remaining_tuple[2],
                        remaining_tuple[3],
                    )
                    if key in remaining_carpet_map:
                        newly_remaining.append(remaining_carpet_map[key])

                # Remove placed carpets from remaining list
                placed_carpet_set = set(
                    (c.polygon, c.filename, c.color, c.order_id)
                    for c in matching_carpets
                    if c not in newly_remaining
                )
                remaining_priority2 = [
                    c
                    for c in remaining_priority2
                    if (c.polygon, c.filename, c.color, c.order_id)
                    not in placed_carpet_set
                ]

                logger.info(
                    f"    Дозаполнен лист #{layout['sheet_number']}: +{len(additional_placed)} приоритет2"
                )
        except Exception as e:
            logger.debug(f"Не удалось дозаполнить лист приоритетом 2: {e}")
            continue

    # Add any remaining priority 2 to unplaced (no new sheets allowed)
    if remaining_priority2:
        logger.info(
            f"Остается неразмещенными {len(remaining_priority2)} приоритет2 (новые листы не создаются)"
        )
        all_unplaced.extend(remaining_priority2)

    # STEP 7: Sort sheets by color (group black together, then grey)
    logger.info("\n=== ЭТАП 7: ГРУППИРОВКА ЛИСТОВ ПО ЦВЕТАМ ===")

    # Separate black and grey sheets, maintain relative order within each color
    black_sheets = []
    grey_sheets = []

    for layout in placed_layouts:
        if layout["sheet_color"] == "чёрный":
            black_sheets.append(layout)
        else:
            grey_sheets.append(layout)

    # Reassign sheet numbers: first all black, then all grey
    final_layouts = []
    sheet_number = 1

    for layout in black_sheets + grey_sheets:
        layout["sheet_number"] = sheet_number
        final_layouts.append(layout)
        sheet_number += 1

    placed_layouts = final_layouts

    logger.info(
        f"Перегруппировка завершена: {len(black_sheets)} черных + {len(grey_sheets)} серых = {len(placed_layouts)} листов"
    )

    # Final logging and progress
    logger.info("\n=== ИТОГИ РАЗМЕЩЕНИЯ ===")
    logger.info(f"Всего листов создано: {len(placed_layouts)}")
    logger.info(f"Неразмещенных полигонов: {len(all_unplaced)}")

    if verbose:
        st.info(
            f"Размещение завершено: {len(placed_layouts)} листов, {len(all_unplaced)} не размещено"
        )

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
        if display_name.endswith(".dxf"):
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
    carpets: list[Carpet],
) -> dict[str, BytesIO]:
    """Create individual plots for each DXF file."""
    if not carpets:
        return {}

    plots = {}
    for carpet in carpets:
        plot_buf = plot_single_polygon(
            carpet.polygon,
            f"Файл: {carpet.filename} (цвет: {carpet.color})",
            filename=carpet.filename,
        )
        plots[carpet.filename] = plot_buf

    return plots
