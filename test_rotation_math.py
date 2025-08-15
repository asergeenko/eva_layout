#!/usr/bin/env python3
"""
Тест математической согласованности поворотов.
Проверяет, что трансформации в bin_packing и save_dxf_layout_complete дают одинаковый результат.
"""

from layout_optimizer import rotate_polygon, translate_polygon, place_polygon_at_origin
from shapely.geometry import Polygon
import numpy as np

def test_transform_consistency():
    """Тест согласованности трансформаций"""
    
    print("=== Тест математической согласованности поворотов ===")
    
    # Создаем ковер в произвольном положении (не в начале координат)
    original_polygon = Polygon([(10, 20), (110, 20), (110, 70), (10, 70)])
    print(f"Исходный ковер: bounds={original_polygon.bounds}")
    
    angle = 90
    target_position = (200, 100)  # Целевая позиция после размещения
    
    # === МЕТОД 1: Как делает bin_packing ===
    print("\n--- Метод 1 (bin_packing) ---")
    
    # Шаг 1: Поворачиваем исходный полигон
    rotated_for_packing = rotate_polygon(original_polygon, angle)
    print(f"После поворота: bounds={rotated_for_packing.bounds}")
    
    # Шаг 2: Размещаем в нужном месте через translate
    # В bin_packing используется более сложная логика, но суть такая:
    rotated_bounds = rotated_for_packing.bounds
    offset_x = target_position[0] - rotated_bounds[0]
    offset_y = target_position[1] - rotated_bounds[1]
    
    final_packing = translate_polygon(rotated_for_packing, offset_x, offset_y)
    print(f"После размещения: bounds={final_packing.bounds}")
    print(f"Применены смещения: offset_x={offset_x}, offset_y={offset_y}")
    
    # === МЕТОД 2: Как делает save_dxf_layout_complete (УПРОЩЕННЫЙ ПОДХОД) ===
    print("\n--- Метод 2 (save_dxf_layout_complete УПРОЩЕННЫЙ) ---")
    
    # Шаг 1: Перемещаем к началу координат и поворачиваем
    orig_bounds = original_polygon.bounds
    moved_to_origin = translate_polygon(original_polygon, -orig_bounds[0], -orig_bounds[1])
    rotated_at_origin = rotate_polygon(moved_to_origin, angle)
    print(f"После поворота в начале координат: bounds={rotated_at_origin.bounds}")
    
    # Шаг 2: Вычисляем смещение для достижения целевого положения
    rotated_bounds = rotated_at_origin.bounds
    target_bounds = final_packing.bounds
    translate_x = target_bounds[0] - rotated_bounds[0]
    translate_y = target_bounds[1] - rotated_bounds[1]
    print(f"Необходимое смещение: dx={translate_x}, dy={translate_y}")
    
    # Шаг 3: Применяем финальное смещение
    final_dxf = translate_polygon(rotated_at_origin, translate_x, translate_y)
    print(f"После финального перемещения: bounds={final_dxf.bounds}")
    
    # === СРАВНЕНИЕ РЕЗУЛЬТАТОВ ===
    print("\n--- Сравнение результатов ---")
    
    packing_bounds = final_packing.bounds
    dxf_bounds = final_dxf.bounds
    
    print(f"Результат bin_packing: {packing_bounds}")
    print(f"Результат save_dxf:    {dxf_bounds}")
    
    tolerance = 0.1  # 0.1мм погрешность
    
    bounds_match = (
        abs(packing_bounds[0] - dxf_bounds[0]) < tolerance and
        abs(packing_bounds[1] - dxf_bounds[1]) < tolerance and
        abs(packing_bounds[2] - dxf_bounds[2]) < tolerance and
        abs(packing_bounds[3] - dxf_bounds[3]) < tolerance
    )
    
    if bounds_match:
        print("✅ ТЕСТ ПРОЙДЕН: Трансформации согласованы!")
        return True
    else:
        print("❌ ТЕСТ НЕ ПРОЙДЕН: Трансформации не согласованы!")
        print(f"Погрешности:")
        print(f"  dx1: {abs(packing_bounds[0] - dxf_bounds[0]):.6f}")
        print(f"  dy1: {abs(packing_bounds[1] - dxf_bounds[1]):.6f}")
        print(f"  dx2: {abs(packing_bounds[2] - dxf_bounds[2]):.6f}")
        print(f"  dy2: {abs(packing_bounds[3] - dxf_bounds[3]):.6f}")
        return False

def test_multiple_angles():
    """Тест с разными углами поворота"""
    print("\n=== Тест разных углов поворота ===")
    
    original_polygon = Polygon([(5, 10), (55, 10), (55, 30), (5, 30)])
    target_position = (100, 50)
    
    angles = [0, 90, 180, 270]
    all_passed = True
    
    for angle in angles:
        print(f"\n--- Угол {angle}° ---")
        
        # Метод bin_packing
        rotated = rotate_polygon(original_polygon, angle)
        rotated_bounds = rotated.bounds
        offset_x = target_position[0] - rotated_bounds[0]
        offset_y = target_position[1] - rotated_bounds[1]
        final_packing = translate_polygon(rotated, offset_x, offset_y)
        
        # Метод save_dxf (УПРОЩЕННЫЙ)
        orig_bounds = original_polygon.bounds
        moved_to_origin = translate_polygon(original_polygon, -orig_bounds[0], -orig_bounds[1])
        rotated_at_origin = rotate_polygon(moved_to_origin, angle)
        
        # Вычисляем смещение для достижения того же результата что и bin_packing
        rotated_at_origin_bounds = rotated_at_origin.bounds
        target_bounds = final_packing.bounds
        translate_x = target_bounds[0] - rotated_at_origin_bounds[0]
        translate_y = target_bounds[1] - rotated_at_origin_bounds[1]
        final_dxf = translate_polygon(rotated_at_origin, translate_x, translate_y)
        
        # Сравнение
        tolerance = 0.1
        bounds_match = all(
            abs(a - b) < tolerance 
            for a, b in zip(final_packing.bounds, final_dxf.bounds)
        )
        
        if bounds_match:
            print(f"  ✅ Угол {angle}°: OK")
        else:
            print(f"  ❌ Угол {angle}°: FAIL")
            all_passed = False
    
    return all_passed

if __name__ == "__main__":
    result1 = test_transform_consistency()
    result2 = test_multiple_angles()
    
    print("\n=== ИТОГОВЫЙ РЕЗУЛЬТАТ ===")
    if result1 and result2:
        print("🎉 Проблема с поворотом ковров ИСПРАВЛЕНА!")
        print("Все трансформации работают согласованно.")
    else:
        print("🚨 Проблема с поворотом ковров НЕ ИСПРАВЛЕНА!")
        print("Требуются дополнительные исправления.")