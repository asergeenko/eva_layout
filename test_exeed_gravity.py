#!/usr/bin/env python3
"""Test gravity fix with exeed carpets from the user's example."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from carpet import Carpet, PlacedCarpet
from layout_optimizer import apply_aggressive_gravity, translate_polygon
from dxf_utils import parse_dxf
from plot import plot_layout


def main():
    print("Loading exeed carpets...")

    # Load the carpets mentioned by user: 2x 3.dxf, 1x 4.dxf
    carpet_3_path = "data/EXEED VX/3.dxf"
    carpet_4_path = "data/EXEED VX/4.dxf"

    carpet_3_poly = parse_dxf(carpet_3_path, verbose=False)
    carpet_4_poly = parse_dxf(carpet_4_path, verbose=False)

    if carpet_3_poly is None or carpet_4_poly is None:
        print("ERROR: Failed to load carpets")
        return

    print(f"Carpet 3 bounds: {carpet_3_poly.bounds}")
    print(f"Carpet 4 bounds: {carpet_4_poly.bounds}")

    # Create Carpet objects
    carpet_3a = Carpet(
        polygon=carpet_3_poly, filename=carpet_3_path, color="синий", order_id="order1"
    )
    carpet_3b = Carpet(
        polygon=carpet_3_poly, filename=carpet_3_path, color="синий", order_id="order1"
    )
    carpet_4 = Carpet(
        polygon=carpet_4_poly,
        filename=carpet_4_path,
        color="фиолетовый",
        order_id="order2",
    )

    # Sheet dimensions (typical 140x200cm = 1400x2000mm)
    sheet_width = 1400
    sheet_height = 2000

    # Manually place carpets at different heights to simulate poor packing
    # We'll place them with large gaps like in exeed.png
    # Stack them vertically in the same column to test gravity
    placed_carpets = []

    # Bottom carpet (3a) - place at bottom left
    x_offset_3a = 10
    y_offset_3a = 10
    poly_3a = translate_polygon(
        carpet_3_poly,
        x_offset_3a - carpet_3_poly.bounds[0],
        y_offset_3a - carpet_3_poly.bounds[1],
    )
    carpet_3a_placed = PlacedCarpet(
        polygon=poly_3a,
        x_offset=x_offset_3a,
        y_offset=y_offset_3a,
        angle=0,
        filename=carpet_3_path,
        color="синий",
        order_id="order1",
        carpet_id=carpet_3a.carpet_id,
        priority=carpet_3a.priority,
    )
    placed_carpets.append(carpet_3a_placed)

    # Middle carpet (4) - place with large gap above first, same X
    x_offset_4 = 10
    y_offset_4 = 1200  # Large gap above first carpet
    poly_4 = translate_polygon(
        carpet_4_poly,
        x_offset_4 - carpet_4_poly.bounds[0],
        y_offset_4 - carpet_4_poly.bounds[1],
    )
    carpet_4_placed = PlacedCarpet(
        polygon=poly_4,
        x_offset=x_offset_4,
        y_offset=y_offset_4,
        angle=0,
        filename=carpet_4_path,
        color="фиолетовый",
        order_id="order2",
        carpet_id=carpet_4.carpet_id,
        priority=carpet_4.priority,
    )
    placed_carpets.append(carpet_4_placed)

    # Top carpet (3b) - place high up with gap, adjacent horizontally
    x_offset_3b = 750  # Place next to the column
    y_offset_3b = 1200  # Same height as middle carpet
    poly_3b = translate_polygon(
        carpet_3_poly,
        x_offset_3b - carpet_3_poly.bounds[0],
        y_offset_3b - carpet_3_poly.bounds[1],
    )
    carpet_3b_placed = PlacedCarpet(
        polygon=poly_3b,
        x_offset=x_offset_3b,
        y_offset=y_offset_3b,
        angle=0,
        filename=carpet_3_path,
        color="зелёный",
        order_id="order3",
        carpet_id=carpet_3b.carpet_id,
        priority=carpet_3b.priority,
    )
    placed_carpets.append(carpet_3b_placed)

    print("\n=== BEFORE GRAVITY ===")
    for i, c in enumerate(placed_carpets):
        bounds = c.polygon.bounds
        print(
            f"Carpet {i}: bottom_y={bounds[1]:.1f}, top_y={bounds[3]:.1f}, height={bounds[3]-bounds[1]:.1f}"
        )

    # Save before image
    print("\nGenerating BEFORE visualization...")
    buf_before = plot_layout(placed_carpets, (sheet_width / 10, sheet_height / 10))
    with open("tmp_test/exeed_before_gravity.png", "wb") as f:
        f.write(buf_before.read())
    print("Saved: tmp_test/exeed_before_gravity.png")

    # Apply aggressive gravity
    print("\n=== APPLYING GRAVITY ===")
    placed_after = apply_aggressive_gravity(
        placed_carpets, sheet_width, sheet_height, max_iterations=5
    )

    print("\n=== AFTER GRAVITY ===")
    for i, c in enumerate(placed_after):
        bounds = c.polygon.bounds
        print(
            f"Carpet {i}: bottom_y={bounds[1]:.1f}, top_y={bounds[3]:.1f}, height={bounds[3]-bounds[1]:.1f}"
        )

    # Calculate movement
    print("\n=== MOVEMENT ===")
    for i in range(len(placed_carpets)):
        before_y = placed_carpets[i].polygon.bounds[1]
        after_y = placed_after[i].polygon.bounds[1]
        movement = before_y - after_y
        print(
            f"Carpet {i}: moved DOWN by {movement:.1f}mm (from Y={before_y:.1f} to Y={after_y:.1f})"
        )

    # Save after image
    print("\nGenerating AFTER visualization...")
    buf_after = plot_layout(placed_after, (sheet_width / 10, sheet_height / 10))
    with open("tmp_test/exeed_after_gravity.png", "wb") as f:
        f.write(buf_after.read())
    print("Saved: tmp_test/exeed_after_gravity.png")

    # Check for gaps
    print("\n=== GAP ANALYSIS ===")
    sorted_carpets = sorted(placed_after, key=lambda c: c.polygon.bounds[1])
    for i in range(len(sorted_carpets) - 1):
        top_of_lower = sorted_carpets[i].polygon.bounds[3]
        bottom_of_upper = sorted_carpets[i + 1].polygon.bounds[1]
        gap = bottom_of_upper - top_of_lower
        print(f"Gap between carpet {i} and {i+1}: {gap:.1f}mm")

    print(
        "\nTest complete! Check tmp_test/exeed_before_gravity.png and tmp_test/exeed_after_gravity.png"
    )


if __name__ == "__main__":
    main()
