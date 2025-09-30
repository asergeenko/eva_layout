"""Fast geometry operations using Numba JIT compilation for critical performance."""

import numpy as np
from numba import jit, prange
from shapely.strtree import STRtree


@jit(nopython=True, cache=True, fastmath=True)
def bounds_intersect(bounds1, bounds2, gap=0.1):
    """Ultra-fast bounding box intersection check with gap tolerance.

    bounds format: (minx, miny, maxx, maxy)
    Returns True if bounding boxes are closer than gap.
    """
    # Check if bounding boxes are separated by more than gap
    if bounds1[2] + gap < bounds2[0]:  # bounds1 is to the left
        return False
    if bounds2[2] + gap < bounds1[0]:  # bounds2 is to the left
        return False
    if bounds1[3] + gap < bounds2[1]:  # bounds1 is below
        return False
    if bounds2[3] + gap < bounds1[1]:  # bounds2 is below
        return False
    return True


@jit(nopython=True, cache=True, fastmath=True)
def bbox_distance_squared(bounds1, bounds2):
    """Calculate squared distance between two bounding boxes.

    Returns 0 if boxes overlap, otherwise squared distance between closest points.
    """
    dx = max(0.0, max(bounds1[0] - bounds2[2], bounds2[0] - bounds1[2]))
    dy = max(0.0, max(bounds1[1] - bounds2[3], bounds2[1] - bounds1[3]))
    return dx * dx + dy * dy


@jit(nopython=True, cache=True, fastmath=True)
def point_in_bounds(x, y, bounds):
    """Check if point (x, y) is within bounds."""
    return bounds[0] <= x <= bounds[2] and bounds[1] <= y <= bounds[3]


@jit(nopython=True, cache=True, fastmath=True)
def bounds_within_sheet(bounds, sheet_width, sheet_height, tolerance=0.1):
    """Check if bounds fit within sheet dimensions."""
    return (
        bounds[0] >= -tolerance
        and bounds[1] >= -tolerance
        and bounds[2] <= sheet_width + tolerance
        and bounds[3] <= sheet_height + tolerance
    )


@jit(nopython=True, cache=True, fastmath=True)
def translate_bounds(bounds, dx, dy):
    """Translate bounding box by (dx, dy)."""
    return (bounds[0] + dx, bounds[1] + dy, bounds[2] + dx, bounds[3] + dy)


@jit(nopython=True, cache=True, fastmath=True, parallel=True)
def filter_positions_by_bounds_parallel(
    positions, poly_bounds, obstacles_bounds, sheet_width, sheet_height, min_gap=2.0
):
    """Filter positions using parallel bounding box checks.

    Returns array of valid position indices.
    """
    n_positions = len(positions)
    n_obstacles = len(obstacles_bounds)
    valid = np.ones(n_positions, dtype=np.bool_)

    poly_width = poly_bounds[2] - poly_bounds[0]
    poly_height = poly_bounds[3] - poly_bounds[1]

    for i in prange(n_positions):
        x, y = positions[i]

        # Check sheet boundaries
        test_bounds = (x, y, x + poly_width, y + poly_height)
        if not bounds_within_sheet(test_bounds, sheet_width, sheet_height):
            valid[i] = False
            continue

        # Check collision with obstacles using bounding boxes
        for j in range(n_obstacles):
            if bounds_intersect(test_bounds, obstacles_bounds[j], min_gap):
                valid[i] = False
                break

    return valid


@jit(nopython=True, cache=True, fastmath=True)
def filter_positions_by_bounds(
    positions, poly_bounds, obstacles_bounds, sheet_width, sheet_height, min_gap=2.0
):
    """Filter positions using bounding box checks (non-parallel version).

    Returns array of valid position indices.
    """
    n_positions = len(positions)
    n_obstacles = len(obstacles_bounds)
    valid = np.ones(n_positions, dtype=np.bool_)

    poly_width = poly_bounds[2] - poly_bounds[0]
    poly_height = poly_bounds[3] - poly_bounds[1]

    for i in range(n_positions):
        x, y = positions[i]

        # Check sheet boundaries
        test_bounds = (x, y, x + poly_width, y + poly_height)
        if not bounds_within_sheet(test_bounds, sheet_width, sheet_height):
            valid[i] = False
            continue

        # Check collision with obstacles using bounding boxes
        for j in range(n_obstacles):
            if bounds_intersect(test_bounds, obstacles_bounds[j], min_gap):
                valid[i] = False
                break

    return valid


@jit(nopython=True, cache=True, fastmath=True)
def generate_candidate_positions(
    poly_width,
    poly_height,
    sheet_width,
    sheet_height,
    obstacles_bounds,
    step_size=2.0,
    max_candidates=2000,
):
    """Generate candidate positions using smart placement strategy.

    Returns array of (x, y) positions.
    """
    candidates = []

    # CRITICAL: Ultra-fine grid for bottom-left corner (most important region)
    corner_size = min(200, sheet_width / 3, sheet_height / 3)
    x = 0.0
    ultra_fine_step = 1.0  # 1mm steps in critical region
    while (
        x <= min(corner_size, sheet_width - poly_width)
        and len(candidates) < max_candidates // 4
    ):
        candidates.append((x, 0.0))
        x += ultra_fine_step

    y = 0.0
    while (
        y <= min(corner_size, sheet_height - poly_height)
        and len(candidates) < max_candidates // 4
    ):
        candidates.append((0.0, y))
        y += ultra_fine_step

    # Fine grid for rest of bottom edge (critical for tight packing)
    x = corner_size if corner_size < sheet_width - poly_width else 0.0
    fine_step = min(step_size, 3.0)  # 3mm max for edges
    while x <= sheet_width - poly_width and len(candidates) < max_candidates // 2:
        candidates.append((x, 0.0))
        x += fine_step

    # Fine grid for rest of left edge
    y = corner_size if corner_size < sheet_height - poly_height else 0.0
    while y <= sheet_height - poly_height and len(candidates) < max_candidates // 2:
        candidates.append((0.0, y))
        y += fine_step

    # Dense positions based on obstacles (CRITICAL for quality)
    n_obstacles = len(obstacles_bounds)
    gaps = [0.5, 1.0, 2.0, 3.0]  # Try multiple gap distances

    for i in range(n_obstacles):
        if len(candidates) >= max_candidates:
            break

        obs_bounds = obstacles_bounds[i]

        for gap in gaps:
            # Right of obstacle - multiple Y positions
            x = obs_bounds[2] + gap
            if x + poly_width <= sheet_width:
                # Try aligning with obstacle edges
                candidates.append((x, obs_bounds[1]))  # Bottom-aligned
                candidates.append((x, obs_bounds[3] - poly_height))  # Top-aligned
                candidates.append((x, 0.0))  # Bottom of sheet

                # Try positions along obstacle height
                y_step = max(fine_step, (obs_bounds[3] - obs_bounds[1]) / 3)
                y = obs_bounds[1]
                while y <= obs_bounds[3] and y + poly_height <= sheet_height:
                    candidates.append((x, y))
                    y += y_step

            # Above obstacle - multiple X positions
            y = obs_bounds[3] + gap
            if y + poly_height <= sheet_height:
                # Try aligning with obstacle edges
                candidates.append((obs_bounds[0], y))  # Left-aligned
                candidates.append((obs_bounds[2] - poly_width, y))  # Right-aligned
                candidates.append((0.0, y))  # Left of sheet

                # Try positions along obstacle width
                x_step = max(fine_step, (obs_bounds[2] - obs_bounds[0]) / 3)
                x = obs_bounds[0]
                while x <= obs_bounds[2] and x + poly_width <= sheet_width:
                    candidates.append((x, y))
                    x += x_step

            # Left of obstacle
            x = obs_bounds[0] - poly_width - gap
            if x >= 0:
                candidates.append((x, obs_bounds[1]))
                candidates.append((x, 0.0))

            # Below obstacle
            y = obs_bounds[1] - poly_height - gap
            if y >= 0:
                candidates.append((obs_bounds[0], y))
                candidates.append((0.0, y))

    # Return as numpy array
    # Note: Some duplicates may remain, but will be filtered by sorting/selection later
    if len(candidates) == 0:
        return np.empty((0, 2), dtype=np.float64)

    return np.array(candidates, dtype=np.float64)


def remove_duplicate_positions(positions, precision=0.1):
    """Remove duplicate positions efficiently (non-JIT for flexibility).

    Args:
        positions: numpy array of (x, y) positions
        precision: rounding precision in mm (default 0.1mm)

    Returns:
        numpy array with duplicates removed
    """
    if len(positions) == 0:
        return positions

    # Round to precision and find unique
    rounded = np.round(positions / precision) * precision
    _, unique_indices = np.unique(rounded, axis=0, return_index=True)

    return positions[unique_indices]


class SpatialIndexCache:
    """Cache for STRtree spatial index to avoid rebuilding."""

    def __init__(self):
        self.tree = None
        self.polygons = None
        self.version = 0

    def update(self, polygons):
        """Update the spatial index if polygons changed."""
        # Check if we need to rebuild
        if self.polygons is None or len(polygons) != len(self.polygons):
            self._rebuild(polygons)
            return

        # Simple check - compare object ids
        needs_rebuild = False
        for i, poly in enumerate(polygons):
            if poly is not self.polygons[i]:
                needs_rebuild = True
                break

        if needs_rebuild:
            self._rebuild(polygons)

    def _rebuild(self, polygons):
        """Rebuild the spatial index."""
        if polygons:
            self.tree = STRtree(polygons)
            self.polygons = list(polygons)
        else:
            self.tree = None
            self.polygons = []
        self.version += 1

    def query(self, polygon):
        """Query the spatial index."""
        if self.tree is None:
            return []
        return self.tree.query(polygon)

    def is_empty(self):
        """Check if index is empty."""
        return self.tree is None or not self.polygons


def check_collision_fast_indexed(polygon, spatial_cache, min_gap=0.1):
    """Fast collision check using cached spatial index.

    Args:
        polygon: Shapely Polygon to test
        spatial_cache: SpatialIndexCache instance
        min_gap: Minimum gap between polygons

    Returns:
        True if collision detected, False otherwise
    """
    if spatial_cache.is_empty():
        return False

    if not polygon.is_valid:
        return True

    # Query spatial index for nearby polygons
    possible_indices = list(spatial_cache.query(polygon))

    if not possible_indices:
        return False

    # Fast bounding box pre-check
    poly_bounds = polygon.bounds
    poly_bounds_tuple = (poly_bounds[0], poly_bounds[1], poly_bounds[2], poly_bounds[3])

    for idx in possible_indices:
        other_poly = spatial_cache.polygons[idx]
        other_bounds = other_poly.bounds
        other_bounds_tuple = (
            other_bounds[0],
            other_bounds[1],
            other_bounds[2],
            other_bounds[3],
        )

        # Fast bounding box distance check
        if bounds_intersect(poly_bounds_tuple, other_bounds_tuple, min_gap):
            # Do precise geometric check only if bounding boxes are close
            if polygon.intersects(other_poly):
                return True

            # Check actual geometric distance
            try:
                dist = polygon.distance(other_poly)
                if dist < min_gap:
                    return True
            except Exception:
                # Conservative on errors
                return True

    return False


def extract_bounds_array(polygons):
    """Extract bounding boxes as numpy array for fast operations.

    Args:
        polygons: List of Shapely Polygons

    Returns:
        numpy array of shape (n, 4) with bounds (minx, miny, maxx, maxy)
    """
    n = len(polygons)
    bounds_array = np.empty((n, 4), dtype=np.float64)

    for i, poly in enumerate(polygons):
        b = poly.bounds
        bounds_array[i] = [b[0], b[1], b[2], b[3]]

    return bounds_array


@jit(nopython=True, cache=True, fastmath=True)
def quick_bounds_check_batch(
    candidate_positions, poly_width, poly_height, sheet_width, sheet_height, poly_bounds
):
    """Fast batch boundary checking for candidate positions.

    Returns array of booleans indicating valid positions.
    """
    n = len(candidate_positions)
    valid = np.ones(n, dtype=np.bool_)

    for i in range(n):
        x, y = candidate_positions[i]

        # Check sheet boundaries
        if x + poly_width > sheet_width + 0.1 or y + poly_height > sheet_height + 0.1:
            valid[i] = False
            continue
        if x < -0.1 or y < -0.1:
            valid[i] = False
            continue

        # Check translated bounds
        x_offset = x - poly_bounds[0]
        y_offset = y - poly_bounds[1]

        test_minx = poly_bounds[0] + x_offset
        test_miny = poly_bounds[1] + y_offset
        test_maxx = poly_bounds[2] + x_offset
        test_maxy = poly_bounds[3] + y_offset

        if (
            test_minx < -0.1
            or test_miny < -0.1
            or test_maxx > sheet_width + 0.1
            or test_maxy > sheet_height + 0.1
        ):
            valid[i] = False

    return valid


@jit(nopython=True, cache=True, fastmath=True, parallel=True)
def quick_bounds_check_batch_parallel(
    candidate_positions, poly_width, poly_height, sheet_width, sheet_height, poly_bounds
):
    """Parallel version of boundary checking (for large candidate sets).

    Returns array of booleans indicating valid positions.
    """
    n = len(candidate_positions)
    valid = np.ones(n, dtype=np.bool_)

    for i in prange(n):
        x, y = candidate_positions[i]

        # Check sheet boundaries
        if x + poly_width > sheet_width + 0.1 or y + poly_height > sheet_height + 0.1:
            valid[i] = False
            continue
        if x < -0.1 or y < -0.1:
            valid[i] = False
            continue

        # Check translated bounds
        x_offset = x - poly_bounds[0]
        y_offset = y - poly_bounds[1]

        test_minx = poly_bounds[0] + x_offset
        test_miny = poly_bounds[1] + y_offset
        test_maxx = poly_bounds[2] + x_offset
        test_maxy = poly_bounds[3] + y_offset

        if (
            test_minx < -0.1
            or test_miny < -0.1
            or test_maxx > sheet_width + 0.1
            or test_maxy > sheet_height + 0.1
        ):
            valid[i] = False

    return valid
