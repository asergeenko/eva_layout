#!/usr/bin/env python3

from pathlib import Path
from dxf_utils import parse_dxf_complete
from carpet import Carpet
from layout_optimizer import bin_packing_with_inventory
import matplotlib.pyplot as plt
from shapely.geometry import Polygon

def analyze_1dxf():
    """Analyze the first carpet (1.dxf) to understand its dimensions and collision behavior"""

    # Parse 1.dxf
    dxf_path = Path('dxf_samples/HYUNDAI SOLARIS 1/1.dxf')
    print(f"Analyzing: {dxf_path}")

    polygon_data = parse_dxf_complete(dxf_path.as_posix(), verbose=True)

    if not polygon_data or not polygon_data.get("combined_polygon"):
        print("Failed to parse DXF")
        return

    polygon = polygon_data["combined_polygon"]
    carpet = Carpet(polygon, "1.dxf", "чёрный", "group_1", 1)

    print(f"\n1.dxf Analysis:")
    print(f"  Area: {polygon.area:.2f} mm²")
    print(f"  Bounds: {polygon.bounds}")

    # Calculate dimensions from bounds
    bounds = polygon.bounds
    width_mm = bounds[2] - bounds[0]  # max_x - min_x
    height_mm = bounds[3] - bounds[1]  # max_y - min_y

    print(f"  Bounding box: {width_mm:.1f} x {height_mm:.1f} mm")
    print(f"  Bounding box: {width_mm/10:.1f} x {height_mm/10:.1f} cm")

    # Available sheet dimensions
    sheet_width_mm = 140 * 10  # 1400mm
    sheet_height_mm = 200 * 10  # 2000mm

    print(f"\nSheet dimensions: {sheet_width_mm} x {sheet_height_mm} mm")
    print(f"Carpet fits in sheet: width={width_mm < sheet_width_mm}, height={height_mm < sheet_height_mm}")

    # Test with simple rotation
    from shapely.affinity import rotate
    rotated_90 = rotate(polygon, 90, origin='centroid')
    rot_bounds = rotated_90.bounds
    rot_width_mm = rot_bounds[2] - rot_bounds[0]
    rot_height_mm = rot_bounds[3] - rot_bounds[1]

    print(f"\nRotated 90° dimensions: {rot_width_mm:.1f} x {rot_height_mm:.1f} mm")
    print(f"Rotated 90° fits: width={rot_width_mm < sheet_width_mm}, height={rot_height_mm < sheet_height_mm}")

    # Now test with multiple carpets
    print(f"\n" + "="*60)
    print("TESTING WITH ALL 5 CARPETS")
    print("="*60)

    # Load all 5 carpets
    models = ["HYUNDAI SOLARIS 1"]
    priority1_polygons = []
    for group_id, group in enumerate(models, 1):
        path = Path('dxf_samples') / group
        files = path.rglob("*.dxf", case_sensitive=False)
        for dxf_file in sorted(files):
            try:
                polygon_data = parse_dxf_complete(dxf_file.as_posix(), verbose=False)
                if polygon_data and polygon_data.get("combined_polygon"):
                    base_polygon = polygon_data["combined_polygon"]
                    carpet = Carpet(base_polygon, f"{dxf_file.name}", "чёрный", f"group_{group_id}", 1)
                    priority1_polygons.append(carpet)
                    print(f"  {dxf_file.name}: {base_polygon.area:.0f} mm² area, bounds {base_polygon.bounds}")
            except Exception as e:
                print(f"⚠️ Error loading {dxf_file}: {e}")

    print(f"\nTotal carpets loaded: {len(priority1_polygons)}")
    total_area = sum(c.polygon.area for c in priority1_polygons)
    sheet_area = sheet_width_mm * sheet_height_mm
    theoretical_utilization = (total_area / sheet_area) * 100
    print(f"Total area: {total_area:.0f} mm² ({total_area/100:.0f} cm²)")
    print(f"Sheet area: {sheet_area:.0f} mm² ({sheet_area/100:.0f} cm²)")
    print(f"Theoretical utilization: {theoretical_utilization:.1f}%")

    # Test bin packing
    available_sheets = [{
        "name": f"Черный лист",
        "width": 140,
        "height": 200,
        "color": "чёрный",
        "count": 5,
        "used": 0
    }]

    print(f"\nRunning bin packing...")
    placed_layouts, unplaced = bin_packing_with_inventory(
        priority1_polygons,
        available_sheets,
        verbose=False,
    )

    print(f"Results: {len(placed_layouts)} sheets, {len(unplaced)} unplaced")

    for i, layout in enumerate(placed_layouts, 1):
        carpet_count = len(layout.placed_polygons)
        usage = layout.usage_percent
        print(f"  Sheet {i}: {carpet_count} carpets, {usage:.1f}% usage")

        for j, placed_carpet in enumerate(layout.placed_polygons):
            print(f"    {placed_carpet.filename}: pos=({placed_carpet.x_offset:.1f}, {placed_carpet.y_offset:.1f}), angle={placed_carpet.angle}°")

    # Special focus on the first carpet collision detection
    if len(placed_layouts) >= 1:
        print(f"\n" + "="*60)
        print("ANALYZING FIRST SHEET COLLISION DETECTION")
        print("="*60)

        first_sheet = placed_layouts[0]
        if len(first_sheet.placed_polygons) == 1:
            first_placed = first_sheet.placed_polygons[0]
            print(f"First carpet {first_placed.filename} is ALONE on sheet 1")
            print(f"Position: ({first_placed.x_offset:.1f}, {first_placed.y_offset:.1f})")
            print(f"Rotation: {first_placed.angle}°")

            # Get the transformed polygon
            from shapely.affinity import rotate, translate
            transformed = rotate(first_placed.polygon, first_placed.angle, origin='centroid')
            transformed = translate(transformed, first_placed.x_offset, first_placed.y_offset)

            trans_bounds = transformed.bounds
            print(f"Transformed bounds: {trans_bounds}")
            print(f"Transformed size: {trans_bounds[2]-trans_bounds[0]:.1f} x {trans_bounds[3]-trans_bounds[1]:.1f} mm")

            # Calculate remaining space
            remaining_width = sheet_width_mm - (trans_bounds[2] - trans_bounds[0])
            remaining_height = sheet_height_mm - (trans_bounds[3] - trans_bounds[1])
            print(f"Remaining space after placing: {remaining_width:.1f} x {remaining_height:.1f} mm")

            # Check if any other carpets could fit in remaining space
            print(f"\nChecking if other carpets could fit in remaining space...")
            for i, other_carpet in enumerate(priority1_polygons[1:], 2):
                other_bounds = other_carpet.polygon.bounds
                other_width = other_bounds[2] - other_bounds[0]
                other_height = other_bounds[3] - other_bounds[1]

                fits_normal = (other_width <= remaining_width and other_height <= remaining_height)
                fits_rotated = (other_height <= remaining_width and other_width <= remaining_height)

                print(f"  {other_carpet.carpet_id} ({other_width:.1f}x{other_height:.1f}): normal={fits_normal}, rotated={fits_rotated}")

                if fits_normal or fits_rotated:
                    print(f"    ❗ {other_carpet.carpet_id} SHOULD FIT but didn't get placed!")

if __name__ == "__main__":
    analyze_1dxf()