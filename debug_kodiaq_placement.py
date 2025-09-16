#!/usr/bin/env python3

import glob
import os
from layout_optimizer import bin_packing_with_inventory
from dxf_utils import parse_dxf
from carpet import Carpet
from plot import plot_layout

def debug_kodiaq_placement():
    # Load the same DXF files used in the test
    dxf_folder = "dxf_samples/SKODA KODIAQ"
    dxf_files = glob.glob(os.path.join(dxf_folder, "*.dxf"))

    print(f"Found {len(dxf_files)} DXF files in {dxf_folder}")

    # Load all polygons
    all_carpets = []
    for file_path in dxf_files:
        try:
            poly = parse_dxf(file_path)
            filename = os.path.basename(file_path)

            if poly and poly.is_valid and poly.area > 100:  # minimum area check
                carpet = Carpet(
                    polygon=poly,
                    filename=filename,
                    color="белый",  # Изменено для соответствия цвету листов
                    order_id="test_order",
                    priority=1
                )
                all_carpets.append(carpet)
                print(f"Loaded {filename}: area={poly.area:.0f}, bounds={poly.bounds}")
        except Exception as e:
            print(f"Error loading {file_path}: {e}")

    print(f"\nTotal carpets loaded: {len(all_carpets)}")

    # Create carpets list for 20 copies
    carpets_to_place = []
    for _ in range(20):
        carpets_to_place.extend(all_carpets)

    print(f"Total carpets to place (20 copies): {len(carpets_to_place)}")

    # Define sheet inventory - 20 sheets of 140x200cm
    available_sheets = []
    for i in range(20):
        sheet = {
            'width': 1400,  # 140cm in mm
            'height': 2000,  # 200cm in mm
            'color': 'белый',
            'name': f'Лист_{i+1}',  # Исправлено: переименовано в name
            'sheet_type': f'Лист_{i+1}',
            'count': 1,  # Исправлено: добавлено поле count
            'used': 0    # Исправлено: добавлено поле used
        }
        available_sheets.append(sheet)

    print(f"Available sheets: {len(available_sheets)}")

    # Run bin packing
    print("\nRunning bin packing...")
    placed_sheets, unplaced_carpets = bin_packing_with_inventory(
        carpets_to_place,
        available_sheets,
        verbose=True
    )

    print(f"\nResults:")
    print(f"Placed sheets: {len(placed_sheets)}")
    print(f"Unplaced carpets: {len(unplaced_carpets)}")

    # Debug the first sheet (which should be kodiaq1.png)
    if placed_sheets:
        first_sheet = placed_sheets[0]
        print(f"\nFirst sheet details:")
        print(f"Sheet size: {first_sheet.sheet_size}")
        print(f"Usage: {first_sheet.usage_percent:.1f}%")
        print(f"Placed carpets: {len(first_sheet.placed_polygons)}")

        # Check for problems in placements
        for i, placed_carpet in enumerate(first_sheet.placed_polygons):
            print(f"Carpet {i}: {placed_carpet.filename}")
            print(f"  Position: ({placed_carpet.x_offset:.1f}, {placed_carpet.y_offset:.1f})")
            print(f"  Angle: {placed_carpet.angle}°")
            print(f"  Polygon bounds: {placed_carpet.polygon.bounds}")

            # Check if polygon is at origin (indicates missing transformation)
            bounds = placed_carpet.polygon.bounds
            if abs(bounds[0]) < 1 and abs(bounds[1]) < 1:
                print(f"  ⚠️  WARNING: Carpet {placed_carpet.filename} appears to be at origin!")
                print(f"     This suggests transformation was not applied properly")

        # Generate plot for debugging
        print(f"\nGenerating debug plot...")
        os.makedirs('tmp_test', exist_ok=True)
        plot_layout(
            first_sheet.placed_polygons,
            first_sheet.sheet_size[0],
            first_sheet.sheet_size[1],
            f"tmp_test/debug_kodiaq1.png",
            f"Отладка раскроя на листе {first_sheet.sheet_size[0]/10:.0f} x {first_sheet.sheet_size[1]/10:.0f} см"
        )
        print(f"Debug plot saved to tmp_test/debug_kodiaq1.png")

if __name__ == "__main__":
    debug_kodiaq_placement()