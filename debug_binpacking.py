#!/usr/bin/env python3

from dxf_utils import parse_dxf_complete
from carpet import Carpet
from layout_optimizer import bin_packing


def test_bin_packing_directly():
    """Test the bin_packing function directly with the 5 Solaris carpets"""

    # Load all 5 carpets
    carpets = []
    for i in range(1, 6):
        dxf_path = f"dxf_samples/HYUNDAI SOLARIS 1/{i}.dxf"
        polygon_data = parse_dxf_complete(dxf_path, verbose=False)
        if polygon_data and polygon_data.get("combined_polygon"):
            carpet = Carpet(
                polygon_data["combined_polygon"], f"{i}.dxf", "чёрный", f"group_{i}", 1
            )
            carpets.append(carpet)
            print(f"Loaded {i}.dxf: area={carpet.polygon.area:.0f} mm²")

    print(f"\nTotal carpets: {len(carpets)}")
    print(f"Total area: {sum(c.polygon.area for c in carpets):.0f} mm²")

    # Sheet dimensions (same as in test)
    sheet_size = (140, 200)  # cm
    sheet_area = sheet_size[0] * sheet_size[1] * 100  # cm²
    print(f"Sheet area: {sheet_area:.0f} cm²")

    # Calculate theoretical utilization
    total_carpet_area_cm2 = sum(c.polygon.area for c in carpets) / 100  # Convert to cm²
    theoretical_utilization = (total_carpet_area_cm2 / sheet_area) * 100
    print(f"Theoretical utilization: {theoretical_utilization:.1f}%")

    print("\n" + "=" * 60)
    print("TESTING BIN_PACKING DIRECTLY")
    print("=" * 60)

    # Call bin_packing with verbose=True to see what's happening
    placed, unplaced = bin_packing(carpets, sheet_size, verbose=True)

    print("\nResults:")
    print(f"Placed: {len(placed)} carpets")
    print(f"Unplaced: {len(unplaced)} carpets")

    if placed:
        placed_area_cm2 = sum(p.polygon.area for p in placed) / 100
        actual_utilization = (placed_area_cm2 / sheet_area) * 100
        print(f"Actual utilization: {actual_utilization:.1f}%")

        print("\nPlaced carpets:")
        for i, p in enumerate(placed):
            bounds = p.polygon.bounds
            print(
                f"  {p.filename}: pos=({p.x_offset:.1f}, {p.y_offset:.1f}), angle={p.angle}°, bounds={bounds}"
            )

    if unplaced:
        print("\nUnplaced carpets:")
        for u in unplaced:
            print(f"  {u.filename}")

    # If not all carpets were placed, this is the bug
    if len(placed) < len(carpets):
        print(f"\n❌ BUG DETECTED: Only {len(placed)}/{len(carpets)} carpets placed!")
        print("   This explains why they get split across multiple sheets")

        # Let's test step by step
        print("\n" + "=" * 60)
        print("STEP-BY-STEP DEBUGGING")
        print("=" * 60)

        # Test placing just the first carpet
        print("\n1. Testing with just the first carpet:")
        placed1, unplaced1 = bin_packing([carpets[0]], sheet_size, verbose=False)
        print(f"   Result: {len(placed1)} placed, {len(unplaced1)} unplaced")

        # Test placing first + second carpet
        print("\n2. Testing with first + second carpet:")
        placed2, unplaced2 = bin_packing(
            [carpets[0], carpets[1]], sheet_size, verbose=False
        )
        print(f"   Result: {len(placed2)} placed, {len(unplaced2)} unplaced")
        if len(placed2) < 2:
            print("   ❌ PROBLEM: Cannot place first + second together!")

        # Test placing second + first carpet (reverse order)
        print("\n3. Testing with second + first carpet (reverse order):")
        placed3, unplaced3 = bin_packing(
            [carpets[1], carpets[0]], sheet_size, verbose=False
        )
        print(f"   Result: {len(placed3)} placed, {len(unplaced3)} unplaced")

        # Test with smaller carpets first
        smaller_carpets = sorted(carpets, key=lambda c: c.polygon.area)
        print("\n4. Testing with carpets sorted by area (smallest first):")
        placed4, unplaced4 = bin_packing(smaller_carpets, sheet_size, verbose=False)
        print(f"   Result: {len(placed4)} placed, {len(unplaced4)} unplaced")

        if len(placed4) > len(placed):
            print(
                f"   ✅ IMPROVEMENT: Smallest-first got {len(placed4)} vs {len(placed)}"
            )

    else:
        print("\n✅ All carpets placed successfully!")


if __name__ == "__main__":
    test_bin_packing_directly()
