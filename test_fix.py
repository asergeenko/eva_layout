#!/usr/bin/env python3

import sys
sys.path.append('.')
import os
from shapely.geometry import Polygon
from carpet import PlacedCarpet
from plot import plot_layout

def test_plot_fix():
    """Test if the plot fix correctly handles PlacedCarpet with incorrect polygon positioning"""

    # Create test case that mimics the problem
    original_polygon = Polygon([(0, 0), (100, 0), (100, 100), (0, 100)])

    # Create PlacedCarpet with original polygon at origin BUT with offset info
    # This simulates the bug where polygon wasn't transformed properly
    problematic_carpet = PlacedCarpet(
        polygon=original_polygon,  # This is at origin (0,0)
        x_offset=300,  # But should be at (300, 400)
        y_offset=400,
        angle=0,
        filename="8_копия_17.dxf",  # Same as in the original problem
        color="черный"
    )

    print(f"Problematic carpet polygon bounds: {problematic_carpet.polygon.bounds}")
    print(f"Problematic carpet offsets: x={problematic_carpet.x_offset}, y={problematic_carpet.y_offset}")

    # Create another correct carpet for comparison
    correct_polygon = Polygon([(500, 600), (600, 600), (600, 700), (500, 700)])
    correct_carpet = PlacedCarpet(
        polygon=correct_polygon,
        x_offset=500,
        y_offset=600,
        angle=0,
        filename="correct.dxf",
        color="черный"
    )

    # Test the plot
    sheet_width = 1400  # 140cm
    sheet_height = 2000  # 200cm

    os.makedirs('tmp_test', exist_ok=True)

    print("\nTesting plot with fix...")
    plot_layout(
        [problematic_carpet, correct_carpet],
        sheet_width,
        sheet_height,
        "tmp_test/test_fix.png",
        "Test: Fixed plot should position carpet correctly"
    )
    print("Plot saved: tmp_test/test_fix.png")

    print("\nExpected behavior:")
    print("- Problematic carpet (8_копия_17) should be moved from origin to (300, 400)")
    print("- Correct carpet should remain at (500, 600)")
    print("- No overlapping at origin")

if __name__ == "__main__":
    test_plot_fix()