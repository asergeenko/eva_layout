#!/usr/bin/env python3

import sys
sys.path.append('.')
from shapely.geometry import Polygon
from carpet import PlacedCarpet
from layout_optimizer import apply_placement_transform

def test_fix_logic():
    """Test the fix logic without plotting"""

    # Create test case that mimics the problem
    original_polygon = Polygon([(0, 0), (100, 0), (100, 100), (0, 100)])

    # Create PlacedCarpet with original polygon at origin BUT with offset info
    problematic_carpet = PlacedCarpet(
        polygon=original_polygon,  # This is at origin (0,0)
        x_offset=300,  # But should be at (300, 400)
        y_offset=400,
        angle=0,
        filename="8_копия_17.dxf",
        color="черный"
    )

    print(f"Original carpet polygon bounds: {problematic_carpet.polygon.bounds}")
    print(f"Carpet offsets: x={problematic_carpet.x_offset}, y={problematic_carpet.y_offset}")

    # Apply the same fix logic as in plot.py
    polygon = problematic_carpet.polygon
    polygon_bounds = polygon.bounds
    has_offset = hasattr(problematic_carpet, 'x_offset') and hasattr(problematic_carpet, 'y_offset')

    if has_offset:
        x_offset = getattr(problematic_carpet, 'x_offset', 0)
        y_offset = getattr(problematic_carpet, 'y_offset', 0)

        # Check if polygon seems to be at origin but should be elsewhere
        is_near_origin = (abs(polygon_bounds[0]) < 10 and abs(polygon_bounds[1]) < 10)
        has_nonzero_offset = (abs(x_offset) > 10 or abs(y_offset) > 10)

        print(f"is_near_origin: {is_near_origin}")
        print(f"has_nonzero_offset: {has_nonzero_offset}")

        if is_near_origin and has_nonzero_offset:
            print("Applying transformation fix...")
            fixed_polygon = apply_placement_transform(polygon, x_offset, y_offset, problematic_carpet.angle)
            print(f"Fixed polygon bounds: {fixed_polygon.bounds}")

            # Check if fix worked correctly
            expected_bounds = (300, 400, 400, 500)  # Should be at (300, 400) with size 100x100
            actual_bounds = fixed_polygon.bounds

            if all(abs(actual_bounds[i] - expected_bounds[i]) < 1 for i in range(4)):
                print("✅ Fix worked correctly!")
            else:
                print("❌ Fix didn't work as expected")
                print(f"Expected: {expected_bounds}")
                print(f"Actual: {actual_bounds}")
        else:
            print("No fix needed")
    else:
        print("No offset information available")

if __name__ == "__main__":
    test_fix_logic()