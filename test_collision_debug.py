#!/usr/bin/env python3

from shapely.geometry import Polygon
from layout_optimizer import check_collision, translate_polygon

def test_collision_at_origin():
    """Test collision detection when both polygons are at origin."""

    # Create two overlapping rectangles at origin
    rect1 = Polygon([(0, 0), (200, 0), (200, 100), (0, 100)])  # First rectangle
    rect2 = Polygon([(0, 0), (100, 0), (100, 50), (0, 50)])   # Second smaller rectangle, overlapping

    print(f"Rectangle 1 bounds: {rect1.bounds}")
    print(f"Rectangle 2 bounds: {rect2.bounds}")

    # Test collision
    collision = check_collision(rect1, rect2, min_gap=0.1)
    print(f"Collision detected: {collision}")

    if not collision:
        print("❌ ERROR: No collision detected when rectangles clearly overlap!")
        return False

    # Test with gap
    rect3 = Polygon([(210, 0), (310, 0), (310, 50), (210, 50)])  # Rectangle to the right
    print(f"Rectangle 3 bounds: {rect3.bounds}")

    collision2 = check_collision(rect1, rect3, min_gap=0.1)
    print(f"Collision between rect1 and rect3: {collision2}")

    if collision2:
        print("❌ ERROR: Collision detected when rectangles are separate!")
        return False

    # Test exact touching
    rect4 = Polygon([(200, 0), (300, 0), (300, 50), (200, 50)])  # Exactly touching
    collision3 = check_collision(rect1, rect4, min_gap=0.1)
    print(f"Collision between touching rectangles (rect1 and rect4): {collision3}")

    if not collision3:
        print("❌ ERROR: Should detect collision with min_gap when rectangles touch!")
        return False

    print("✅ All collision tests passed")
    return True

def test_placement_at_origin_with_obstacles():
    """Test placement algorithm when obstacles are at origin."""
    from layout_optimizer import find_contour_following_position

    # Create obstacle at origin
    obstacle = Polygon([(0, 0), (200, 0), (200, 100), (0, 100)])
    obstacles = [obstacle]

    # Try to place new carpet
    new_carpet = Polygon([(0, 0), (100, 0), (100, 50), (0, 50)])

    print(f"\nObstacle bounds: {obstacle.bounds}")
    print(f"New carpet bounds: {new_carpet.bounds}")

    sheet_width = 1000
    sheet_height = 1000

    result_x, result_y = find_contour_following_position(
        new_carpet, obstacles, sheet_width, sheet_height
    )

    print(f"Found position: ({result_x}, {result_y})")

    if result_x is None:
        print("✅ Good: No position found, avoiding overlap")
        return True

    # Check if found position would cause collision
    x_offset = result_x - new_carpet.bounds[0]
    y_offset = result_y - new_carpet.bounds[1]
    translated = translate_polygon(new_carpet, x_offset, y_offset)

    print(f"Translated carpet bounds: {translated.bounds}")

    collision = check_collision(translated, obstacle, min_gap=0.1)
    if collision:
        print(f"❌ ERROR: Found position causes collision!")
        return False

    print(f"✅ Found valid position without collision")
    return True

if __name__ == "__main__":
    print("Testing collision detection...")
    test1_passed = test_collision_at_origin()

    print("\nTesting placement with obstacles...")
    test2_passed = test_placement_at_origin_with_obstacles()

    if test1_passed and test2_passed:
        print("\n✅ All tests passed")
    else:
        print("\n❌ Some tests failed")