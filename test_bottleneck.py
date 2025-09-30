"""Test to identify the bottleneck in find_bottom_left_position_with_obstacles."""

import time
import numpy as np
from shapely.geometry import box

from layout_optimizer import (
    find_bottom_left_position_with_obstacles,
    find_ultra_tight_position,
)


def create_scenario(n_obstacles=30):
    """Create test scenario."""
    sheet_width = 3000.0
    sheet_height = 1500.0

    np.random.seed(42)
    obstacles = []

    for i in range(n_obstacles):
        w = np.random.uniform(100, 300)
        h = np.random.uniform(100, 300)
        x = np.random.uniform(0, sheet_width - w)
        y = np.random.uniform(0, sheet_height - h)
        obstacles.append(box(x, y, x + w, y + h))

    return obstacles, sheet_width, sheet_height


def test_ultra_tight_only():
    """Test find_ultra_tight_position performance."""
    print("=" * 70)
    print("Testing find_ultra_tight_position ONLY")
    print("=" * 70)

    test_poly = box(0, 0, 150, 150)
    obstacles, sheet_width, sheet_height = create_scenario(30)

    # Warmup
    for _ in range(3):
        find_ultra_tight_position(test_poly, obstacles, sheet_width, sheet_height)

    # Measure
    times = []
    for _ in range(20):
        start = time.perf_counter()
        result = find_ultra_tight_position(
            test_poly, obstacles, sheet_width, sheet_height
        )
        elapsed = time.perf_counter() - start
        times.append(elapsed * 1000)

    avg_time = np.mean(times)
    print(f"  Avg time: {avg_time:.3f}ms")
    print(f"  Result: {result}")


def test_full_function():
    """Test find_bottom_left_position_with_obstacles (includes ultra_tight)."""
    print("\n" + "=" * 70)
    print("Testing find_bottom_left_position_with_obstacles FULL")
    print("=" * 70)

    test_poly = box(0, 0, 150, 150)
    obstacles, sheet_width, sheet_height = create_scenario(30)

    # Warmup
    for _ in range(3):
        find_bottom_left_position_with_obstacles(
            test_poly, obstacles, sheet_width, sheet_height
        )

    # Measure
    times = []
    for _ in range(20):
        start = time.perf_counter()
        result = find_bottom_left_position_with_obstacles(
            test_poly, obstacles, sheet_width, sheet_height
        )
        elapsed = time.perf_counter() - start
        times.append(elapsed * 1000)

    avg_time = np.mean(times)
    print(f"  Avg time: {avg_time:.3f}ms")
    print(f"  Result: {result}")


if __name__ == "__main__":
    test_ultra_tight_only()
    test_full_function()
    print("\n" + "=" * 70)
    print("✅ Test complete")
    print("=" * 70)
