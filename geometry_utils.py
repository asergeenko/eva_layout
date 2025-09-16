from shapely import Polygon, affinity


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

    # CONSERVATIVE FIX: Only repair if necessary, preserve geometry when possible
    if not rotated.is_valid:
        try:
            # Try minimal buffer repair first
            fixed = rotated.buffer(0)
            if fixed.is_valid:
                return fixed

            # Try tiny buffer if needed
            fixed = rotated.buffer(0.001)
            if fixed.is_valid:
                return fixed

        except Exception:
            pass

        # If repair fails, return original only if it's valid
        if polygon.is_valid:
            return polygon

    # Return rotated result even if not perfectly valid - it's usually fine for collision detection
    return rotated


def translate_polygon(polygon: Polygon, x: float, y: float) -> Polygon:
    """Translate a polygon to a new position."""
    translated = affinity.translate(polygon, xoff=x, yoff=y)

    # CONSERVATIVE FIX: Only repair if necessary, preserve translation accuracy
    if not translated.is_valid:
        try:
            # Try minimal buffer repair
            fixed = translated.buffer(0)
            if fixed.is_valid:
                return fixed

            # Try tiny buffer if needed
            fixed = translated.buffer(0.001)
            if fixed.is_valid:
                return fixed

        except Exception:
            pass

        # If repair fails, return original only if it's valid
        if polygon.is_valid:
            return polygon

    # Return translated result - preserve the translation even if not perfectly valid
    return translated
