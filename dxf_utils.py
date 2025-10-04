import math
import os
import tempfile
from io import BytesIO

import logging
import ezdxf
import numpy as np
from shapely import Polygon, unary_union, MultiPolygon

from carpet import PlacedCarpet

logger = logging.getLogger(__name__)


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

    except Exception:
        logger.exception(f"Ошибка конвертации {entity_type}.")

    return None


def save_dxf_layout_complete(
    placed_elements: list[PlacedCarpet],
    sheet_size: tuple[float, float],
    output_path: str,
    original_dxf_data_map=None,
):
    """COMPLETELY CORRECTED - Use coordinate mapping from original to transformed polygon"""

    # Create new DXF document
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4  # millimeters
    doc.header["$LUNITS"] = 2  # decimal units
    msp = doc.modelspace()

    for placed_element in placed_elements:
        transformed_polygon = placed_element.polygon
        rotation_angle = placed_element.angle
        file_name = placed_element.filename

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

        except Exception:
            logger.exception(f"Ошибка обработки {entity_type}")

    # Combine all polygons into one using unary_union
    if polygons:
        from shapely.ops import unary_union

        combined = unary_union(polygons)

        # If result is MultiPolygon, get the convex hull to make it a single polygon
        if hasattr(combined, "geoms"):
            # It's a MultiPolygon, take convex hull to get single polygon
            combined = combined.convex_hull
        return combined
    else:
        return None


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
                    else:
                        continue
                result["polygons"].append(polygon)
        except Exception:
            logger.exception(f"⚠️ Не удалось конвертировать {entity_type} в полигон.")

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
            else:
                result["combined_polygon"] = combined
    else:
        result["combined_polygon"] = None

    # Проверка: если combined_polygon слишком маленький (незамкнутый контур),
    # выдаем предупреждение и возвращаем None
    if result["combined_polygon"] and result["combined_polygon"].area < 10000:
        # Проверяем количество SPLINE в файле
        spline_count = sum(1 for e in result["original_entities"] if e["type"] == "SPLINE")
        if spline_count > 10:
            bounds = result["combined_polygon"].bounds
            size = f"{bounds[2]-bounds[0]:.0f}x{bounds[3]-bounds[1]:.0f}"
            logger.info(f"⚠️  ПРЕДУПРЕЖДЕНИЕ: Файл содержит {spline_count} SPLINE, но получен очень маленький полигон ({size} мм, area={result['combined_polygon'].area:.0f} мм²)")
            logger.info(f"   Возможно контур не замкнут или содержит только текст/надписи")
            logger.info(f"   Файл будет пропущен при раскладке")
            result["combined_polygon"] = None
            result["parse_warning"] = "незамкнутый контур или только текст"

    # ВАЖНО: Нормализуем combined_polygon к координатам (0,0)
    # чтобы избежать проблем с отрицательными координатами
    if result["combined_polygon"]:
        from shapely.affinity import translate as shapely_translate

        bounds = result["combined_polygon"].bounds
        result["original_bounds"] = bounds  # Сохраняем оригинальные границы
        result["combined_polygon"] = shapely_translate(
            result["combined_polygon"], -bounds[0], -bounds[1]
        )

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

    # Store original data separately since Shapely polygons don't allow attribute assignment
    # We'll pass this data through function parameters instead

    return result
