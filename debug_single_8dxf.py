#!/usr/bin/env python3

from pathlib import Path
from dxf_utils import parse_dxf_complete
from layout_optimizer import Carpet, bin_packing_with_inventory

def test_single_8dxf():
    """Тест с одним ковром 8.dxf чтобы увидеть выбор ориентации."""

    dxf_file = Path('dxf_samples/SKODA KODIAQ/8.dxf')
    if not dxf_file.exists():
        print(f"❌ File not found: {dxf_file}")
        return

    try:
        polygon_data = parse_dxf_complete(dxf_file.as_posix(), verbose=False)
        if not polygon_data or not polygon_data.get("combined_polygon"):
            print("❌ Failed to parse DXF file")
            return

        base_polygon = polygon_data["combined_polygon"]
        carpet = Carpet(base_polygon, "8.dxf", "чёрный", "test", 1)

        print(f"🔍 Testing SINGLE carpet 8.dxf placement")
        print(f"Area: {base_polygon.area/10000:.1f} cm²")
        print(f"Original bounds: {base_polygon.bounds}")
        print()

        # Создаем листы
        available_sheets = [{
            "name": "Черный лист",
            "width": 140,
            "height": 200,
            "color": "чёрный",
            "count": 1,
            "used": 0
        }]

        print("🔄 Running bin_packing_with_inventory with VERBOSE=True...")
        print()

        # Запускаем с verbose=True чтобы увидеть детали
        placed_layouts, unplaced = bin_packing_with_inventory(
            [carpet],
            available_sheets,
            verbose=True
        )

        if placed_layouts and len(placed_layouts) > 0:
            layout = placed_layouts[0]
            if layout.placed_polygons:
                placed_carpet = layout.placed_polygons[0]

                print(f"\n📊 РЕЗУЛЬТАТ:")
                print(f"Angle chosen: {placed_carpet.angle}°")
                print(f"Position: ({placed_carpet.x_offset:.1f}, {placed_carpet.y_offset:.1f})")
                print(f"Final bounds: {placed_carpet.polygon.bounds}")

                # Анализ выбора
                if placed_carpet.angle == 0:
                    print("❌ Original orientation (0°) was chosen - tetris might not be working")
                elif placed_carpet.angle == 90 or placed_carpet.angle == 270:
                    print("🎯 ✅ 90°/270° rotation was chosen - tetris algorithm worked!")
                elif placed_carpet.angle == 180:
                    print("🔄 180° rotation was chosen")

                return placed_layouts
            else:
                print("❌ No carpets were placed")
        else:
            print("❌ No layouts created")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_single_8dxf()