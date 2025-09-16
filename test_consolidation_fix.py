#!/usr/bin/env python3

from shapely.geometry import Polygon
from layout_optimizer import simple_sheet_consolidation, PlacedSheet, PlacedCarpet


def create_test_sheet(sheet_number, polygons, sheet_size=(140, 200)):
    """Create a test sheet with given polygons."""
    placed_polygons = []
    for i, (poly, filename) in enumerate(polygons):
        placed_carpet = PlacedCarpet(
            polygon=poly,
            x_offset=0,
            y_offset=0,
            angle=0,
            filename=filename,
            color="белый",
            order_id="test",
            carpet_id=i,
            priority=1,
        )
        placed_polygons.append(placed_carpet)

    sheet = PlacedSheet(
        placed_polygons=placed_polygons,
        usage_percent=50.0,  # Mock usage
        sheet_size=sheet_size,
        sheet_color="белый",
        orders_on_sheet=["test"],
        sheet_type={"name": f"test_sheet_{sheet_number}"},
        sheet_number=sheet_number,
    )
    return sheet


def test_consolidation_fix():
    """Test that consolidation doesn't create duplicate carpets."""

    # Create first sheet with some space
    poly1 = Polygon([(0, 0), (500, 0), (500, 200), (0, 200)])
    sheet1 = create_test_sheet(1, [(poly1, "carpet_1.dxf")])

    # Create second sheet with carpet to move
    poly2 = Polygon([(0, 0), (300, 0), (300, 100), (0, 100)])
    sheet2 = create_test_sheet(2, [(poly2, "carpet_2.dxf")])

    sheets = [sheet1, sheet2]

    print("Before consolidation:")
    print(f"Sheet 1: {len(sheet1.placed_polygons)} carpets")
    print(f"Sheet 2: {len(sheet2.placed_polygons)} carpets")
    print(f"Total carpets: {sum(len(s.placed_polygons) for s in sheets)}")

    # Run consolidation
    result_sheets = simple_sheet_consolidation(sheets)

    print("\nAfter consolidation:")
    total_carpets_after = sum(len(s.placed_polygons) for s in result_sheets)
    print(f"Number of sheets: {len(result_sheets)}")
    print(f"Total carpets: {total_carpets_after}")

    # Check for duplicates
    all_filenames = []
    for sheet in result_sheets:
        for carpet in sheet.placed_polygons:
            all_filenames.append(carpet.filename)

    print(f"Carpet filenames: {all_filenames}")

    duplicates = len(all_filenames) - len(set(all_filenames))
    if duplicates > 0:
        print(f"❌ ERROR: Found {duplicates} duplicate carpets!")
        return False

    if total_carpets_after != 2:  # Should be same as before
        print(f"❌ ERROR: Total carpet count changed from 2 to {total_carpets_after}")
        return False

    print("✅ Consolidation test passed - no duplicates")
    return True


if __name__ == "__main__":
    success = test_consolidation_fix()
    if success:
        print("\n✅ Test PASSED: Consolidation fix works correctly")
    else:
        print("\n❌ Test FAILED: Consolidation still has issues")
