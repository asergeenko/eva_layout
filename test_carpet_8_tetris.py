#!/usr/bin/env python3

from pathlib import Path
from dxf_utils import parse_dxf_complete
from layout_optimizer import Carpet, bin_packing_with_existing
from carpet import PlacedCarpet


def test_carpet_8_tetris_improvement():
    """Специфичный тест для ковра 8.dxf - проверяем что новая тетрисовость работает."""

    # Загружаем ковер 8.dxf
    dxf_file = Path("dxf_samples/SKODA KODIAQ/8.dxf")
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

        print("📊 Testing carpet 8.dxf tetris behavior")
        print(f"Area: {base_polygon.area/10000:.1f} cm²")
        print()

        # Создаем простые препятствия для имитации уже размещенных ковров
        from shapely import affinity

        obstacle_polygon = affinity.translate(
            base_polygon.buffer(0), xoff=300, yoff=300
        )
        existing_placed = [
            PlacedCarpet.from_carpet(
                Carpet(obstacle_polygon, "obstacle1.dxf", "чёрный", "test", 1), 0, 0, 0
            )
        ]

        print("🔄 Testing placement with tetris quality assessment...")

        # Тестируем размещение на листе 140x200 см
        sheet_size = (140, 200)  # cm
        additional_placed, remaining_unplaced = bin_packing_with_existing(
            [carpet],
            existing_placed,
            sheet_size,
            verbose=True,  # Включаем детальное логирование
        )

        if additional_placed:
            placed = additional_placed[0]
            print("\n✅ РЕЗУЛЬТАТ РАЗМЕЩЕНИЯ:")
            print(f"Angle: {placed.angle}°")
            print(f"Position: ({placed.x_offset:.1f}, {placed.y_offset:.1f})")
            print(f"Final bounds: {placed.polygon.bounds}")

            # Анализ результата
            bounds = placed.polygon.bounds
            height = bounds[3] - bounds[1]
            width = bounds[2] - bounds[0]
            aspect_ratio = width / height if height > 0 else 1

            print(f"Dimensions: {width:.0f}mm x {height:.0f}mm")
            print(f"Aspect ratio: {aspect_ratio:.2f}")

            if placed.angle == 90 or placed.angle == 270:
                print("🎯 ✅ Carpet was rotated - likely for better tetris quality!")
            else:
                print("ℹ️  Carpet kept original orientation")

            # Проверим доступность пространства снизу
            bottom_y = bounds[1]
            if bottom_y > 50:  # Больше 50мм от низа
                print(
                    f"⚠️  Carpet is {bottom_y:.0f}mm from bottom - some space below may be trapped"
                )
            else:
                print(
                    f"✅ Carpet is close to bottom ({bottom_y:.0f}mm) - good tetris placement"
                )

        else:
            print("❌ Failed to place carpet")

        return additional_placed, remaining_unplaced

    except Exception as e:
        print(f"❌ Error: {e}")
        return [], []


if __name__ == "__main__":
    test_carpet_8_tetris_improvement()
