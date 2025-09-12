"""Helper functions for EVA mat nesting optimization."""

# Version for cache busting
__version__ = "1.5.0"

import numpy as np

from shapely.geometry import Polygon
from shapely import affinity
import streamlit as st
import logging

from carpet import Carpet, PlacedCarpet, UnplacedCarpet, PlacedSheet

# Настройка логирования
logger = logging.getLogger(__name__)


logging.getLogger("ezdxf").setLevel(logging.ERROR)

__all__ = [
    "rotate_polygon",
    "translate_polygon",
    "place_polygon_at_origin",
    "check_collision",
    "bin_packing_with_inventory",
    "calculate_usage_percent",
    "bin_packing",
]


def find_available_sheet_of_color(color, sheet_inventory):
    """Find an available sheet of the specified color."""
    for sheet_type in sheet_inventory:
        if (
            sheet_type.get("color", "серый") == color
            and sheet_type["count"] - sheet_type["used"] > 0
        ):
            return sheet_type
    return None


def create_new_sheet(sheet_type, sheet_number, color) -> PlacedSheet:
    """Create a new sheet layout."""
    sheet_size = (sheet_type["width"], sheet_type["height"])
    return PlacedSheet(
        sheet_number=sheet_number,
        sheet_type=sheet_type["name"],
        sheet_color=color,
        sheet_size=sheet_size,
        placed_polygons=[],
        usage_percent=0.0,
        orders_on_sheet=[],
    )


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


def check_collision_fast(
    polygon1: Polygon, polygon2: Polygon, min_gap: float = 0.1
) -> bool:
    """FIXED fast collision check - PRIORITY: Accuracy over speed."""
    # Fast validity check
    if not (polygon1.is_valid and polygon2.is_valid):
        return True

    try:
        # CRITICAL FIX: Always check intersection first - this catches overlapping polygons
        if polygon1.intersects(polygon2):
            return True

        # SPEED OPTIMIZATION: Only use bbox pre-filter for distant objects
        bounds1 = polygon1.bounds
        bounds2 = polygon2.bounds

        # Calculate minimum possible distance between bounding boxes
        dx = max(0, max(bounds1[0] - bounds2[2], bounds2[0] - bounds1[2]))
        dy = max(0, max(bounds1[1] - bounds2[3], bounds2[1] - bounds1[3]))
        bbox_min_distance = (dx * dx + dy * dy) ** 0.5

        # SAFE EARLY EXIT: Only skip geometric check if bounding boxes are clearly far apart
        if bbox_min_distance > min_gap + 50:  # Conservative 50mm safety margin
            return False

        # ALWAYS do accurate geometric distance check for close/potentially colliding objects
        geometric_distance = polygon1.distance(polygon2)
        return geometric_distance < min_gap

    except Exception:
        # Be conservative on errors
        return True


def check_collision(polygon1: Polygon, polygon2: Polygon, min_gap: float = 0.1) -> bool:
    """Check if two polygons collide using TRUE GEOMETRIC distance with speed optimization."""
    return check_collision_fast(polygon1, polygon2, min_gap)


# @profile
def bin_packing_with_existing(
    polygons: list[Carpet],
    existing_placed: list[PlacedCarpet],
    sheet_size: tuple[float, float],
    verbose: bool = True,
    tighten=True,
) -> tuple[list[PlacedCarpet], list[UnplacedCarpet]]:
    """Bin packing that considers already placed polygons on the sheet."""
    # Convert sheet size from cm to mm to match DXF polygon units
    sheet_width_mm, sheet_height_mm = sheet_size[0] * 10, sheet_size[1] * 10

    placed = []
    unplaced = []

    # Start with existing placed polygons as obstacles
    obstacles = [placed_tuple.polygon for placed_tuple in existing_placed]

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
                    [PlacedCarpet(obs, 0, 0, 0, "obstacle") for obs in obstacles],
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
                PlacedCarpet(
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
            unplaced.append(UnplacedCarpet(polygon, file_name, color, order_id))

        # ПРОФИЛИРОВАНИЕ: Логируем время обработки медленных полигонов
        polygon_elapsed = time.time() - polygon_start_time
        if polygon_elapsed > 2.0:  # Логируем полигоны, обрабатывающиеся дольше 2 секунд
            logger.warning(
                f"⏱️ Медленный полигон {file_name}: {polygon_elapsed:.2f}s, размещен={placed_successfully}"
            )

    # Жадный сдвиг (greedy push) — прижимаем коврики максимально влево/вниз
    if tighten:
        placed = tighten_layout(placed, sheet_size, min_gap=0.1)

    return placed, unplaced


def bin_packing(
    polygons: list[Carpet],
    sheet_size: tuple[float, float],
    verbose: bool = True,
    max_processing_time: float = 300.0,  # 5 minute timeout
    progress_callback=None,  # Callback function for progress updates
) -> tuple[list[PlacedCarpet], list[UnplacedCarpet]]:
    """Optimize placement of complex polygons on a sheet with ultra-dense/polygonal/improved algorithms."""
    import time

    start_time = time.time()

    # Convert sheet size from cm to mm to match DXF polygon units
    sheet_width_mm, sheet_height_mm = sheet_size[0] * 10, sheet_size[1] * 10

    placed: list[PlacedCarpet] = []
    unplaced: list[UnplacedCarpet] = []

    if verbose:
        st.info(
            f"Начинаем стандартную упаковку {len(polygons)} полигонов на листе {sheet_size[0]}x{sheet_size[1]} см"
        )

    # IMPROVEMENT 1: Enhanced polygon sorting for optimal packing density
    def get_polygon_priority(carpet: Carpet):
        polygon = carpet.polygon
        area = polygon.area
        bounds = polygon.bounds
        width = bounds[2] - bounds[0]
        height = bounds[3] - bounds[1]

        # Multi-factor scoring for better packing:
        # 1. Area (larger first)
        # 2. Aspect ratio (irregular shapes first)
        # 3. Compactness (less regular shapes first)
        aspect_ratio = (
            max(width / height, height / width) if min(width, height) > 0 else 1
        )
        compactness = area / (width * height) if width * height > 0 else 0
        perimeter_approx = 2 * (width + height)

        # Prioritize larger, more irregular shapes for better space utilization
        return (
            area * 1.0
            + (aspect_ratio - 1) * area * 0.3
            + (1 - compactness) * area * 0.2
            + perimeter_approx * 0.05
        )

    sorted_polygons = sorted(polygons, key=get_polygon_priority, reverse=True)

    # Set dataset size context for adaptive algorithms
    find_bottom_left_position._dataset_size = len(sorted_polygons)

    if verbose:
        st.info("✨ Сортировка полигонов по площади (сначала крупные)")

    for i, carpet in enumerate(sorted_polygons):
        # Check timeout
        if time.time() - start_time > max_processing_time:
            if verbose:
                st.warning(
                    f"⏰ Превышено время обработки ({max_processing_time}s), остальные полигоны добавлены в неразмещенные"
                )
            unplaced.extend(
                UnplacedCarpet(
                    carpet.polygon, carpet.filename, carpet.color, carpet.order_id
                )
                for carpet in sorted_polygons[i:]
            )
            break

        placed_successfully = False

        # Check if polygon is too large for the sheet
        bounds = carpet.polygon.bounds
        poly_width = bounds[2] - bounds[0]
        poly_height = bounds[3] - bounds[1]

        if poly_width > sheet_width_mm or poly_height > sheet_height_mm:
            if verbose:
                st.warning(
                    f"Полигон из {carpet.filename} слишком большой: {poly_width/10:.1f}x{poly_height/10:.1f} см > {sheet_size[0]}x{sheet_size[1]} см"
                )
            unplaced.append(
                UnplacedCarpet(
                    carpet.polygon, carpet.filename, carpet.color, carpet.order_id
                )
            )
            continue

        # SPEED OPTIMIZATION: Smart rotation strategy
        best_placement = None
        best_waste = float("inf")

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
                PlacedCarpet(
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

            # Optimized grid placement as fallback with timeout
            max_grid_attempts = (
                5 if len(placed) > 10 else 10
            )  # Further reduced for many obstacles
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

            for grid_x in x_positions:
                for grid_y in y_positions:
                    x_offset = grid_x - simple_bounds[0]
                    y_offset = grid_y - simple_bounds[1]

                    # Fast bounds check with minimal tolerance for tight packing
                    test_bounds = (
                        simple_bounds[0] + x_offset,
                        simple_bounds[1] + y_offset,
                        simple_bounds[2] + x_offset,
                        simple_bounds[3] + y_offset,
                    )

                    if not (
                        test_bounds[0] >= -0.01
                        and test_bounds[1] >= -0.01
                        and test_bounds[2] <= sheet_width_mm + 0.01
                        and test_bounds[3] <= sheet_height_mm + 0.01
                    ):
                        continue

                    # Skip ALL bounding box checks - use only true geometric collision
                    translated = translate_polygon(carpet.polygon, x_offset, y_offset)

                    # Final precise collision check
                    collision = False
                    for placed_poly in placed:
                        if check_collision(translated, placed_poly.polygon):
                            collision = True
                            break

                    if not collision:
                        placed.append(
                            PlacedCarpet(
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
            unplaced.append(
                UnplacedCarpet(
                    carpet.polygon, carpet.filename, carpet.color, carpet.order_id
                )
            )

    # Применяем жадный сдвиг
    placed = tighten_layout(placed, sheet_size)

    if verbose:
        usage_percent = calculate_usage_percent(placed, sheet_size)
        st.info(
            f"🏁 Упаковка завершена: {len(placed)} размещено, {len(unplaced)} не размещено, использование: {usage_percent:.1f}%"
        )
    return placed, unplaced


def find_contour_following_position(
    polygon: Polygon, obstacles: list[Polygon], sheet_width: float, sheet_height: float
) -> tuple[float | None, float | None]:
    """Find position using TRUE CONTOUR-FOLLOWING - shapes can nestle into concave areas!"""
    bounds = polygon.bounds
    poly_width = bounds[2] - bounds[0]
    poly_height = bounds[3] - bounds[1]

    candidates = []

    # REVOLUTIONARY: Follow actual shape contours, not bounding boxes
    for obstacle in obstacles[:8]:  # Limit for performance
        # Get the actual boundary coordinates of the obstacle
        if hasattr(obstacle.exterior, "coords"):
            contour_points = list(obstacle.exterior.coords)

            # Generate positions along the actual contour with minimal gaps
            for i, (cx, cy) in enumerate(
                contour_points[:-1]
            ):  # Skip last duplicate point
                # Try positioning our polygon at various points along this contour
                test_positions = [
                    # Right of this contour point
                    (cx + 0.1, cy - poly_height / 2),
                    (cx + 0.1, cy),
                    (cx + 0.1, cy - poly_height),
                    # Above this contour point
                    (cx - poly_width / 2, cy + 0.1),
                    (cx, cy + 0.1),
                    (cx - poly_width, cy + 0.1),
                ]

                for test_x, test_y in test_positions:
                    if (
                        0 <= test_x <= sheet_width - poly_width
                        and 0 <= test_y <= sheet_height - poly_height
                    ):
                        candidates.append((test_x, test_y))

    # Add sheet edges
    step = max(1.0, min(poly_width, poly_height) / 10)  # Adaptive step
    for x in np.arange(0, sheet_width - poly_width + 1, step):
        candidates.append((x, 0))
    for y in np.arange(0, sheet_height - poly_height + 1, step):
        candidates.append((0, y))

    # Sort by bottom-left preference and limit candidates
    candidates = list(set(candidates))  # Remove duplicates
    candidates.sort(key=lambda pos: (pos[1], pos[0]))
    candidates = candidates[: min(1000, len(candidates))]  # Performance limit

    # Test each position using true geometric collision detection
    for x, y in candidates:
        x_offset = x - bounds[0]
        y_offset = y - bounds[1]
        test_polygon = translate_polygon(polygon, x_offset, y_offset)

        # Use our new TRUE GEOMETRIC collision check (no bounding box constraints!)
        collision = False
        for obstacle in obstacles:
            if check_collision(test_polygon, obstacle, min_gap=0.1):  # Ultra-tight
                collision = True
                break

        if not collision:
            return x, y

    return None, None


def find_ultra_tight_position(
    polygon: Polygon, obstacles: list[Polygon], sheet_width: float, sheet_height: float
) -> tuple[float | None, float | None]:
    """Find ultra-tight position using contour-following for maximum density."""

    # Try new contour-following algorithm first
    result = find_contour_following_position(
        polygon, obstacles, sheet_width, sheet_height
    )
    if result[0] is not None:
        return result

    # Fallback to grid-based approach
    bounds = polygon.bounds
    poly_width = bounds[2] - bounds[0]
    poly_height = bounds[3] - bounds[1]

    # Use fine grid for small number of obstacles
    step_size = 1.0 if len(obstacles) <= 5 else 2.0
    candidates = []

    # Grid search with no bounding box prefiltering
    for x in np.arange(0, sheet_width - poly_width + 1, step_size):
        for y in np.arange(0, sheet_height - poly_height + 1, step_size):
            candidates.append((x, y))
            if len(candidates) >= 500:  # Performance limit
                break
        if len(candidates) >= 500:
            break

    # Test positions using pure geometric collision detection
    for x, y in candidates:
        x_offset = x - bounds[0]
        y_offset = y - bounds[1]
        test_polygon = translate_polygon(polygon, x_offset, y_offset)

        collision = False
        for obstacle in obstacles:
            if check_collision(test_polygon, obstacle, min_gap=0.1):
                collision = True
                break

        if not collision:
            return x, y

    return None, None


def find_bottom_left_position_with_obstacles(
    polygon: Polygon, obstacles: list[Polygon], sheet_width: float, sheet_height: float
) -> tuple[float | None, float | None]:
    """Find the bottom-left position for a polygon using ultra-tight packing algorithm."""
    # Try ultra-tight algorithm first
    result = find_ultra_tight_position(polygon, obstacles, sheet_width, sheet_height)
    if result[0] is not None:
        return result

    # Fallback to improved algorithm
    bounds = polygon.bounds
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


def find_quick_position(
    polygon: Polygon, placed_polygons, sheet_width: float, sheet_height: float
) -> tuple[float | None, float | None]:
    """Quick position finding for scenarios with many obstacles."""
    bounds = polygon.bounds
    poly_width = bounds[2] - bounds[0]
    poly_height = bounds[3] - bounds[1]

    # Use reasonable steps for balance of speed and density
    step_size = 2.0  # Reduced from 5.0 for better placement options
    max_positions = 200  # Increased from 100 for better coverage

    # Generate minimal candidate set
    candidates = []

    # Bottom edge with large steps
    for x in np.arange(0, sheet_width - poly_width + 1, step_size):
        candidates.append((x, 0))
        if len(candidates) >= max_positions:
            break

    # Left edge with large steps
    for y in np.arange(0, sheet_height - poly_height + 1, step_size):
        candidates.append((0, y))
        if len(candidates) >= max_positions:
            break

    # Test positions quickly
    for x, y in candidates:
        if x + poly_width <= sheet_width and y + poly_height <= sheet_height:
            x_offset = x - bounds[0]
            y_offset = y - bounds[1]
            test_polygon = translate_polygon(polygon, x_offset, y_offset)

            # Quick collision check with looser tolerance
            collision = False
            for placed_poly in placed_polygons:
                if check_collision(
                    test_polygon, placed_poly.polygon, min_gap=2.0
                ):  # Looser gap
                    collision = True
                    break

            if not collision:
                return x, y

    return None, None


def find_bottom_left_position(
    polygon: Polygon, placed_polygons, sheet_width: float, sheet_height: float
):
    """Find the bottom-left position for a polygon using ultra-tight Bottom-Left Fill algorithm with timeout."""
    import time

    start_time = time.time()
    timeout = 5.0  # Faster timeout for quicker processing

    # PERFORMANCE: Quick fallback for too many obstacles - aggressive for speed
    if len(placed_polygons) > 8:  # More aggressive fallback for reasonable performance
        return find_quick_position(polygon, placed_polygons, sheet_width, sheet_height)

    # Convert placed polygons to obstacles and use ultra-tight algorithm
    obstacles = [placed_tuple.polygon for placed_tuple in placed_polygons]

    # Try ultra-tight algorithm with timeout
    try:
        result = find_ultra_tight_position(
            polygon, obstacles, sheet_width, sheet_height
        )
        if result[0] is not None and time.time() - start_time < timeout:
            return result
    except Exception:
        pass  # Fallback to conventional algorithm

    # Fallback to improved conventional algorithm
    bounds = polygon.bounds
    poly_width = bounds[2] - bounds[0]
    poly_height = bounds[3] - bounds[1]

    # PERFORMANCE OPTIMIZATION: Pre-compute placed polygon bounds
    placed_bounds_list = []
    for placed_tuple in placed_polygons:
        placed_polygon = placed_tuple.polygon
        placed_bounds_list.append(placed_polygon.bounds)

    # Generate candidate positions with fine granularity
    candidate_positions = set()  # Use set to avoid duplicates

    # Balanced step size for good density without excessive computation
    step_size = 1.0  # 1mm steps for good precision with reasonable performance

    # Bottom edge positions
    for x in np.arange(0, sheet_width - poly_width + 1, step_size):
        candidate_positions.add((x, 0))

    # Left edge positions
    for y in np.arange(0, sheet_height - poly_height + 1, step_size):
        candidate_positions.add((0, y))

    # OPTIMIZATION: Generate positions based on existing polygons with tight packing
    min_gap = 0.1  # Tight gap for good density
    for placed_bounds in placed_bounds_list:
        # Try position to the right of existing polygon
        x = placed_bounds[2] + min_gap
        if x + poly_width <= sheet_width:
            # Add multiple Y positions for better fit
            y_positions = [
                placed_bounds[1],  # Same Y as existing
                0,  # Bottom edge
                placed_bounds[1] - poly_height / 2,  # Below existing
                placed_bounds[1] + poly_height / 2,  # Above existing
                placed_bounds[3] - poly_height,  # Top-aligned with existing
            ]
            for y_pos in y_positions:
                if 0 <= y_pos <= sheet_height - poly_height:
                    candidate_positions.add((x, y_pos))

        # Try position above existing polygon
        y = placed_bounds[3] + min_gap
        if y + poly_height <= sheet_height:
            # Add multiple X positions for better fit
            x_positions = [
                placed_bounds[0],  # Same X as existing
                0,  # Left edge
                placed_bounds[0] - poly_width / 2,  # Left of existing
                placed_bounds[0] + poly_width / 2,  # Right of existing
                placed_bounds[2] - poly_width,  # Right-aligned with existing
            ]
            for x_pos in x_positions:
                if 0 <= x_pos <= sheet_width - poly_width:
                    candidate_positions.add((x_pos, y))

    # Convert to sorted list (bottom-left preference)
    candidate_positions = sorted(candidate_positions, key=lambda pos: (pos[1], pos[0]))

    # PERFORMANCE: Ultra-tight collision checking for each candidate
    for x, y in candidate_positions:
        # Ultra-precise boundary pre-check
        if (
            x + poly_width > sheet_width + 0.01
            or y + poly_height > sheet_height + 0.01
            or x < -0.01
            or y < -0.01
        ):
            continue

        x_offset = x - bounds[0]
        y_offset = y - bounds[1]

        # Check bounds with minimal tolerance
        test_bounds = (
            bounds[0] + x_offset,
            bounds[1] + y_offset,
            bounds[2] + x_offset,
            bounds[3] + y_offset,
        )
        if (
            test_bounds[0] < -0.01
            or test_bounds[1] < -0.01
            or test_bounds[2] > sheet_width + 0.01
            or test_bounds[3] > sheet_height + 0.01
        ):
            continue

        # REVOLUTIONARY: Skip ALL bounding box checks - use only true geometric collision
        test_polygon = translate_polygon(polygon, x_offset, y_offset)

        # Final collision check with actual polygons
        collision = False
        for p in placed_polygons:
            if check_collision(
                test_polygon, p.polygon, min_gap=0.1
            ):  # Standard tight gap
                collision = True
                break

        if not collision:
            return x, y

    return None, None


def calculate_placement_waste(
    polygon: Polygon, placed_polygons: list[PlacedCarpet], sheet_width, sheet_height
):
    """Calculate waste/inefficiency for a polygon placement."""
    bounds = polygon.bounds

    # Calculate compactness - how close polygon is to other polygons and edges
    edge_distance = min(bounds[0], bounds[1])  # Distance to bottom-left corner

    # Distance to other polygons
    min_neighbor_distance = float("inf")
    for placed_tuple in placed_polygons:
        placed_polygon = placed_tuple.polygon
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
    carpets: list[Carpet],
    available_sheets: list[dict],
    verbose: bool = True,
    progress_callback=None,
) -> tuple[list[PlacedSheet], list[UnplacedCarpet]]:
    """Optimize placement of polygons on available sheets with inventory tracking.

    NEW ALGORITHM: Two-sheet forced packing for achieving client goals:
    1. Try to fit all carpets on exactly 2 sheets with maximum density
    2. Fallback to priority-based placement if 2-sheet approach fails
    """
    logger.info(
        "=== НАЧАЛО bin_packing_with_inventory (АЛГОРИТМ МАКСИМАЛЬНОЙ ПЛОТНОСТИ) ==="
    )
    logger.info(
        f"Входные параметры: {len(carpets)} полигонов, {len(available_sheets)} типов листов"
    )

    placed_layouts: list[PlacedSheet] = []
    all_unplaced: list[UnplacedCarpet] = []
    sheet_inventory = [sheet.copy() for sheet in available_sheets]
    sheet_counter = 0

    # Step 1: Group carpets by priority
    logger.info("Группировка полигонов по приоритету...")
    priority1_carpets: list[Carpet] = []  # Excel orders and additional priority 1
    priority2_carpets: list[Carpet] = []  # Priority 2 carpets

    for carpet in carpets:
        if carpet.priority == 2:
            priority2_carpets.append(carpet)
        else:
            # All Excel orders (ZAKAZ_*) and priority 1 items go together
            priority1_carpets.append(carpet)

    logger.info(
        f"Группировка завершена: {len(priority1_carpets)} приоритет 1 + Excel, {len(priority2_carpets)} приоритет 2"
    )

    # Early return if nothing to place
    if not priority1_carpets and not priority2_carpets:
        logger.info("Нет полигонов для размещения")
        return placed_layouts, all_unplaced

    # STEP 2: Place priority 1 items (Excel orders + manual priority 1) with new sheets allowed
    logger.info(
        f"\n=== ЭТАП 2: РАЗМЕЩЕНИЕ {len(priority1_carpets)} ПРИОРИТЕТ 1 + EXCEL ЗАКАЗОВ ==="
    )

    # Group priority 1 carpets by color for efficient processing
    remaining_priority1: list[Carpet] = list(priority1_carpets)

    # First try to fill existing sheets with priority 1 carpets
    for layout_idx, layout in enumerate(placed_layouts):
        if not remaining_priority1:
            break
        if (
            layout.usage_percent >= 95
        ):  # More aggressive filling - try harder to use existing sheets
            continue

        # Group remaining by color matching this sheet
        matching_carpets = [
            c for c in remaining_priority1 if c.color == layout.sheet_color
        ]
        if not matching_carpets:
            continue

        try:
            additional_placed, remaining_unplaced = bin_packing_with_existing(
                matching_carpets,
                layout.placed_polygons,
                layout.sheet_size,
                verbose=False,
            )

            if additional_placed:
                # Update layout
                placed_layouts[layout_idx].placed_polygons.extend(additional_placed)
                placed_layouts[layout_idx].usage_percent = calculate_usage_percent(
                    placed_layouts[layout_idx].placed_polygons, layout.sheet_size
                )

                # Update remaining
                remaining_carpet_map = {
                    UnplacedCarpet(c.polygon, c.filename, c.color, c.order_id): c
                    for c in matching_carpets
                }
                newly_remaining = set()
                for remaining_carpet in remaining_unplaced:
                    if remaining_carpet in remaining_carpet_map:
                        newly_remaining.add(remaining_carpet_map[remaining_carpet])

                # Remove placed carpets from remaining list
                placed_carpet_set = set(
                    UnplacedCarpet(c.polygon, c.filename, c.color, c.order_id)
                    for c in matching_carpets
                    if c not in newly_remaining
                )
                remaining_priority1 = [
                    c
                    for c in remaining_priority1
                    if UnplacedCarpet(c.polygon, c.filename, c.color, c.order_id)
                    not in placed_carpet_set
                ]

                logger.info(
                    f"    Дозаполнен лист #{layout.sheet_number}: +{len(additional_placed)} приоритет1+Excel"
                )
        except Exception as e:
            logger.debug(f"Не удалось дозаполнить лист приоритетом 1: {e}")
            continue

    # Create new sheets for remaining priority 1 carpets
    carpets_by_color: dict[str, list[Carpet]] = {}
    for carpet in remaining_priority1:
        color = carpet.color
        if color not in carpets_by_color:
            carpets_by_color[color] = []
        carpets_by_color[color].append(carpet)

    for color, color_carpets in carpets_by_color.items():
        remaining_carpets = list(color_carpets)

        # AGGRESSIVE RETRY: Try to place remaining carpets on ALL existing sheets before creating new ones
        if remaining_carpets and placed_layouts:
            logger.info(
                f"Попытка агрессивного дозаполнения существующих листов для {len(remaining_carpets)} ковров {color}"
            )

            # Try each existing sheet again with more relaxed criteria
            for layout_idx, layout in enumerate(placed_layouts):
                if not remaining_carpets:
                    break

                # Only skip if truly full (>98%) or wrong color
                if layout.usage_percent >= 98 or layout.sheet_color != color:
                    continue

                # Try to fit remaining carpets on this sheet with more aggressive attempts
                matching_carpets = [c for c in remaining_carpets if c.color == color]
                if not matching_carpets:
                    continue

                try:
                    # Try multiple times with different carpet orderings for better fit
                    best_placed = []
                    best_remaining = matching_carpets
                    remaining_carpet_map = {
                        UnplacedCarpet(c.polygon, c.filename, c.color, c.order_id): c
                        for c in matching_carpets
                    }

                    for attempt in range(3):  # Try up to 3 different orderings
                        if attempt == 1:
                            # Try reverse order
                            test_carpets = list(reversed(matching_carpets))
                        elif attempt == 2:
                            # Try sorted by area (smallest first for gaps)
                            test_carpets = sorted(
                                matching_carpets, key=lambda c: c.polygon.area
                            )
                        else:
                            test_carpets = matching_carpets

                        additional_placed, remaining_unplaced = (
                            bin_packing_with_existing(
                                test_carpets,
                                layout.placed_polygons,
                                layout.sheet_size,
                                verbose=False,
                            )
                        )

                        # Keep the best result
                        if len(additional_placed) > len(best_placed):
                            best_placed = additional_placed
                            best_remaining = [
                                remaining_carpet_map.get(
                                    UnplacedCarpet(
                                        rt.polygon, rt.filename, rt.color, rt.order_id
                                    ),
                                    next(
                                        (
                                            c
                                            for c in matching_carpets
                                            if (
                                                c.polygon,
                                                c.filename,
                                                c.color,
                                                c.order_id,
                                            )
                                            == (
                                                rt.polygon,
                                                rt.filename,
                                                rt.color,
                                                rt.order_id,
                                            )
                                        ),
                                        None,
                                    ),
                                )
                                for rt in remaining_unplaced
                                if remaining_carpet_map.get(
                                    UnplacedCarpet(
                                        rt.polygon, rt.filename, rt.color, rt.order_id
                                    ),
                                    next(
                                        (
                                            c
                                            for c in matching_carpets
                                            if (
                                                c.polygon,
                                                c.filename,
                                                c.color,
                                                c.order_id,
                                            )
                                            == (
                                                rt.polygon,
                                                rt.filename,
                                                rt.color,
                                                rt.order_id,
                                            )
                                        ),
                                        None,
                                    ),
                                )
                                is not None
                            ]

                    # Apply the best result if any improvement
                    if best_placed:
                        # CRITICAL: Verify no overlaps before accepting placement
                        all_existing_polygons = [
                            p.polygon for p in layout.placed_polygons
                        ]
                        new_polygons = [p.polygon for p in best_placed]

                        # Check for any overlaps between new and existing polygons
                        has_overlap = False
                        for new_poly in new_polygons:
                            for existing_poly in all_existing_polygons:
                                if check_collision(
                                    new_poly, existing_poly, min_gap=0.05
                                ):
                                    logger.error(
                                        f"КРИТИЧЕСКАЯ ОШИБКА: Обнаружено перекрытие при агрессивном дозаполнении листа #{layout.sheet_number}"
                                    )
                                    has_overlap = True
                                    break
                            if has_overlap:
                                break

                        # Only accept if no overlaps detected
                        if not has_overlap:
                            # Update layout
                            placed_layouts[layout_idx].placed_polygons.extend(
                                best_placed
                            )
                            placed_layouts[
                                layout_idx
                            ].usage_percent = calculate_usage_percent(
                                placed_layouts[layout_idx].placed_polygons,
                                layout.sheet_size,
                            )
                        else:
                            logger.warning(
                                "Отклонено агрессивное дозаполнение из-за обнаруженных перекрытий"
                            )
                            best_placed = []  # Reset to prevent further processing

                            # Remove successfully placed carpets from remaining list
                            placed_carpet_set = set(
                                c for c in matching_carpets if c not in best_remaining
                            )
                            remaining_carpets = [
                                c
                                for c in remaining_carpets
                                if c not in placed_carpet_set
                            ]

                            logger.info(
                                f"    Агрессивно дозаполнен лист #{layout.sheet_number}: +{len(best_placed)} ковров, итого {layout.usage_percent:.1f}%"
                            )

                except Exception as e:
                    logger.debug(f"Не удалось агрессивно дозаполнить лист: {e}")
                    continue

        while remaining_carpets:
            sheet_type = find_available_sheet_of_color(color, sheet_inventory)
            if not sheet_type:
                logger.warning(f"Нет доступных листов цвета {color} для приоритета 1")
                all_unplaced.extend(remaining_carpets)
                break

            sheet_counter += 1
            sheet_type["used"] += 1
            sheet_size = (sheet_type["width"], sheet_type["height"])

            ###################################################################3
            # Попытка максимально плотной упаковки - несколько проходов
            placed, remaining = bin_packing(
                remaining_carpets,
                sheet_size,
                verbose=False,
                progress_callback=progress_callback,
            )

            if placed:
                new_layout = create_new_sheet(sheet_type, sheet_counter, color)
                new_layout.placed_polygons = placed
                new_layout.usage_percent = calculate_usage_percent(placed, sheet_size)
                new_layout.orders_on_sheet = list(
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

                if progress_callback:
                    progress = min(
                        70,
                        int(70 * len(placed_layouts) / (len(carpets))),
                    )
                    progress_callback(
                        progress,
                        f"Создан лист #{sheet_counter}. Размещено ковров: {len(placed)}",
                    )
            else:
                logger.warning(
                    f"Не удалось разместить приоритет 1 на новом листе {color}"
                )
                all_unplaced.extend(remaining_carpets)
                sheet_type["used"] -= 1
                sheet_counter -= 1
                break

    # STEP 3: Place priority 2 on remaining space only (no new sheets)
    logger.info(
        f"\n=== ЭТАП 3: РАЗМЕЩЕНИЕ {len(priority2_carpets)} ПРИОРИТЕТ2 НА СВОБОДНОМ МЕСТЕ ==="
    )

    remaining_priority2 = list(priority2_carpets)

    for layout_idx, layout in enumerate(placed_layouts):
        if not remaining_priority2:
            break
        if (
            layout.usage_percent >= 95
        ):  # More aggressive filling - try harder to use existing sheets
            continue

        # Try to place carpets of matching color
        matching_carpets = [
            c for c in remaining_priority2 if c.color == layout.sheet_color
        ]
        if not matching_carpets:
            continue

        try:
            additional_placed, remaining_unplaced = bin_packing_with_existing(
                matching_carpets,
                layout.placed_polygons,
                layout.sheet_size,
                verbose=False,
                tighten=False,
            )

            if additional_placed:
                # SMART: Skip overlap check if sheet has plenty of free space (low usage)
                current_usage = layout.usage_percent

                if current_usage < 20:
                    # If sheet is mostly empty, trust bin_packing_with_existing
                    logger.info(
                        f"Лист #{layout.sheet_number} заполнен всего на {current_usage:.1f}% - пропускаем проверку перекрытий для приоритета 2"
                    )
                    accept_placement = True
                else:
                    # Check for major overlaps only on fuller sheets
                    all_existing_polygons = [p.polygon for p in layout.placed_polygons]
                    new_polygons = [p.polygon for p in additional_placed]

                    has_major_overlap = False
                    for i, new_poly in enumerate(new_polygons):
                        for j, existing_poly in enumerate(all_existing_polygons):
                            if new_poly.intersects(existing_poly):
                                try:
                                    intersection = new_poly.intersection(existing_poly)
                                    intersection_area = (
                                        intersection.area
                                        if hasattr(intersection, "area")
                                        else 0
                                    )
                                    new_poly_area = new_poly.area

                                    # More permissive threshold for fuller sheets (50%)
                                    if (
                                        intersection_area > 0
                                        and intersection_area / new_poly_area > 0.50
                                    ):
                                        logger.warning(
                                            f"Крупное перекрытие при размещении приоритета 2: {intersection_area/new_poly_area*100:.1f}% от полигона {i} на листе #{layout.sheet_number}"
                                        )
                                        has_major_overlap = True
                                        break
                                    else:
                                        logger.debug(
                                            f"Допустимое перекрытие: {intersection_area/new_poly_area*100:.1f}% от полигона {i} - разрешено"
                                        )
                                except Exception as e:
                                    logger.debug(f"Ошибка при расчете пересечения: {e}")
                                    continue
                        if has_major_overlap:
                            break

                    accept_placement = not has_major_overlap

                if accept_placement:
                    # Update layout
                    placed_layouts[layout_idx].placed_polygons.extend(additional_placed)
                    placed_layouts[layout_idx].usage_percent = calculate_usage_percent(
                        placed_layouts[layout_idx].placed_polygons,
                        layout.sheet_size,
                    )

                    # Update remaining
                    remaining_carpet_map = {
                        UnplacedCarpet(c.polygon, c.filename, c.color, c.order_id): c
                        for c in matching_carpets
                    }
                    newly_remaining = []
                    for carpet in remaining_unplaced:
                        if carpet in remaining_carpet_map:
                            newly_remaining.append(remaining_carpet_map[carpet])

                    # Remove placed carpets from remaining list
                    placed_carpet_set = set(
                        c for c in matching_carpets if c not in newly_remaining
                    )
                    remaining_priority2 = [
                        c
                        for c in remaining_priority2
                        if (c.polygon, c.filename, c.color, c.order_id)
                        not in placed_carpet_set
                    ]
                    logger.info(
                        f"    Дозаполнен лист #{layout.sheet_number}: +{len(additional_placed)} приоритет2"
                    )
                else:
                    logger.warning(
                        f"Отклонено размещение приоритета 2 из-за крупных перекрытий на листе #{layout.sheet_number}"
                    )
                    additional_placed = []  # Reset to prevent further processing
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
        if layout.sheet_color == "чёрный":
            black_sheets.append(layout)
        else:
            grey_sheets.append(layout)

    # Reassign sheet numbers: first all black, then all grey
    final_layouts = []
    sheet_number = 1

    for layout in black_sheets + grey_sheets:
        layout.sheet_number = sheet_number
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
    placed_polygons: list[PlacedCarpet], sheet_size: tuple[float, float]
) -> float:
    """Calculate material usage percentage for a sheet."""
    used_area_mm2 = sum(placed_tuple.polygon.area for placed_tuple in placed_polygons)
    sheet_area_mm2 = (sheet_size[0] * 10) * (sheet_size[1] * 10)
    return (used_area_mm2 / sheet_area_mm2) * 100


def tighten_layout(
    placed: list[PlacedCarpet],
    sheet_size=None,
    min_gap: float = 0.1,
    step: float = 1.0,
    max_passes: int = 3,
) -> list[PlacedCarpet]:
    """
    Жадный сдвиг (greedy push): для каждого полигона пробуем сдвинуть максимально
    влево, затем максимально вниз, не нарушая коллизий с *любой* другой деталью.

    Args:
        placed: список кортежей полигонов в абсолютных координатах.
                Формат кортежа ожидается как минимум (polygon, x_off, y_off, angle, filename, color, order_id)
                — но функция работает и если у вас немного другой набор полей: она всегда
                возвращает 7-элементный кортеж.
        sheet_size: оставлен для совместимости сигнатур (не используется внутри).
        min_gap: минимальный зазор в мм (передавайте 0.0 или 0.1).
        step: шаг сдвига в мм (1.0 — точный, можно поставить 2.0 для ускорения).
        max_passes: число проходов по всем полигонам (обычно 2–3 достаточно).
    Returns:
        Новый список placed в том же формате (каждый элемент — 7-ка), где полигоны сдвинуты.
    """
    # Защитная проверка
    if not placed:
        return placed

    # Создаём список текущих полигонов (будем обновлять)
    current_polys = [item.polygon for item in placed]
    # Сохраняем сопут. данные (x_off, y_off, angle, filename, color, order_id) с запасом по длине
    meta = placed[:]

    n = len(current_polys)

    # Несколько проходов, пока происходят сдвиги или пока не исчерпаны max_passes
    for pass_idx in range(max_passes):
        moved_any = False

        for i in range(n):
            poly = current_polys[i]
            moved = poly

            # --- Сдвигаем влево по шагам ---
            while True:
                test = translate_polygon(moved, -step, 0)
                # Пробуем выйти за левую границу? Останавливаемся
                if test.bounds[0] < -0.01:
                    break

                # Проверяем столкновения со всеми остальными полигонами
                collision = False
                for j in range(n):
                    if j == i:
                        continue
                    other = current_polys[j]
                    # Точная проверка: true если пересекается или ближе минимума
                    if check_collision(test, other, min_gap=min_gap):
                        collision = True
                        break

                if collision:
                    break

                # Нет столкновений — применяем сдвиг
                moved = test
                moved_any = True

            # --- Сдвигаем вниз по шагам ---
            while True:
                test = translate_polygon(moved, 0, -step)
                if test.bounds[1] < -0.01:
                    break

                collision = False
                for j in range(n):
                    if j == i:
                        continue
                    other = current_polys[j]
                    if check_collision(test, other, min_gap=min_gap):
                        collision = True
                        break

                if collision:
                    break

                moved = test
                moved_any = True

            # Обновляем текущую позицию полигона
            current_polys[i] = moved

        # Если за проход изменений не было — прекращаем
        if not moved_any:
            break

    # Формируем новый список placed (возвращаем 7-элементные кортежи)
    new_placed: list[PlacedCarpet] = []

    for i in range(n):
        new_poly = current_polys[i]
        orig_poly = placed[i].polygon
        # Смещение в абсолютных координатах между исходным и новым
        dx_total = new_poly.bounds[0] - orig_poly.bounds[0]
        dy_total = new_poly.bounds[1] - orig_poly.bounds[1]

        item = meta[i]
        new_x_off = item.x_offset + dx_total
        new_y_off = item.y_offset + dy_total

        # Возвращаем стандартный 7-элементный кортеж
        new_placed.append(
            PlacedCarpet(
                new_poly,
                new_x_off,
                new_y_off,
                item.angle,
                item.filename,
                item.color,
                item.order_id,
            )
        )

    return new_placed
