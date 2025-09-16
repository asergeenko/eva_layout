#!/usr/bin/env python3

from dxf_utils import parse_dxf_complete
from carpet import Carpet
from layout_optimizer import (
    check_collision,
    find_bottom_left_position,
    translate_polygon,
    rotate_polygon,
)


def test_collision_detection():
    """Test collision detection between first carpet and remaining carpets"""

    # Load all carpets
    carpets = []
    for i in range(1, 6):
        dxf_path = f"dxf_samples/HYUNDAI SOLARIS 1/{i}.dxf"
        polygon_data = parse_dxf_complete(dxf_path, verbose=False)
        if polygon_data and polygon_data.get("combined_polygon"):
            carpet = Carpet(
                polygon_data["combined_polygon"], f"{i}.dxf", "чёрный", f"group_{i}", 1
            )
            carpets.append(carpet)

    if len(carpets) < 2:
        print("Not enough carpets loaded")
        return

    # Simulate the exact placement from debug output
    # First carpet (1.dxf): pos=(414.8, 297.5), angle=90°
    first_carpet = carpets[0]  # 1.dxf

    print(f"First carpet original bounds: {first_carpet.polygon.bounds}")

    # Apply rotation and translation as in the actual placement
    rotated = rotate_polygon(first_carpet.polygon, 90)  # 90° rotation
    print(f"Rotated bounds: {rotated.bounds}")

    # Calculate the translation needed to place at (414.8, 297.5)
    rotated_bounds = rotated.bounds
    x_offset = 414.8 - rotated_bounds[0]
    y_offset = 297.5 - rotated_bounds[1]

    placed_polygon = translate_polygon(rotated, x_offset, y_offset)
    final_bounds = placed_polygon.bounds

    print(f"Placed polygon bounds: {final_bounds}")
    print(f"Translation: x_offset={x_offset:.1f}, y_offset={y_offset:.1f}")

    # Sheet dimensions
    sheet_width_mm = 1400
    sheet_height_mm = 2000

    print(f"\nSheet bounds: (0, 0, {sheet_width_mm}, {sheet_height_mm})")

    # Check if the first carpet is correctly within sheet bounds
    if (
        final_bounds[0] < 0
        or final_bounds[1] < 0
        or final_bounds[2] > sheet_width_mm
        or final_bounds[3] > sheet_height_mm
    ):
        print("❌ FIRST CARPET IS OUTSIDE SHEET BOUNDS!")
    else:
        print("✅ First carpet is within sheet bounds")

    # Calculate actual space occupied and remaining
    occupied_width = final_bounds[2] - final_bounds[0]
    occupied_height = final_bounds[3] - final_bounds[1]
    remaining_width = sheet_width_mm - occupied_width
    remaining_height = sheet_height_mm - occupied_height

    print(f"\nFirst carpet occupies: {occupied_width:.1f} x {occupied_height:.1f} mm")
    print(f"Remaining space: {remaining_width:.1f} x {remaining_height:.1f} mm")

    # Create a placed carpet for collision testing
    from carpet import PlacedCarpet

    placed_first = PlacedCarpet(
        placed_polygon, x_offset, y_offset, 90, "1.dxf", "чёрный", "group_1", 1, 1
    )

    # Test collision detection with each remaining carpet
    print("\n" + "=" * 60)
    print("COLLISION TESTING")
    print("=" * 60)

    for i, other_carpet in enumerate(carpets[1:], 2):
        print(f"\nTesting {other_carpet.filename}:")

        # Test direct collision (should be False since they're in different areas)
        direct_collision = check_collision(
            placed_polygon, other_carpet.polygon, min_gap=2.0
        )
        print(f"  Direct collision with raw polygon: {direct_collision}")

        # Test if we can find a placement position for the other carpet
        best_x, best_y = find_bottom_left_position(
            other_carpet.polygon, [placed_first], sheet_width_mm, sheet_height_mm
        )

        if best_x is not None and best_y is not None:
            print(f"  ✅ Can be placed at ({best_x:.1f}, {best_y:.1f})")

            # Create the placed polygon and verify no collision
            other_bounds = other_carpet.polygon.bounds
            other_x_offset = best_x - other_bounds[0]
            other_y_offset = best_y - other_bounds[1]
            other_placed = translate_polygon(
                other_carpet.polygon, other_x_offset, other_y_offset
            )

            # Final collision check
            final_collision = check_collision(placed_polygon, other_placed, min_gap=2.0)
            print(f"  Final collision check: {final_collision}")

            if not final_collision:
                other_final_bounds = other_placed.bounds
                print(f"  Other carpet would be placed at bounds: {other_final_bounds}")

                # Check if both fit in sheet
                max_x = max(final_bounds[2], other_final_bounds[2])
                max_y = max(final_bounds[3], other_final_bounds[3])

                if max_x <= sheet_width_mm and max_y <= sheet_height_mm:
                    print("  ✅ Both carpets would fit together on sheet!")
                    print(
                        f"  Combined bounds would be: (0, 0, {max_x:.1f}, {max_y:.1f})"
                    )
                    utilization = (
                        (
                            (final_bounds[2] - final_bounds[0])
                            * (final_bounds[3] - final_bounds[1])
                            + (other_final_bounds[2] - other_final_bounds[0])
                            * (other_final_bounds[3] - other_final_bounds[1])
                        )
                        / (sheet_width_mm * sheet_height_mm)
                        * 100
                    )
                    print(f"  Combined utilization would be: {utilization:.1f}%")
                else:
                    print(
                        f"  ❌ Combined bounds would exceed sheet: max_x={max_x:.1f}, max_y={max_y:.1f}"
                    )
            else:
                print("  ❌ Final collision detected even though position was found")
        else:
            print("  ❌ No position found by find_bottom_left_position")

            # Let's try manual positioning to see what's happening
            print("  Trying manual positioning...")

            # Try simple positions
            other_bounds = other_carpet.polygon.bounds
            other_width = other_bounds[2] - other_bounds[0]
            other_height = other_bounds[3] - other_bounds[1]

            # Try position to the left of first carpet
            try_x = 50.0  # 50mm from left edge
            try_y = 50.0  # 50mm from bottom edge

            if (
                try_x + other_width < final_bounds[0]
                and try_y + other_height < sheet_height_mm
            ):
                try_x_offset = try_x - other_bounds[0]
                try_y_offset = try_y - other_bounds[1]
                try_placed = translate_polygon(
                    other_carpet.polygon, try_x_offset, try_y_offset
                )

                manual_collision = check_collision(
                    placed_polygon, try_placed, min_gap=2.0
                )
                print(
                    f"  Manual test at ({try_x}, {try_y}): collision={manual_collision}"
                )

                if not manual_collision:
                    try_bounds = try_placed.bounds
                    print(f"  Manual placement bounds: {try_bounds}")


if __name__ == "__main__":
    test_collision_detection()
