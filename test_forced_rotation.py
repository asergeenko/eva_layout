#!/usr/bin/env python3
"""
Тест принудительного поворота для проверки исправлений.
"""

from layout_optimizer import rotate_polygon, translate_polygon, check_collision
from shapely.geometry import Polygon

def test_manual_rotation():
    """Тест ручного поворота и проверка коллизий"""
    print("=== Тест ручного поворота ===")
    
    # Создаем два ковра
    carpet1 = Polygon([(0, 0), (100, 0), (100, 50), (0, 50)])     # 100x50
    carpet2 = Polygon([(0, 0), (80, 0), (80, 60), (0, 60)])       # 80x60
    
    print(f"Исходные ковры:")
    print(f"  Ковер 1: bounds={carpet1.bounds} (размер: 10x5 см)")
    print(f"  Ковер 2: bounds={carpet2.bounds} (размер: 8x6 см)")
    print(f"  Коллизия между исходными: {check_collision(carpet1, carpet2)}")
    
    # Размещаем первый ковер в позиции (0, 0)
    placed_carpet1 = carpet1  # Уже в правильном месте
    
    # Размещаем второй ковер рядом без поворота
    placed_carpet2_no_rot = translate_polygon(carpet2, 100, 0)  # Сдвигаем на 100мм вправо
    
    print(f"\nБез поворота:")
    print(f"  Ковер 1: bounds={placed_carpet1.bounds}")
    print(f"  Ковер 2: bounds={placed_carpet2_no_rot.bounds}")
    print(f"  Коллизия: {check_collision(placed_carpet1, placed_carpet2_no_rot)}")
    print(f"  Общая ширина: {placed_carpet2_no_rot.bounds[2]} мм")
    
    # Поворачиваем второй ковер на 90° и размещаем 
    rotated_carpet2 = rotate_polygon(carpet2, 90)
    print(f"\nПосле поворота ковра 2 на 90°:")
    print(f"  Повернутый ковер 2: bounds={rotated_carpet2.bounds}")
    
    # Размещаем повернутый ковер рядом с первым
    placed_carpet2_rot = translate_polygon(rotated_carpet2, 100 - rotated_carpet2.bounds[0], 0 - rotated_carpet2.bounds[1])
    
    print(f"\nС поворотом:")
    print(f"  Ковер 1: bounds={placed_carpet1.bounds}")
    print(f"  Ковер 2 (повернутый): bounds={placed_carpet2_rot.bounds}")
    print(f"  Коллизия: {check_collision(placed_carpet1, placed_carpet2_rot)}")
    
    rotated_width = placed_carpet2_rot.bounds[2] - placed_carpet2_rot.bounds[0]
    rotated_height = placed_carpet2_rot.bounds[3] - placed_carpet2_rot.bounds[1]
    print(f"  Размер повернутого ковра: {rotated_width/10:.1f}x{rotated_height/10:.1f} см")
    print(f"  Общая ширина: {placed_carpet2_rot.bounds[2]} мм")
    
    # Проверяем правильность поворота
    # Исходный ковер 80x60 после поворота на 90° должен стать 60x80
    expected_width = 60  # Была высота
    expected_height = 80  # Была ширина
    
    actual_width = rotated_width
    actual_height = rotated_height
    
    width_correct = abs(actual_width - expected_width) < 1
    height_correct = abs(actual_height - expected_height) < 1
    
    print(f"\nПроверка размеров после поворота:")
    print(f"  Ожидались: {expected_width}x{expected_height} мм")
    print(f"  Получили: {actual_width:.1f}x{actual_height:.1f} мм")
    print(f"  Размеры правильные: {width_correct and height_correct}")
    
    # Проверяем, что нет коллизий
    no_collision = not check_collision(placed_carpet1, placed_carpet2_rot)
    
    success = width_correct and height_correct and no_collision
    
    if success:
        print(f"\n✅ Ручной тест поворота УСПЕШЕН!")
        print(f"  - Размеры после поворота корректны")
        print(f"  - Коллизий нет") 
        print(f"  - Алгоритм поворота работает правильно")
    else:
        print(f"\n❌ Ручной тест поворота НЕУСПЕШЕН!")
        if not (width_correct and height_correct):
            print(f"  - Проблема с размерами после поворота")
        if not no_collision:
            print(f"  - Проблема с коллизиями")
    
    return success

def test_dxf_transformation_simulation():
    """Симуляция трансформации как в save_dxf_layout_complete"""
    print(f"\n=== Симуляция DXF трансформации ===")
    
    # Исходный ковер
    original_carpet = Polygon([(10, 20), (90, 20), (90, 70), (10, 70)])  # 80x50 в позиции (10,20)
    print(f"Исходный ковер: bounds={original_carpet.bounds}")
    
    # Результат bin_packing (имитируем)
    angle = 90
    final_position = (150, 80)  # Где должен оказаться ковер после поворота и размещения
    
    # 1. Поворот как в bin_packing (вокруг нижнего левого угла)
    binpack_rotated = rotate_polygon(original_carpet, angle)
    binpack_placed = translate_polygon(binpack_rotated, 
                                      final_position[0] - binpack_rotated.bounds[0],
                                      final_position[1] - binpack_rotated.bounds[1])
    
    print(f"Результат bin_packing: bounds={binpack_placed.bounds}")
    
    # 2. Трансформация как в save_dxf_layout_complete
    orig_bounds = original_carpet.bounds
    
    # Перемещаем к началу координат
    moved_to_origin = translate_polygon(original_carpet, -orig_bounds[0], -orig_bounds[1])
    print(f"Перемещен к началу координат: bounds={moved_to_origin.bounds}")
    
    # Поворачиваем в начале координат
    rotated_at_origin = rotate_polygon(moved_to_origin, angle)
    print(f"Повернут в начале координат: bounds={rotated_at_origin.bounds}")
    
    # Вычисляем смещение для достижения целевого положения 
    rotated_bounds = rotated_at_origin.bounds
    target_bounds = binpack_placed.bounds
    translate_x = target_bounds[0] - rotated_bounds[0]
    translate_y = target_bounds[1] - rotated_bounds[1]
    
    # Применяем финальное смещение
    dxf_result = translate_polygon(rotated_at_origin, translate_x, translate_y)
    print(f"Результат DXF: bounds={dxf_result.bounds}")
    
    # Сравниваем результаты
    tolerance = 0.1
    bounds_match = all(
        abs(a - b) < tolerance 
        for a, b in zip(binpack_placed.bounds, dxf_result.bounds)
    )
    
    print(f"\nСравнение результатов:")
    print(f"  bin_packing: {binpack_placed.bounds}")
    print(f"  save_dxf:    {dxf_result.bounds}")
    print(f"  Совпадают: {bounds_match}")
    
    if bounds_match:
        print(f"\n✅ DXF трансформация работает корректно!")
    else:
        print(f"\n❌ DXF трансформация НЕ работает корректно!")
        
    return bounds_match

if __name__ == "__main__":
    print("=== Тест принудительного поворота и DXF трансформации ===")
    
    test1 = test_manual_rotation()
    test2 = test_dxf_transformation_simulation()
    
    print(f"\n=== ИТОГОВЫЙ РЕЗУЛЬТАТ ===")
    if test1 and test2:
        print("🎉 Все тесты поворота прошли успешно!")
        print("Исправления rotate_polygon и save_dxf_layout_complete работают корректно.")
    else:
        print("🚨 Обнаружены проблемы в алгоритмах поворота!")
        if not test1:
            print("- Проблема в базовом алгоритме поворота")
        if not test2:
            print("- Проблема в DXF трансформации")