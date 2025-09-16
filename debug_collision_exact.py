#!/usr/bin/env python3

from dxf_utils import parse_dxf_complete
from carpet import Carpet
from layout_optimizer import rotate_polygon, translate_polygon, check_collision


def debug_collision_function():
    """Точная отладка функции check_collision"""

    # Загружаем ковры
    carpets = []
    for i in range(1, 3):
        dxf_path = f"dxf_samples/HYUNDAI SOLARIS 1/{i}.dxf"
        polygon_data = parse_dxf_complete(dxf_path, verbose=False)
        if polygon_data and polygon_data.get("combined_polygon"):
            carpet = Carpet(
                polygon_data["combined_polygon"], f"{i}.dxf", "чёрный", f"group_{i}", 1
            )
            carpets.append(carpet)

    # Первый ковёр: повёрнут на 90° и размещён в (0, 0)
    first_rotated = rotate_polygon(carpets[0].polygon, 90)
    first_bounds = first_rotated.bounds
    first_translated = translate_polygon(
        first_rotated, 0 - first_bounds[0], 0 - first_bounds[1]
    )

    # Второй ковёр в позиции (0, 900)
    second_polygon = carpets[1].polygon
    second_bounds = second_polygon.bounds
    x_offset = 0 - second_bounds[0]
    y_offset = 900 - second_bounds[1]
    second_translated = translate_polygon(second_polygon, x_offset, y_offset)

    print("Первый полигон:")
    print(f"  valid: {first_translated.is_valid}")
    print(f"  simple: {first_translated.is_simple}")
    print(f"  bounds: {first_translated.bounds}")

    print("\nВторой полигон:")
    print(f"  valid: {second_translated.is_valid}")
    print(f"  simple: {second_translated.is_simple}")
    print(f"  bounds: {second_translated.bounds}")

    # Пошаговая отладка check_collision
    print("\nПошаговая отладка check_collision:")

    # 1. Проверка валидности
    valid_check = first_translated.is_valid and second_translated.is_valid
    print(f"1. Валидность полигонов: {valid_check}")
    if not valid_check:
        print("❌ ПРОБЛЕМА: Один из полигонов невалиден!")
        return

    # 2. Проверка пересечения
    intersects = first_translated.intersects(second_translated)
    print(f"2. Пересечение полигонов: {intersects}")
    if intersects:
        print("❌ Полигоны пересекаются - коллизия True")
        return

    # 3. Вычисление расстояний между bounding box'ами
    bounds1 = first_translated.bounds
    bounds2 = second_translated.bounds
    print("3. Bounding boxes:")
    print(f"   Первый: {bounds1}")
    print(f"   Второй: {bounds2}")

    dx = max(0, max(bounds1[0] - bounds2[2], bounds2[0] - bounds1[2]))
    dy = max(0, max(bounds1[1] - bounds2[3], bounds2[1] - bounds1[3]))
    bbox_min_distance = (dx * dx + dy * dy) ** 0.5
    print(f"   dx: {dx:.3f}, dy: {dy:.3f}")
    print(f"   bbox_min_distance: {bbox_min_distance:.3f} мм")

    min_gap = 2.0
    safety_margin = 50.0
    threshold = min_gap + safety_margin

    print("4. Проверка раннего выхода:")
    print(f"   min_gap: {min_gap} мм")
    print(f"   safety_margin: {safety_margin} мм")
    print(f"   threshold: {threshold} мм")
    print(f"   bbox_min_distance > threshold: {bbox_min_distance > threshold}")

    if bbox_min_distance > threshold:
        print("✅ Ранний выход - полигоны далеко, коллизии нет")
        return

    # 5. Геометрическое расстояние
    print("5. Геометрическое расстояние:")
    try:
        geometric_distance = first_translated.distance(second_translated)
        print(f"   geometric_distance: {geometric_distance:.3f} мм")
        collision_result = geometric_distance < min_gap
        print(f"   geometric_distance < min_gap: {collision_result}")
        print(f"   Итоговый результат коллизии: {collision_result}")
    except Exception as e:
        print(f"❌ Ошибка при вычислении расстояния: {e}")
        print("   Возвращаем True по умолчанию")

    # Сравним с фактическим вызовом функции
    print("\n6. Фактический вызов check_collision:")
    actual_result = check_collision(first_translated, second_translated, min_gap=2.0)
    print(f"   Результат: {actual_result}")


if __name__ == "__main__":
    debug_collision_function()
