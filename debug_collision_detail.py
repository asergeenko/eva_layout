#!/usr/bin/env python3

from pathlib import Path
from dxf_utils import parse_dxf_complete
from carpet import Carpet, PlacedCarpet
from layout_optimizer import rotate_polygon, translate_polygon, check_collision
from shapely.geometry import Polygon

def test_specific_position():
    """Проверяем конкретную позицию, которая должна работать"""

    # Загружаем ковры
    carpets = []
    for i in range(1, 3):
        dxf_path = f'dxf_samples/HYUNDAI SOLARIS 1/{i}.dxf'
        polygon_data = parse_dxf_complete(dxf_path, verbose=False)
        if polygon_data and polygon_data.get("combined_polygon"):
            carpet = Carpet(polygon_data["combined_polygon"], f"{i}.dxf", "чёрный", f"group_{i}", 1)
            carpets.append(carpet)

    # Первый ковёр: повёрнут на 90° и размещён в (0, 0)
    first_rotated = rotate_polygon(carpets[0].polygon, 90)
    first_bounds = first_rotated.bounds
    first_translated = translate_polygon(first_rotated, 0 - first_bounds[0], 0 - first_bounds[1])

    print(f"Первый ковёр:")
    print(f"  Оригинальные границы: {carpets[0].polygon.bounds}")
    print(f"  После поворота 90°: {first_rotated.bounds}")
    print(f"  После размещения в (0,0): {first_translated.bounds}")

    # Второй ковёр без поворота
    second_polygon = carpets[1].polygon
    second_bounds = second_polygon.bounds

    print(f"\nВторой ковёр:")
    print(f"  Оригинальные границы: {second_bounds}")
    print(f"  Размеры: {second_bounds[2] - second_bounds[0]:.1f} x {second_bounds[3] - second_bounds[1]:.1f} мм")

    # Лист
    sheet_width_mm, sheet_height_mm = 1400, 2000

    # Тестируем конкретные позиции, где второй ковёр должен помещаться
    test_positions = [
        (0, 700),
        (0, 800),
        (0, 900),
        (0, 1000),
        (850, 0),  # Справа от первого ковра
        (850, 100),
        (850, 200),
    ]

    print(f"\nТестируем конкретные позиции:")

    for test_x, test_y in test_positions:
        print(f"\n--- Позиция ({test_x}, {test_y}) ---")

        # Вычисляем смещение
        x_offset = test_x - second_bounds[0]
        y_offset = test_y - second_bounds[1]

        # Создаём размещённый полигон
        test_polygon = translate_polygon(second_polygon, x_offset, y_offset)
        test_bounds = test_polygon.bounds

        print(f"Смещение: ({x_offset:.1f}, {y_offset:.1f})")
        print(f"Итоговые границы: {test_bounds}")

        # Проверяем границы листа
        if (test_bounds[0] < 0 or test_bounds[1] < 0 or
            test_bounds[2] > sheet_width_mm or test_bounds[3] > sheet_height_mm):
            print(f"❌ Выходит за границы листа")
            print(f"   Лист: (0, 0, {sheet_width_mm}, {sheet_height_mm})")
            continue

        # Проверяем коллизию с первым ковром
        collision = check_collision(test_polygon, first_translated, min_gap=2.0)
        print(f"Коллизия с первым ковром: {collision}")

        if not collision:
            print(f"✅ ПОЗИЦИЯ ВАЛИДНА!")

            # Вычисляем пересечение границ для визуального контроля
            first_bounds = first_translated.bounds
            print(f"Первый ковёр: ({first_bounds[0]:.1f}, {first_bounds[1]:.1f}, {first_bounds[2]:.1f}, {first_bounds[3]:.1f})")
            print(f"Второй ковёр: ({test_bounds[0]:.1f}, {test_bounds[1]:.1f}, {test_bounds[2]:.1f}, {test_bounds[3]:.1f})")

            # Проверяем, не пересекаются ли прямоугольники границ
            boxes_overlap = not (
                first_bounds[2] <= test_bounds[0] or  # первый левее второго
                test_bounds[2] <= first_bounds[0] or  # второй левее первого
                first_bounds[3] <= test_bounds[1] or  # первый ниже второго
                test_bounds[3] <= first_bounds[1]     # второй ниже первого
            )
            print(f"Пересечение bounding box'ов: {boxes_overlap}")

            if not boxes_overlap:
                print(f"🎯 НАЙДЕНА РАБОЧАЯ ПОЗИЦИЯ: ({test_x}, {test_y})")
                return

        else:
            print(f"❌ Коллизия обнаружена")

            # Детальная диагностика коллизии
            distance = first_translated.distance(test_polygon)
            intersection = first_translated.intersects(test_polygon)
            print(f"   Геометрическое расстояние: {distance:.3f} мм")
            print(f"   Пересечение полигонов: {intersection}")

            if intersection:
                try:
                    overlap = first_translated.intersection(test_polygon)
                    if hasattr(overlap, 'area'):
                        print(f"   Площадь пересечения: {overlap.area:.1f} мм²")
                except:
                    print(f"   Не удалось вычислить площадь пересечения")

    print(f"\n❌ Ни одна из тестовых позиций не подошла")

if __name__ == "__main__":
    test_specific_position()