#!/usr/bin/env python3

from pathlib import Path
from dxf_utils import parse_dxf_complete
from layout_optimizer import Carpet, bin_packing_with_inventory

def create_kodiaq_test_carpets():
    """Create multiple copies of Kodiaq carpets for density testing."""
    base_files = ['5.dxf', '7.dxf', '8.dxf']
    carpets = []

    for base_file in base_files:
        file_path = Path(f'dxf_samples/SKODA KODIAQ/{base_file}')
        if not file_path.exists():
            print(f"⚠️ File not found: {file_path}")
            continue

        try:
            polygon_data = parse_dxf_complete(file_path.as_posix(), verbose=False)
            if polygon_data and polygon_data.get("combined_polygon"):
                base_polygon = polygon_data["combined_polygon"]

                # Create multiple copies as shown in the image
                for copy_num in range(2, 6):  # _2, _3, _4, _5 copies
                    filename = f"{file_path.stem}_копия_{copy_num}.dxf"
                    carpet = Carpet(base_polygon, filename, "чёрный", "test", 1)
                    carpets.append(carpet)
                    print(f"✅ Created carpet: {filename}, area: {base_polygon.area/10000:.1f} см²")

        except Exception as e:
            print(f"❌ Error loading {file_path}: {e}")

    print(f"📊 Total carpets created: {len(carpets)}")
    return carpets

def test_kodiaq_density():
    """Test current algorithm density on Kodiaq carpets."""

    # Create test carpets
    carpets = create_kodiaq_test_carpets()
    if not carpets:
        print("❌ No carpets to test!")
        return

    # Sheet specification
    available_sheets = [{
        "name": "Черный лист",
        "width": 140,  # 140 cm
        "height": 200, # 200 cm
        "color": "чёрный",
        "count": 3,    # Allow multiple sheets
        "used": 0
    }]

    print(f"\n=== TESTING CURRENT ALGORITHM ON KODIAQ CARPETS ===")
    print(f"Carpets to place: {len(carpets)}")
    print(f"Total carpet area: {sum(c.polygon.area for c in carpets)/10000:.1f} см²")
    print(f"Sheet area: {140 * 200} см² per sheet")

    # Run optimization
    placed_layouts, unplaced = bin_packing_with_inventory(
        carpets, available_sheets, verbose=True
    )

    # Analyze results
    print(f"\n=== DENSITY ANALYSIS ===")
    print(f"📄 Sheets used: {len(placed_layouts)}")
    print(f"📊 Carpets placed: {len(carpets) - len(unplaced)}/{len(carpets)}")

    total_carpet_area = sum(c.polygon.area for c in carpets if c.carpet_id not in [u.carpet_id for u in unplaced])
    total_sheet_area = len(placed_layouts) * 140 * 200 * 100  # Convert to mm²
    utilization = (total_carpet_area / total_sheet_area) * 100 if total_sheet_area > 0 else 0

    print(f"🎯 Material utilization: {utilization:.1f}%")

    if len(placed_layouts) > 0:
        print(f"\n📄 SHEET DETAILS:")
        for i, layout in enumerate(placed_layouts, 1):
            print(f"   Sheet {i}: {len(layout.placed_polygons)} carpets, {layout.usage_percent:.1f}% full")

            # Analyze wasted space
            max_height = max(c.polygon.bounds[3] for c in layout.placed_polygons) if layout.placed_polygons else 0
            wasted_height = (layout.sheet_size[1] * 10) - max_height  # Convert cm to mm
            wasted_area = (layout.sheet_size[0] * 10) * wasted_height  # mm²

            print(f"      Max height: {max_height:.0f}mm, wasted top space: {wasted_height:.0f}mm ({wasted_area/10000:.1f} см²)")

    if len(unplaced) > 0:
        print(f"\n❌ UNPLACED CARPETS:")
        for carpet in unplaced:
            area_cm2 = carpet.polygon.area / 10000 if hasattr(carpet, 'polygon') else 0
            print(f"   {carpet.filename}: {area_cm2:.1f} см²")

    return placed_layouts, unplaced

if __name__ == "__main__":
    test_kodiaq_density()