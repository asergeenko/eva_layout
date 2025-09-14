#!/usr/bin/env python3

from pathlib import Path
from dxf_utils import parse_dxf_complete
from carpet import Carpet
from layout_optimizer import find_bottom_left_position, rotate_polygon, translate_polygon, check_collision
from shapely.geometry import Polygon

def debug_bin_packing_step_by_step():
    """Полное воспроизведение логики bin_packing для понимания проблемы"""

    # Загружаем первые два ковра
    carpets = []
    for i in range(1, 3):
        dxf_path = f'dxf_samples/HYUNDAI SOLARIS 1/{i}.dxf'
        polygon_data = parse_dxf_complete(dxf_path, verbose=False)
        if polygon_data and polygon_data.get("combined_polygon"):
            carpet = Carpet(polygon_data["combined_polygon"], f"{i}.dxf", "чёрный", f"group_{i}", 1)
            carpets.append(carpet)

    if len(carpets) < 2:
        print("Недостаточно ковров")
        return

    print(f"Тестируем размещение 2 ковров:")
    print(f"1.dxf: площадь {carpets[0].polygon.area:.0f} мм²")
    print(f"2.dxf: площадь {carpets[1].polygon.area:.0f} мм²")

    # Размеры листа
    sheet_size = (140, 200)  # см
    sheet_width_mm, sheet_height_mm = sheet_size[0] * 10, sheet_size[1] * 10

    print(f"Лист: {sheet_width_mm} x {sheet_height_mm} мм")

    # Воспроизводим логику bin_packing
    placed = []
    unplaced = []

    # Сортировка (как в bin_packing)
    def get_polygon_priority(carpet: Carpet):
        polygon = carpet.polygon
        area = polygon.area
        bounds = polygon.bounds
        width = bounds[2] - bounds[0]
        height = bounds[3] - bounds[1]
        aspect_ratio = max(width / height, height / width) if min(width, height) > 0 else 1
        compactness = area / (width * height) if width * height > 0 else 0
        perimeter_approx = 2 * (width + height)
        return (
            area * 1.0
            + (aspect_ratio - 1) * area * 0.3
            + (1 - compactness) * area * 0.2
            + perimeter_approx * 0.05
        )

    sorted_polygons = sorted(carpets, key=get_polygon_priority, reverse=True)
    print(f"\nПорядок размещения: {[c.filename for c in sorted_polygons]}")

    # Обрабатываем каждый ковёр
    for i, carpet in enumerate(sorted_polygons):
        print(f"\n{'='*50}")
        print(f"РАЗМЕЩЕНИЕ КОВРА {i+1}: {carpet.filename}")
        print(f"{'='*50}")

        # Проверяем размеры
        bounds = carpet.polygon.bounds
        poly_width = bounds[2] - bounds[0]
        poly_height = bounds[3] - bounds[1]

        print(f"Размеры: {poly_width:.1f} x {poly_height:.1f} мм")

        if poly_width > sheet_width_mm or poly_height > sheet_height_mm:
            print(f"❌ Слишком большой для листа")
            unplaced.append(carpet)
            continue

        # Тестируем все повороты
        best_placement = None
        best_score = float("inf")

        rotation_angles = [0, 90, 180, 270]

        for angle in rotation_angles:
            print(f"\n--- Тестируем поворот {angle}° ---")

            rotated = rotate_polygon(carpet.polygon, angle) if angle != 0 else carpet.polygon
            rotated_bounds = rotated.bounds
            rotated_width = rotated_bounds[2] - rotated_bounds[0]
            rotated_height = rotated_bounds[3] - rotated_bounds[1]

            print(f"Повёрнутые размеры: {rotated_width:.1f} x {rotated_height:.1f} мм")

            # Проверяем поместится ли
            if rotated_width > sheet_width_mm or rotated_height > sheet_height_mm:
                print(f"❌ Не помещается в лист")
                continue

            # Ищем позицию
            print(f"Ищем позицию для повёрнутого полигона...")
            best_x, best_y = find_bottom_left_position(
                rotated, placed, sheet_width_mm, sheet_height_mm
            )

            if best_x is not None and best_y is not None:
                print(f"✅ Найдена позиция: ({best_x:.1f}, {best_y:.1f})")

                # Вычисляем счёт
                position_score = best_y * 10 + best_x * 100

                # Бонусы за форму (как в bin_packing)
                shape_bonus = 0
                aspect_ratio = rotated_width / rotated_height if rotated_height > 0 else 1

                if aspect_ratio > 1.05:
                    width_bonus = min(2000, int((aspect_ratio - 1) * 2000))
                    shape_bonus -= width_bonus
                    if best_y < 5:
                        shape_bonus -= 3000
                    if best_x < 5:
                        shape_bonus -= 2000

                total_score = position_score + shape_bonus
                print(f"Счёт: position={position_score}, shape={shape_bonus}, total={total_score}")

                if total_score < best_score:
                    best_score = total_score
                    translated = translate_polygon(
                        rotated, best_x - rotated_bounds[0], best_y - rotated_bounds[1]
                    )
                    best_placement = {
                        "polygon": translated,
                        "x_offset": best_x - rotated_bounds[0],
                        "y_offset": best_y - rotated_bounds[1],
                        "angle": angle,
                        "position": (best_x, best_y)
                    }
                    print(f"🎯 Новый лучший вариант!")
                else:
                    print(f"Не лучше текущего варианта")
            else:
                print(f"❌ Позиция не найдена")

        # Применяем лучшее размещение
        if best_placement:
            from carpet import PlacedCarpet
            placed_carpet = PlacedCarpet(
                best_placement["polygon"],
                best_placement["x_offset"],
                best_placement["y_offset"],
                best_placement["angle"],
                carpet.filename,
                carpet.color,
                carpet.order_id,
                carpet.carpet_id,
                carpet.priority,
            )
            placed.append(placed_carpet)

            print(f"\n✅ РАЗМЕЩЁН: {carpet.filename}")
            print(f"   Позиция: {best_placement['position']}")
            print(f"   Поворот: {best_placement['angle']}°")
            print(f"   Границы: {best_placement['polygon'].bounds}")
        else:
            print(f"\n❌ НЕ РАЗМЕЩЁН: {carpet.filename}")
            unplaced.append(carpet)

    print(f"\n{'='*60}")
    print("ИТОГОВЫЙ РЕЗУЛЬТАТ:")
    print(f"Размещено: {len(placed)} ковров")
    print(f"Не размещено: {len(unplaced)} ковров")

    if len(placed) < len(carpets):
        print(f"❌ ПРОБЛЕМА: не все ковры размещены!")

        if len(placed) >= 1:
            first_bounds = placed[0].polygon.bounds
            print(f"Первый ковёр занимает: {first_bounds}")

            remaining_width = sheet_width_mm - (first_bounds[2] - first_bounds[0])
            remaining_height = sheet_height_mm - (first_bounds[3] - first_bounds[1])
            print(f"Оставшееся место: {remaining_width:.1f} x {remaining_height:.1f} мм")

if __name__ == "__main__":
    debug_bin_packing_step_by_step()