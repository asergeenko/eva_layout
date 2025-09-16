#!/usr/bin/env python3

import sys
from shapely.geometry import Polygon
from layout_optimizer import find_contour_following_position, check_collision


def test_placement_fix():
    """Test that the placement algorithm correctly handles existing obstacles."""

    # Create a simple sheet 1000x1000mm
    sheet_width = 1000
    sheet_height = 1000

    # Create obstacles (simulating already placed carpets)
    obstacle1 = Polygon([(0, 0), (200, 0), (200, 100), (0, 100)])  # Rectangle at origin
    obstacle2 = Polygon(
        [(300, 0), (500, 0), (500, 150), (300, 150)]
    )  # Another rectangle
    obstacles = [obstacle1, obstacle2]

    # Create a new polygon to place
    new_polygon = Polygon([(0, 0), (100, 0), (100, 50), (0, 50)])  # Small rectangle

    print(f"Sheet size: {sheet_width}x{sheet_height} mm")
    print(f"Number of obstacles: {len(obstacles)}")
    print(f"New polygon bounds: {new_polygon.bounds}")

    # Test the placement function
    result_x, result_y = find_contour_following_position(
        new_polygon, obstacles, sheet_width, sheet_height
    )

    if result_x is None or result_y is None:
        print("❌ No position found")
        return False

    print(f"Found position: ({result_x}, {result_y})")

    # Verify this position doesn't overlap with obstacles
    from layout_optimizer import translate_polygon

    x_offset = result_x - new_polygon.bounds[0]
    y_offset = result_y - new_polygon.bounds[1]
    translated_polygon = translate_polygon(new_polygon, x_offset, y_offset)

    print(f"Translated polygon bounds: {translated_polygon.bounds}")

    # Check for collisions
    has_collision = False
    for i, obstacle in enumerate(obstacles):
        if check_collision(translated_polygon, obstacle, min_gap=0.1):
            print(f"❌ Collision detected with obstacle {i+1}")
            print(f"   Obstacle bounds: {obstacle.bounds}")
            print(f"   Translated polygon bounds: {translated_polygon.bounds}")
            has_collision = True

    if not has_collision:
        print("✅ No collisions detected - placement is valid!")
        return True

    return False


if __name__ == "__main__":
    success = test_placement_fix()
    if success:
        print("\n✅ Test PASSED: Placement algorithm works correctly")
        sys.exit(0)
    else:
        print("\n❌ Test FAILED: Placement algorithm has issues")
        sys.exit(1)
