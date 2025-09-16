#!/usr/bin/env python3

import sys
sys.path.append('.')
import os
from pathlib import Path
from dxf_utils import parse_dxf_complete
from layout_optimizer import bin_packing_with_inventory, Carpet
from plot import plot_layout

def regenerate_kodiaq():
    """Regenerate kodiaq1.png with fixes applied"""

    print("Loading SKODA KODIAQ DXF files...")

    # Create available sheets (like in test_skoda.py)
    available_sheets = [{
        "name": f"Черный лист",
        "width": 140,  # cm
        "height": 200,  # cm
        "color": "чёрный",
        "count": 10,
        "used": 0
    }]

    # Load SKODA KODIAQ models
    models = ["SKODA KODIAQ"]
    priority1_polygons = []

    for group_id, group in enumerate(models, 1):
        path = Path('dxf_samples') / group
        files = path.rglob("*.dxf", case_sensitive=False)
        for dxf_file in files:
            try:
                polygon_data = parse_dxf_complete(dxf_file.as_posix(), verbose=False)
                if polygon_data and polygon_data.get("combined_polygon"):
                    base_polygon = polygon_data["combined_polygon"]
                    priority1_polygons.append(Carpet(base_polygon, f"{dxf_file.name}", "чёрный", f"group_{group_id}", 1))
                    print(f"Loaded: {dxf_file.name}")
            except Exception as e:
                print(f"Error loading {dxf_file}: {e}")

    if not priority1_polygons:
        print("No polygons loaded!")
        return

    print(f"Loaded {len(priority1_polygons)} unique carpets")

    # Create 20 copies like in the original test
    all_polygons = []
    for copy_num in range(20):
        for carpet in priority1_polygons:
            # Create copy with modified filename
            copy_carpet = Carpet(
                carpet.polygon,
                f"{carpet.filename.replace('.dxf', '')}_копия_{copy_num + 1}.dxf",
                carpet.color,
                carpet.order_id,
                carpet.priority
            )
            all_polygons.append(copy_carpet)

    print(f"Total carpets to place: {len(all_polygons)}")

    # Run bin packing
    print("Running bin packing...")
    placed_layouts, unplaced = bin_packing_with_inventory(
        all_polygons,
        available_sheets,
        verbose=False
    )

    print(f"Placed {len(placed_layouts)} sheets, {len(unplaced)} unplaced carpets")

    if placed_layouts:
        first_sheet = placed_layouts[0]
        print(f"First sheet: {len(first_sheet.placed_polygons)} carpets, {first_sheet.usage_percent:.1f}% usage")

        # Check for problematic placements
        for i, carpet in enumerate(first_sheet.placed_polygons):
            bounds = carpet.polygon.bounds
            if abs(bounds[0]) < 10 and abs(bounds[1]) < 10:
                print(f"⚠️  Found carpet at origin: {carpet.filename} - will be fixed by plot")

        # Generate new plot
        os.makedirs('tmp_test', exist_ok=True)
        plot_layout(
            first_sheet.placed_polygons,
            first_sheet.sheet_size[0],
            first_sheet.sheet_size[1],
            "tmp_test/kodiaq1_fixed.png",
            f"Исправленный раскрой на листе {first_sheet.sheet_size[0]/10:.0f} x {first_sheet.sheet_size[1]/10:.0f} см"
        )
        print("Fixed plot saved to tmp_test/kodiaq1_fixed.png")

if __name__ == "__main__":
    regenerate_kodiaq()