"""Detailed profiling of the layout functions."""

import time
import numpy as np
from shapely.geometry import box

from layout_optimizer import (
    find_bottom_left_position,
    find_bottom_left_position_with_obstacles,
)
from carpet import PlacedCarpet


def create_real_scenario(n_obstacles=50):
    """Create realistic test scenario."""
    sheet_width = 3000.0  # 300cm
    sheet_height = 1500.0  # 150cm

    np.random.seed(42)
    placed = []
    obstacles = []

    for i in range(n_obstacles):
        w = np.random.uniform(100, 300)
        h = np.random.uniform(100, 300)
        x = np.random.uniform(0, sheet_width - w)
        y = np.random.uniform(0, sheet_height - h)

        poly = box(x, y, x + w, y + h)
        obstacles.append(poly)
        placed.append(PlacedCarpet(
            polygon=poly,
            carpet_id=i,
            priority=0,
            x_offset=x,
            y_offset=y,
            angle=0
        ))

    return obstacles, placed, sheet_width, sheet_height


def profile_with_obstacles():
    """Profile find_bottom_left_position_with_obstacles."""
    print("=" * 70)
    print("PROFILING: find_bottom_left_position_with_obstacles")
    print("=" * 70)

    test_poly = box(0, 0, 150, 150)

    for n_obs in [10, 30, 50, 100]:
        obstacles, _, sheet_width, sheet_height = create_real_scenario(n_obs)

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
            times.append(elapsed * 1000)  # Convert to ms

        avg_time = np.mean(times)
        std_time = np.std(times)

        print(f"\nObstacles: {n_obs}")
        print(f"  Avg time: {avg_time:.3f}ms ± {std_time:.3f}ms")
        print(f"  Min/Max: {min(times):.3f}ms / {max(times):.3f}ms")
        print(f"  Result: {result}")


def profile_simple():
    """Profile find_bottom_left_position."""
    print("\n" + "=" * 70)
    print("PROFILING: find_bottom_left_position")
    print("=" * 70)

    test_poly = box(0, 0, 150, 150)

    for n_obs in [10, 30, 50, 100]:
        _, placed, sheet_width, sheet_height = create_real_scenario(n_obs)

        # Warmup
        for _ in range(3):
            find_bottom_left_position(
                test_poly, placed, sheet_width, sheet_height
            )

        # Measure
        times = []
        for _ in range(20):
            start = time.perf_counter()
            result = find_bottom_left_position(
                test_poly, placed, sheet_width, sheet_height
            )
            elapsed = time.perf_counter() - start
            times.append(elapsed * 1000)  # Convert to ms

        avg_time = np.mean(times)
        std_time = np.std(times)

        print(f"\nObstacles: {n_obs}")
        print(f"  Avg time: {avg_time:.3f}ms ± {std_time:.3f}ms")
        print(f"  Min/Max: {min(times):.3f}ms / {max(times):.3f}ms")
        print(f"  Result: {result}")


if __name__ == "__main__":
    print("\n🔍 DETAILED PROFILING\n")
    profile_with_obstacles()
    profile_simple()
    print("\n" + "=" * 70)
    print("✅ Profiling complete")
    print("=" * 70)