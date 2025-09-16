#!/usr/bin/env python3

import sys

sys.path.append(".")

from shapely.geometry import Polygon
from carpet import PlacedCarpet
from layout_optimizer import apply_placement_transform
from plot import plot_layout
import os


def test_plot_issue():
    """Test if the plot function correctly handles PlacedCarpet with transform info"""

    # Create test carpet at origin
    original_polygon = Polygon([(0, 0), (100, 0), (100, 100), (0, 100)])
    print(f"Original polygon bounds: {original_polygon.bounds}")

    # Test Case 1: PlacedCarpet with original polygon + transform info (WRONG way)
    placed_wrong = PlacedCarpet(
        polygon=original_polygon,  # Original polygon at origin
        x_offset=200,
        y_offset=300,
        angle=90,
        filename="test_wrong.dxf",
        color="черный",
    )

    # Test Case 2: PlacedCarpet with already transformed polygon (CORRECT way)
    transformed_polygon = apply_placement_transform(original_polygon, 200, 300, 90)
    placed_correct = PlacedCarpet(
        polygon=transformed_polygon,  # Already transformed polygon
        x_offset=200,
        y_offset=300,
        angle=90,
        filename="test_correct.dxf",
        color="черный",
    )

    print(f"Wrong PlacedCarpet polygon bounds: {placed_wrong.polygon.bounds}")
    print(f"Correct PlacedCarpet polygon bounds: {placed_correct.polygon.bounds}")

    # Test how plot_layout handles both cases
    sheet_width = 600
    sheet_height = 700

    # Test wrong case
    os.makedirs("tmp_test", exist_ok=True)

    print("\n=== Testing WRONG PlacedCarpet (original polygon) ===")
    plot_layout(
        [placed_wrong],
        sheet_width,
        sheet_height,
        "tmp_test/plot_test_wrong.png",
        "Wrong: Original polygon + offset info",
    )
    print("Plot saved: tmp_test/plot_test_wrong.png")

    print("\n=== Testing CORRECT PlacedCarpet (transformed polygon) ===")
    plot_layout(
        [placed_correct],
        sheet_width,
        sheet_height,
        "tmp_test/plot_test_correct.png",
        "Correct: Already transformed polygon",
    )
    print("Plot saved: tmp_test/plot_test_correct.png")

    # Expected behavior:
    # If plot_layout only uses polygon and ignores x_offset/y_offset/angle,
    # then wrong case will show polygon at origin (0,0)
    # and correct case will show polygon at proper position (200,300)

    print("\n=== Analysis ===")
    if placed_wrong.polygon.bounds == original_polygon.bounds:
        print("❌ WRONG case: polygon is at origin, should be transformed!")
        print("   This suggests that either:")
        print("   1. PlacedCarpet was created incorrectly with original polygon")
        print("   2. plot_layout should apply transform but doesn't")

    if placed_correct.polygon.bounds != original_polygon.bounds:
        print("✅ CORRECT case: polygon is properly transformed")


def test_current_plot_behavior():
    """Test how plot_layout currently behaves"""

    # Look at plot.py to see what it does with x_offset, y_offset, angle
    print("\n=== Checking plot.py behavior ===")

    # From reading the code, plot.py does:
    # for placed_tuple in placed_polygons:
    #     polygon = placed_tuple.polygon  # Uses polygon directly
    #     angle = placed_tuple.angle      # Only used for label
    #     x, y = polygon.exterior.xy      # Uses polygon coordinates
    #     ax.fill(x, y, ...)              # Plots polygon as-is

    print("Current plot.py behavior:")
    print("- Uses placed_tuple.polygon directly for plotting")
    print("- Does NOT apply x_offset, y_offset transformations")
    print("- Only uses 'angle' in the label text")
    print("- This means PlacedCarpet.polygon MUST be already transformed")


if __name__ == "__main__":
    test_plot_issue()
    test_current_plot_behavior()
