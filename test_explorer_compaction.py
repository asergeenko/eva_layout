#!/usr/bin/env python3
"""Test horizontal compaction with explorer carpets from the user's example."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from carpet import Carpet, PlacedCarpet
from layout_optimizer import (
    apply_combined_compaction,
    translate_polygon,
)
from dxf_utils import parse_dxf
from plot import plot_layout


def main():
    print("Loading explorer carpets...")

    # Load the carpets: 2x 1.dxf, 2x 8.dxf
    carpet_1_path = "data/FORD EXPLORER 5/1.dxf"
    carpet_8_path = "data/FORD EXPLORER 5/8.dxf"

    carpet_1_poly = parse_dxf(carpet_1_path, verbose=False)
    carpet_8_poly = parse_dxf(carpet_8_path, verbose=False)

    if carpet_1_poly is None or carpet_8_poly is None:
        print("ERROR: Failed to load carpets")
        return

    print(f"Carpet 1 bounds: {carpet_1_poly.bounds}")
    print(f"Carpet 8 bounds: {carpet_8_poly.bounds}")

    # Create Carpet objects
    carpet_1a = Carpet(
        polygon=carpet_1_poly, filename=carpet_1_path, color="чёрный", order_id="order1"
    )
    carpet_1b = Carpet(
        polygon=carpet_1_poly, filename=carpet_1_path, color="чёрный", order_id="order1"
    )
    carpet_8a = Carpet(
        polygon=carpet_8_poly, filename=carpet_8_path, color="чёрный", order_id="order2"
    )
    carpet_8b = Carpet(
        polygon=carpet_8_poly, filename=carpet_8_path, color="чёрный", order_id="order2"
    )

    # Sheet dimensions
    sheet_width = 1400
    sheet_height = 2000

    # Manually place carpets with horizontal gaps like in explorer.png
    placed_carpets = []

    # Bottom left (1a)
    x_offset_1a = 10
    y_offset_1a = 10
    poly_1a = translate_polygon(
        carpet_1_poly,
        x_offset_1a - carpet_1_poly.bounds[0],
        y_offset_1a - carpet_1_poly.bounds[1],
    )
    placed_carpets.append(
        PlacedCarpet(
            polygon=poly_1a,
            x_offset=x_offset_1a,
            y_offset=y_offset_1a,
            angle=90,
            filename=carpet_1_path,
            color="чёрный",
            order_id="order1",
            carpet_id=carpet_1a.carpet_id,
            priority=carpet_1a.priority,
        )
    )

    # Bottom right (1b) - with horizontal gap
    x_offset_1b = 900  # Large horizontal gap
    y_offset_1b = 10
    poly_1b = translate_polygon(
        carpet_1_poly,
        x_offset_1b - carpet_1_poly.bounds[0],
        y_offset_1b - carpet_1_poly.bounds[1],
    )
    placed_carpets.append(
        PlacedCarpet(
            polygon=poly_1b,
            x_offset=x_offset_1b,
            y_offset=y_offset_1b,
            angle=90,
            filename=carpet_1_path,
            color="чёрный",
            order_id="order1",
            carpet_id=carpet_1b.carpet_id,
            priority=carpet_1b.priority,
        )
    )

    # Upper left (8a)
    x_offset_8a = 50
    y_offset_8a = 1100
    poly_8a = translate_polygon(
        carpet_8_poly,
        x_offset_8a - carpet_8_poly.bounds[0],
        y_offset_8a - carpet_8_poly.bounds[1],
    )
    placed_carpets.append(
        PlacedCarpet(
            polygon=poly_8a,
            x_offset=x_offset_8a,
            y_offset=y_offset_8a,
            angle=90,
            filename=carpet_8_path,
            color="чёрный",
            order_id="order2",
            carpet_id=carpet_8a.carpet_id,
            priority=carpet_8a.priority,
        )
    )

    # Upper right (8b)
    x_offset_8b = 700
    y_offset_8b = 1500
    poly_8b = translate_polygon(
        carpet_8_poly,
        x_offset_8b - carpet_8_poly.bounds[0],
        y_offset_8b - carpet_8_poly.bounds[1],
    )
    placed_carpets.append(
        PlacedCarpet(
            polygon=poly_8b,
            x_offset=x_offset_8b,
            y_offset=y_offset_8b,
            angle=180,
            filename=carpet_8_path,
            color="чёрный",
            order_id="order2",
            carpet_id=carpet_8b.carpet_id,
            priority=carpet_8b.priority,
        )
    )

    print("\n=== BEFORE COMPACTION ===")
    for i, c in enumerate(placed_carpets):
        bounds = c.polygon.bounds
        print(
            f"Carpet {i}: left_x={bounds[0]:.1f}, right_x={bounds[2]:.1f}, width={bounds[2]-bounds[0]:.1f}"
        )

    # Save before image
    print("\nGenerating BEFORE visualization...")
    buf_before = plot_layout(placed_carpets, (sheet_width / 10, sheet_height / 10))
    with open("tmp_test/explorer_before_compaction.png", "wb") as f:
        f.write(buf_before.read())
    print("Saved: tmp_test/explorer_before_compaction.png")

    # Apply combined compaction (alternating vertical + horizontal)
    print("\n=== APPLYING COMBINED COMPACTION ===")
    placed_final = apply_combined_compaction(
        placed_carpets, sheet_width, sheet_height, max_iterations=3
    )

    print("\n=== AFTER COMPACTION ===")
    for i, c in enumerate(placed_final):
        bounds = c.polygon.bounds
        print(
            f"Carpet {i}: left_x={bounds[0]:.1f}, right_x={bounds[2]:.1f}, width={bounds[2]-bounds[0]:.1f}"
        )

    # Calculate horizontal movement
    print("\n=== HORIZONTAL MOVEMENT ===")
    for i in range(len(placed_carpets)):
        before_x = placed_carpets[i].polygon.bounds[0]
        after_x = placed_final[i].polygon.bounds[0]
        movement = before_x - after_x
        print(
            f"Carpet {i}: moved LEFT by {movement:.1f}mm (from X={before_x:.1f} to X={after_x:.1f})"
        )

    # Save after image
    print("\nGenerating AFTER visualization...")
    buf_after = plot_layout(placed_final, (sheet_width / 10, sheet_height / 10))
    with open("tmp_test/explorer_after_compaction.png", "wb") as f:
        f.write(buf_after.read())
    print("Saved: tmp_test/explorer_after_compaction.png")

    # Calculate used width
    print("\n=== SHEET UTILIZATION ===")
    max_x_before = max(c.polygon.bounds[2] for c in placed_carpets)
    max_x_after = max(c.polygon.bounds[2] for c in placed_final)
    print(
        f"Before: max X = {max_x_before:.1f}mm ({max_x_before/sheet_width*100:.1f}% of sheet width)"
    )
    print(
        f"After:  max X = {max_x_after:.1f}mm ({max_x_after/sheet_width*100:.1f}% of sheet width)"
    )
    print(f"Improvement: {max_x_before - max_x_after:.1f}mm saved")

    print(
        "\nTest complete! Check tmp_test/explorer_before_compaction.png and tmp_test/explorer_after_compaction.png"
    )


if __name__ == "__main__":
    main()
