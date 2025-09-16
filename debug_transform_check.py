#!/usr/bin/env python3

import sys

sys.path.append(".")

from layout_optimizer import apply_placement_transform
from shapely.geometry import Polygon
import matplotlib.pyplot as plt


def test_transform():
    """Test if apply_placement_transform works correctly"""

    # Create simple test polygon (square)
    test_polygon = Polygon([(0, 0), (100, 0), (100, 100), (0, 100)])
    print(f"Original polygon bounds: {test_polygon.bounds}")

    # Test transformation
    x_offset = 200
    y_offset = 300
    angle = 90

    transformed = apply_placement_transform(test_polygon, x_offset, y_offset, angle)
    print(f"Transformed polygon bounds: {transformed.bounds}")

    # Expected result depends on the semantics of x_offset, y_offset
    # If x_offset, y_offset mean "move polygon so its origin (0,0) is at this position":
    # 1. Move to origin: polygon becomes (0, 0) to (100, 100)
    # 2. Rotate 90°: becomes (-100, 0) to (0, 100)
    # 3. Translate by (200, 300): becomes (100, 300) to (200, 400)

    # If x_offset, y_offset mean "move polygon so its bottom-left corner is at this position":
    # 1. Move to origin: polygon becomes (0, 0) to (100, 100)
    # 2. Rotate 90°: becomes (-100, 0) to (0, 100)
    # 3. To put bottom-left at (200, 300), need to add (300, 300): becomes (200, 300) to (300, 400)

    # Let's test both interpretations
    interpretation1_bounds = (100, 300, 200, 400)  # offset = target position of origin
    interpretation2_bounds = (
        200,
        300,
        300,
        400,
    )  # offset = target position of bottom-left
    print(f"Interpretation 1 (origin): {interpretation1_bounds}")
    print(f"Interpretation 2 (bottom-left): {interpretation2_bounds}")

    # Create visualization
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 6))

    # Original polygon
    x1, y1 = test_polygon.exterior.xy
    ax1.plot(x1, y1, "b-", linewidth=2, label="Original")
    ax1.fill(x1, y1, alpha=0.3, color="blue")
    ax1.set_title("Original Polygon")
    ax1.grid(True)
    ax1.axis("equal")
    ax1.legend()

    # Transformed polygon
    x2, y2 = transformed.exterior.xy
    ax2.plot(x2, y2, "r-", linewidth=2, label="Transformed")
    ax2.fill(x2, y2, alpha=0.3, color="red")
    ax2.set_title(f"Transformed (offset={x_offset},{y_offset}, angle={angle}°)")
    ax2.grid(True)
    ax2.axis("equal")
    ax2.legend()

    plt.tight_layout()
    plt.savefig("tmp_test/transform_test.png", dpi=150, bbox_inches="tight")
    print("Visualization saved to tmp_test/transform_test.png")

    # Check if transformation is correct
    actual_bounds = transformed.bounds
    tolerance = 1e-10

    match1 = all(
        abs(actual_bounds[i] - interpretation1_bounds[i]) < tolerance for i in range(4)
    )
    match2 = all(
        abs(actual_bounds[i] - interpretation2_bounds[i]) < tolerance for i in range(4)
    )

    if match1:
        print(
            "✅ Transform function works correctly! (Interpretation 1: offset = origin position)"
        )
    elif match2:
        print(
            "✅ Transform function works correctly! (Interpretation 2: offset = bottom-left position)"
        )
    else:
        print("❌ Transform function has issues!")
        print(f"  Actual:   {actual_bounds}")
        print(f"  Expected (origin): {interpretation1_bounds}")
        print(f"  Expected (bottom-left): {interpretation2_bounds}")


def test_placed_carpet_creation():
    """Test creation of PlacedCarpet to see if polygon is properly transformed"""
    from carpet import PlacedCarpet

    # Create simple carpet
    test_polygon = Polygon([(0, 0), (100, 0), (100, 100), (0, 100)])

    # Create placed carpet
    x_offset = 200
    y_offset = 300
    angle = 90

    # Method 1: Direct creation (this is how it might be done incorrectly)
    placed_direct = PlacedCarpet(
        polygon=test_polygon,  # Original polygon, not transformed!
        x_offset=x_offset,
        y_offset=y_offset,
        angle=angle,
        filename="test.dxf",
    )

    # Method 2: Properly transformed polygon
    transformed_polygon = apply_placement_transform(
        test_polygon, x_offset, y_offset, angle
    )
    placed_correct = PlacedCarpet(
        polygon=transformed_polygon,  # Transformed polygon
        x_offset=x_offset,
        y_offset=y_offset,
        angle=angle,
        filename="test.dxf",
    )

    print("\nPlacedCarpet test:")
    print(f"Original polygon bounds: {test_polygon.bounds}")
    print(f"Direct placed polygon bounds: {placed_direct.polygon.bounds}")
    print(f"Correct placed polygon bounds: {placed_correct.polygon.bounds}")

    if placed_direct.polygon.bounds == test_polygon.bounds:
        print(
            "❌ Problem found! PlacedCarpet.polygon contains original untransformed polygon"
        )
    else:
        print("✅ PlacedCarpet.polygon is properly transformed")


if __name__ == "__main__":
    import os

    os.makedirs("tmp_test", exist_ok=True)

    test_transform()
    test_placed_carpet_creation()
