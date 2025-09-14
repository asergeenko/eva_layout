#!/usr/bin/env python3

from pathlib import Path
from dxf_utils import parse_dxf_complete
from carpet import Carpet, PlacedCarpet
from layout_optimizer import rotate_polygon, translate_polygon, check_collision
from shapely.geometry import Polygon

def debug_find_positions():
    """Отладка функции find_bottom_left_position с выводом всех тестируемых позиций"""

    # Загружаем ковры
    carpets = []
    for i in range(1, 3):
        dxf_path = f'dxf_samples/HYUNDAI SOLARIS 1/{i}.dxf'
        polygon_data = parse_dxf_complete(dxf_path, verbose=False)
        if polygon_data and polygon_data.get("combined_polygon"):
            carpet = Carpet(polygon_data["combined_polygon"], f"{i}.dxf", "чёрный", f"group_{i}", 1)
            carpets.append(carpet)

    # Воссоздаём ситуацию: первый ковёр размещён
    first_rotated = rotate_polygon(carpets[0].polygon, 90)
    first_bounds = first_rotated.bounds
    first_translated = translate_polygon(first_rotated, 0 - first_bounds[0], 0 - first_bounds[1])

    placed_first = PlacedCarpet(
        first_translated, 0 - first_bounds[0], 0 - first_bounds[1], 90,
        "1.dxf", "чёрный", "group_1", 1, 1
    )

    print(f"Первый ковёр размещён с границами: {placed_first.polygon.bounds}")

    # Теперь тестируем второй ковёр
    second_polygon = carpets[1].polygon
    sheet_width_mm, sheet_height_mm = 1400, 2000

    print(f"\nТестируем размещение второго ковра (оригинал):")
    print(f"Размеры: {second_polygon.bounds}")

    # Воспроизводим логику find_bottom_left_position с отладкой
    def debug_find_bottom_left_position(polygon, placed_polygons, sheet_width, sheet_height):
        """Версия find_bottom_left_position с детальными логами"""

        if not placed_polygons:
            print("Нет размещённых полигонов, возвращаем (0, 0)")
            return 0, 0

        bounds = polygon.bounds
        poly_width = bounds[2] - bounds[0]
        poly_height = bounds[3] - bounds[1]

        print(f"Ищем позицию для полигона размером {poly_width:.1f} x {poly_height:.1f} мм")

        # Быстрый поиск с большими шагами
        step = max(10.0, min(poly_width, poly_height) / 3)
        print(f"Шаг сетки: {step:.1f} мм")

        # X позиции (приоритет левой стороне)
        x_positions = []
        for x in range(0, int(sheet_width - poly_width), max(5, int(step))):
            x_positions.append(x)
        x_positions.sort()
        print(f"X позиции для тестирования: {x_positions[:15]}")

        best_y = None
        best_positions = []

        for test_x in x_positions[:15]:
            print(f"\n--- Тестируем X = {test_x} ---")

            # Формируем список Y позиций
            test_y_positions = [0]  # Всегда пробуем низ

            # Добавляем позиции на основе существующих полигонов
            for placed_poly in placed_polygons[:5]:  # Увеличено с 2 до 5
                other_bounds = placed_poly.polygon.bounds
                test_y_positions.append(other_bounds[3] + 2.0)  # Выше с зазором 2мм
                test_y_positions.append(other_bounds[1])  # Та же нижняя граница

            # Добавляем систематическую выборку Y
            step_size = max(25, int(poly_height / 8))
            print(f"Систематический шаг Y: {step_size} мм")
            for y_sample in range(0, int(sheet_height - poly_height + 1), step_size):
                test_y_positions.append(float(y_sample))

            # Убираем дубликаты и сортируем
            test_y_positions = sorted(set(test_y_positions))
            print(f"Y позиции для тестирования: {[f'{y:.1f}' for y in test_y_positions[:10]]}{'...' if len(test_y_positions) > 10 else ''}")

            # Тестируем позиции
            for test_y in test_y_positions:
                if test_y < 0 or test_y + poly_height > sheet_height:
                    continue

                # Быстрый тест
                x_offset = test_x - bounds[0]
                y_offset = test_y - bounds[1]
                test_polygon = translate_polygon(polygon, x_offset, y_offset)

                # Проверяем границы листа
                test_bounds = test_polygon.bounds
                if (test_bounds[0] < 0 or test_bounds[1] < 0 or
                    test_bounds[2] > sheet_width or test_bounds[3] > sheet_height):
                    continue

                # Проверяем коллизии
                collision = False
                for placed_poly in placed_polygons:
                    if check_collision(test_polygon, placed_poly.polygon, min_gap=2.0):
                        collision = True
                        break

                if not collision:
                    print(f"✅ Найдена валидная позиция: ({test_x}, {test_y})")
                    if best_y is None or test_y < best_y:
                        best_y = test_y
                        best_positions = [(test_x, test_y)]
                    elif test_y == best_y:
                        best_positions.append((test_x, test_y))
                    break  # Нашли позицию для этого X, переходим к следующему

        # Возвращаем самую левую позицию
        if best_positions:
            best_positions.sort()
            result = best_positions[0]
            print(f"\n🎯 Лучшая позиция: {result}")
            return result

        print(f"\n❌ Ни одной позиции не найдено")
        return None, None

    # Тестируем без поворота
    print(f"\n{'='*60}")
    print("ТЕСТ БЕЗ ПОВОРОТА (0°)")
    print(f"{'='*60}")
    result = debug_find_bottom_left_position(second_polygon, [placed_first], sheet_width_mm, sheet_height_mm)

    # Тестируем с поворотом на 90°
    print(f"\n{'='*60}")
    print("ТЕСТ С ПОВОРОТОМ 90°")
    print(f"{'='*60}")
    second_rotated = rotate_polygon(second_polygon, 90)
    result_90 = debug_find_bottom_left_position(second_rotated, [placed_first], sheet_width_mm, sheet_height_mm)

if __name__ == "__main__":
    debug_find_positions()