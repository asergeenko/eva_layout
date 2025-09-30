"""Test original candidate generation count."""

import numpy as np
from shapely.geometry import box


def test_original_candidate_count():
    """Test how many candidates the original algorithm generates."""
    sheet_width = 3000.0
    sheet_height = 1500.0
    poly_width = 150.0
    poly_height = 150.0

    np.random.seed(42)
    obstacles = []

    for i in range(30):
        w = np.random.uniform(100, 300)
        h = np.random.uniform(100, 300)
        x = np.random.uniform(0, sheet_width - w)
        y = np.random.uniform(0, sheet_height - h)
        obstacles.append(box(x, y, x + w, y + h))

    # ORIGINAL algorithm
    polygon_size = poly_width * poly_height
    is_small = polygon_size < 10000
    grid_step = 2.0 if is_small else 15.0

    candidate_positions = []

    # Bottom edge positions
    for x in np.arange(0, sheet_width - poly_width + 1, grid_step):
        candidate_positions.append((x, 0))

    # Left edge positions
    for y in np.arange(0, sheet_height - poly_height + 1, grid_step):
        candidate_positions.append((0, y))

    # Positions based on existing obstacles
    for obstacle in obstacles:
        obstacle_bounds = obstacle.bounds

        # Right of obstacle
        x = obstacle_bounds[2] + 3
        if x + poly_width <= sheet_width:
            candidate_positions.append((x, obstacle_bounds[1]))
            candidate_positions.append((x, 0))

        # Above obstacle
        y = obstacle_bounds[3] + 3
        if y + poly_height <= sheet_height:
            candidate_positions.append((obstacle_bounds[0], y))
            candidate_positions.append((0, y))

    # Remove duplicates
    candidate_positions_before = len(candidate_positions)
    candidate_positions = list(set(candidate_positions))
    candidate_positions_after = len(candidate_positions)

    print(f"Grid step: {grid_step}")
    print(f"Is small polygon: {is_small}")
    print(f"Candidates before dedup: {candidate_positions_before}")
    print(f"Candidates after dedup: {candidate_positions_after}")


if __name__ == "__main__":
    test_original_candidate_count()
