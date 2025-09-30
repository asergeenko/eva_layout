"""Test candidate generation count."""

import numpy as np
from shapely.geometry import box

from fast_geometry import generate_candidate_positions, extract_bounds_array


def test_candidate_count():
    """Test how many candidates are generated."""
    sheet_width = 3000.0
    sheet_height = 1500.0

    np.random.seed(42)
    obstacles = []

    for i in range(30):
        w = np.random.uniform(100, 300)
        h = np.random.uniform(100, 300)
        x = np.random.uniform(0, sheet_width - w)
        y = np.random.uniform(0, sheet_height - h)
        obstacles.append(box(x, y, x + w, y + h))

    obstacles_bounds = extract_bounds_array(obstacles)
    poly_width = 150.0
    poly_height = 150.0
    polygon_size = poly_width * poly_height
    is_small = polygon_size < 10000
    grid_step = 2.0 if is_small else 15.0

    candidates = generate_candidate_positions(
        poly_width, poly_height, sheet_width, sheet_height,
        obstacles_bounds, step_size=grid_step, max_candidates=2000
    )

    print(f"Grid step: {grid_step}")
    print(f"Number of candidates generated: {len(candidates)}")
    print(f"Is small polygon: {is_small}")


if __name__ == "__main__":
    test_candidate_count()
