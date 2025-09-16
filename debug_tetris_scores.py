#!/usr/bin/env python3

from shapely.geometry import Polygon
from layout_optimizer import bin_packing_with_existing, Carpet


def debug_tetris_scoring():
    """Debug why tetris is choosing rotation over position."""

    # Create existing obstacles (similar to the test case)
    obstacle1 = Polygon([(0, 0), (400, 0), (400, 850), (0, 850)])  # Bottom-left large
    obstacle2 = Polygon(
        [(1000, 0), (1400, 0), (1400, 850), (1000, 850)]
    )  # Bottom-right large

    existing_placed = []
    from carpet import PlacedCarpet

    # Convert to PlacedCarpet
    existing_placed.append(
        PlacedCarpet.from_carpet(
            Carpet(obstacle1, "obstacle1.dxf", "чёрный", "test", 1), 0, 0, 0
        )
    )
    existing_placed.append(
        PlacedCarpet.from_carpet(
            Carpet(obstacle2, "obstacle2.dxf", "чёрный", "test", 1), 0, 0, 0
        )
    )

    # Create new carpet to place (similar shape to test case - roughly rectangular)
    new_carpet_poly = Polygon([(0, 0), (600, 0), (600, 400), (0, 400)])
    new_carpet = Carpet(new_carpet_poly, "new_carpet.dxf", "чёрный", "test", 1)

    print(f"New carpet bounds: {new_carpet_poly.bounds}")
    print(f"New carpet dimensions: {600} x {400} mm")
    print(f"Obstacle 1 bounds: {obstacle1.bounds}")
    print(f"Obstacle 2 bounds: {obstacle2.bounds}")
    print()

    # Test placement
    sheet_size = (144, 200)  # 144cm x 200cm
    additional_placed, remaining_unplaced = bin_packing_with_existing(
        [new_carpet], existing_placed, sheet_size, verbose=True
    )

    if additional_placed:
        placed = additional_placed[0]
        print("\nResult:")
        print(f"Placed at: ({placed.x_offset:.1f}, {placed.y_offset:.1f})")
        print(f"Angle: {placed.angle}°")
        print(f"Final bounds: {placed.polygon.bounds}")

        # Check what position this corresponds to
        if placed.angle == 0:
            print("✅ No rotation - good!")
        elif placed.angle == 90:
            print("❌ Rotated 90° - may not be optimal")

        # Analyze the position
        final_bounds = placed.polygon.bounds
        bottom_y = final_bounds[1]

        if bottom_y < 100:
            print(f"✅ Very low position (Y={bottom_y:.1f})")
        elif bottom_y < 500:
            print(f"⚠️  Medium position (Y={bottom_y:.1f})")
        else:
            print(f"❌ High position (Y={bottom_y:.1f}) - should be lower!")

    else:
        print("❌ Failed to place carpet!")

    return additional_placed, remaining_unplaced


if __name__ == "__main__":
    debug_tetris_scoring()
