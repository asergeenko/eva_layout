"""Benchmark script to measure optimization improvements."""

import time
import numpy as np
from shapely.geometry import Polygon, box

# Import original and optimized functions
from layout_optimizer import (
    find_bottom_left_position,
    find_bottom_left_position_with_obstacles,
    check_collision_with_strtree,
)
from carpet import PlacedCarpet


def create_test_polygon(width=50, height=50):
    """Create a simple rectangular test polygon."""
    return box(0, 0, width, height)


def create_test_obstacles(n_obstacles=10, sheet_width=1000, sheet_height=1000):
    """Create random obstacle polygons."""
    obstacles = []
    placed = []
    np.random.seed(42)

    for i in range(n_obstacles):
        w = np.random.uniform(30, 100)
        h = np.random.uniform(30, 100)
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

    return obstacles, placed


def benchmark_collision_check(n_tests=100):
    """Benchmark collision checking."""
    print("=" * 60)
    print("BENCHMARK: Collision Checking")
    print("=" * 60)

    # Create test data
    test_poly = create_test_polygon(50, 50)
    obstacles, _ = create_test_obstacles(n_obstacles=50)

    # Warmup (for Numba JIT compilation)
    for _ in range(10):
        check_collision_with_strtree(test_poly, obstacles)

    # Benchmark with cache
    start = time.time()
    for _ in range(n_tests):
        check_collision_with_strtree(test_poly, obstacles, use_cache=True)
    time_with_cache = time.time() - start

    # Benchmark without cache
    start = time.time()
    for _ in range(n_tests):
        check_collision_with_strtree(test_poly, obstacles, use_cache=False)
    time_without_cache = time.time() - start

    print(f"Tests: {n_tests}")
    print(f"Obstacles: {len(obstacles)}")
    print(f"Time WITH cache:    {time_with_cache:.4f}s ({time_with_cache/n_tests*1000:.2f}ms per test)")
    print(f"Time WITHOUT cache: {time_without_cache:.4f}s ({time_without_cache/n_tests*1000:.2f}ms per test)")
    print(f"Speedup: {time_without_cache/time_with_cache:.2f}x")
    print()


def benchmark_find_position(n_tests=20):
    """Benchmark position finding."""
    print("=" * 60)
    print("BENCHMARK: find_bottom_left_position_with_obstacles")
    print("=" * 60)

    sheet_width = 1000
    sheet_height = 1000

    test_poly = create_test_polygon(60, 60)

    # Test with different obstacle counts
    for n_obstacles in [10, 30, 50]:
        obstacles, _ = create_test_obstacles(n_obstacles, sheet_width, sheet_height)

        # Warmup
        for _ in range(3):
            find_bottom_left_position_with_obstacles(
                test_poly, obstacles, sheet_width, sheet_height
            )

        # Benchmark
        start = time.time()
        results = []
        for _ in range(n_tests):
            result = find_bottom_left_position_with_obstacles(
                test_poly, obstacles, sheet_width, sheet_height
            )
            results.append(result)
        elapsed = time.time() - start

        successful = sum(1 for r in results if r[0] is not None)

        print(f"Obstacles: {n_obstacles}")
        print(f"  Time: {elapsed:.4f}s ({elapsed/n_tests*1000:.2f}ms per test)")
        print(f"  Success rate: {successful}/{n_tests}")
        print()


def benchmark_find_position_simple(n_tests=20):
    """Benchmark simple position finding."""
    print("=" * 60)
    print("BENCHMARK: find_bottom_left_position")
    print("=" * 60)

    sheet_width = 1000
    sheet_height = 1000

    test_poly = create_test_polygon(60, 60)

    # Test with different obstacle counts
    for n_obstacles in [10, 30, 50]:
        _, placed = create_test_obstacles(n_obstacles, sheet_width, sheet_height)

        # Warmup
        for _ in range(3):
            find_bottom_left_position(
                test_poly, placed, sheet_width, sheet_height
            )

        # Benchmark
        start = time.time()
        results = []
        for _ in range(n_tests):
            result = find_bottom_left_position(
                test_poly, placed, sheet_width, sheet_height
            )
            results.append(result)
        elapsed = time.time() - start

        successful = sum(1 for r in results if r[0] is not None)

        print(f"Obstacles: {n_obstacles}")
        print(f"  Time: {elapsed:.4f}s ({elapsed/n_tests*1000:.2f}ms per test)")
        print(f"  Success rate: {successful}/{n_tests}")
        print()


if __name__ == "__main__":
    print("\n🚀 OPTIMIZATION BENCHMARK\n")

    # Run benchmarks
    benchmark_collision_check(n_tests=100)
    benchmark_find_position(n_tests=20)
    benchmark_find_position_simple(n_tests=20)

    print("=" * 60)
    print("✅ Benchmark complete!")
    print("=" * 60)