#!/usr/bin/env python3

from pathlib import Path
from dxf_utils import parse_dxf_complete
from carpet import Carpet, PlacedCarpet
from layout_optimizer import find_bottom_left_position, translate_polygon, rotate_polygon, check_collision
from shapely.geometry import Polygon

def debug_find_position():
    """Debug the find_bottom_left_position function step by step"""

    # Load first two carpets
    carpets = []
    for i in range(1, 3):  # Just first two for debugging
        dxf_path = f'dxf_samples/HYUNDAI SOLARIS 1/{i}.dxf'
        polygon_data = parse_dxf_complete(dxf_path, verbose=False)
        if polygon_data and polygon_data.get("combined_polygon"):
            carpet = Carpet(polygon_data["combined_polygon"], f"{i}.dxf", "чёрный", f"group_{i}", 1)
            carpets.append(carpet)

    if len(carpets) < 2:
        print("Not enough carpets loaded")
        return

    # Sheet dimensions
    sheet_width_mm = 1400
    sheet_height_mm = 2000

    print(f"First carpet bounds: {carpets[0].polygon.bounds}")
    print(f"Second carpet bounds: {carpets[1].polygon.bounds}")

    # Simulate placing first carpet exactly as bin_packing does
    first_carpet = carpets[0]

    # Apply 90° rotation (as shown in debug output)
    rotated_first = rotate_polygon(first_carpet.polygon, 90)

    # Use the exact position from bin_packing output: pos=(414.8, 297.5)
    first_x, first_y = 414.8, 297.5
    print(f"First carpet placement: ({first_x}, {first_y}) [from bin_packing output]")

    # Create the actual placed polygon using the exact positioning
    first_bounds = rotated_first.bounds
    first_x_offset = first_x - first_bounds[0]
    first_y_offset = first_y - first_bounds[1]
    placed_first_poly = translate_polygon(rotated_first, first_x_offset, first_y_offset)

    placed_first = PlacedCarpet(
        placed_first_poly, first_x_offset, first_y_offset, 90, "1.dxf", "чёрный", "group_1", 1, 1
    )

    print(f"First carpet final bounds: {placed_first_poly.bounds}")

    # Now try to place second carpet
    second_carpet = carpets[1]
    print(f"\nTrying to place second carpet...")
    print(f"Second carpet area: {second_carpet.polygon.area:.0f} mm²")

    # Try different rotations of second carpet
    for angle in [0, 90, 180, 270]:
        print(f"\nTesting angle {angle}°:")

        if angle == 0:
            rotated_second = second_carpet.polygon
        else:
            rotated_second = rotate_polygon(second_carpet.polygon, angle)

        second_bounds = rotated_second.bounds
        print(f"  Rotated bounds: {second_bounds}")
        print(f"  Rotated size: {second_bounds[2]-second_bounds[0]:.1f} x {second_bounds[3]-second_bounds[1]:.1f} mm")

        # Check if it fits in sheet
        if (second_bounds[2] - second_bounds[0] > sheet_width_mm or
            second_bounds[3] - second_bounds[1] > sheet_height_mm):
            print(f"  ❌ Too big for sheet")
            continue

        # Try to find position
        second_x, second_y = find_bottom_left_position(
            rotated_second, [placed_first], sheet_width_mm, sheet_height_mm
        )

        if second_x is not None and second_y is not None:
            print(f"  ✅ Found position: ({second_x:.1f}, {second_y:.1f})")

            # Verify no collision
            second_x_offset = second_x - second_bounds[0]
            second_y_offset = second_y - second_bounds[1]
            placed_second_poly = translate_polygon(rotated_second, second_x_offset, second_y_offset)

            collision = check_collision(placed_first_poly, placed_second_poly, min_gap=2.0)
            print(f"  Collision check: {collision}")

            if not collision:
                placed_second_bounds = placed_second_poly.bounds
                print(f"  Final bounds: {placed_second_bounds}")

                # Check combined bounds fit in sheet
                combined_max_x = max(placed_first_poly.bounds[2], placed_second_bounds[2])
                combined_max_y = max(placed_first_poly.bounds[3], placed_second_bounds[3])

                if combined_max_x <= sheet_width_mm and combined_max_y <= sheet_height_mm:
                    print(f"  ✅ Both fit together! Combined bounds: (0, 0, {combined_max_x:.1f}, {combined_max_y:.1f})")

                    # Calculate utilization
                    first_area = placed_first_poly.area
                    second_area = placed_second_poly.area
                    total_area = first_area + second_area
                    sheet_area = sheet_width_mm * sheet_height_mm
                    utilization = (total_area / sheet_area) * 100
                    print(f"  Combined utilization: {utilization:.1f}%")

                    print(f"\n🎯 THIS SHOULD WORK! But bin_packing is not finding it.")
                    return  # Found a working solution
                else:
                    print(f"  ❌ Combined bounds exceed sheet")
        else:
            print(f"  ❌ No position found by find_bottom_left_position")

    print(f"\n❌ No valid position found for second carpet with any rotation")

if __name__ == "__main__":
    debug_find_position()