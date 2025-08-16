#!/usr/bin/env python3
"""
Детальная отладка трансформации SPLINE элементов.
"""

import ezdxf
import numpy as np
from layout_optimizer import parse_dxf_complete, apply_placement_transform
from shapely.geometry import Polygon

def debug_spline_transformation_detailed():
    """Детальная отладка трансформации SPLINE элементов."""
    print("=== ДЕТАЛЬНАЯ ОТЛАДКА SPLINE ТРАНСФОРМАЦИИ ===")
    
    # Исходный DXF файл
    source_dxf = "/home/sasha/proj/2025/eva_layout/dxf_samples/Лодка Азимут Эверест 385/2.dxf"
    
    print(f"📁 Анализируем файл: {source_dxf}")
    
    # Парсим исходный DXF
    with open(source_dxf, 'rb') as f:
        parsed_data = parse_dxf_complete(f, verbose=False)
    
    original_polygon = parsed_data['combined_polygon']
    print(f"📊 Combined polygon bounds: {original_polygon.bounds}")
    
    if parsed_data.get('real_spline_bounds'):
        spline_bounds = parsed_data['real_spline_bounds']
        print(f"📊 Real SPLINE bounds: {spline_bounds}")
    else:
        print("📊 Нет real_spline_bounds!")
        return
    
    # Параметры трансформации
    x_offset = -200
    y_offset = 150
    rotation_angle = 0
    
    print(f"\\n🔄 Имитация трансформации SPLINE:")
    print(f"  Трансформация: x_offset={x_offset}, y_offset={y_offset}, rotation={rotation_angle}°")
    
    # Берем первый SPLINE для отладки
    spline_entities = [e for e in parsed_data['original_entities'] if e['type'] == 'SPLINE']
    if not spline_entities:
        print("  ❌ Нет SPLINE элементов!")
        return
    
    first_spline = spline_entities[0]
    entity = first_spline['entity']
    control_points = entity.control_points
    
    if not control_points or len(control_points) == 0:
        print("  ❌ Нет контрольных точек!")
        return
    
    # Первая контрольная точка
    cp = control_points[0]
    if hasattr(cp, 'x') and hasattr(cp, 'y'):
        x, y = cp.x, cp.y
    elif len(cp) >= 2:
        x, y = float(cp[0]), float(cp[1])
    else:
        print("  ❌ Неизвестный формат контрольной точки!")
        return
    
    print(f"\\n📍 Первая контрольная точка SPLINE:")
    print(f"  Исходные координаты: ({x:.2f}, {y:.2f})")
    
    # Проверяем, какие bounds используются для нормализации
    if parsed_data.get('real_spline_bounds'):
        norm_bounds = parsed_data['real_spline_bounds']
        print(f"  🎯 Используемые bounds для нормализации: {norm_bounds}")
    else:
        norm_bounds = original_polygon.bounds
        print(f"  🎯 Используемые bounds для нормализации (fallback): {norm_bounds}")
    
    # Step 1: Normalize to origin
    x_norm = x - norm_bounds[0]
    y_norm = y - norm_bounds[1]
    print(f"  После нормализации: ({x_norm:.2f}, {y_norm:.2f})")
    
    # Step 2: Skip rotation (rotation_angle = 0)
    
    # Step 3: Apply final position
    x_final = x_norm + x_offset
    y_final = y_norm + y_offset
    print(f"  После трансформации: ({x_final:.2f}, {y_final:.2f})")
    
    # Ожидаемые координаты на основе apply_placement_transform
    expected_polygon = apply_placement_transform(original_polygon, x_offset, y_offset, rotation_angle)
    print(f"\\n📊 Ожидаемый результат apply_placement_transform:")
    print(f"  Expected polygon bounds: {expected_polygon.bounds}")
    
    # Вычисляем ожидаемую позицию точки
    orig_bounds = original_polygon.bounds
    # Нормализация относительно combined_polygon bounds
    x_norm_expected = x - orig_bounds[0]
    y_norm_expected = y - orig_bounds[1]
    x_final_expected = x_norm_expected + x_offset
    y_final_expected = y_norm_expected + y_offset
    
    print(f"  Ожидаемая позиция точки: ({x_final_expected:.2f}, {y_final_expected:.2f})")
    
    # Сравнение
    print(f"\\n🔍 СРАВНЕНИЕ:")
    print(f"  SPLINE трансформация: ({x_final:.2f}, {y_final:.2f})")
    print(f"  Ожидаемая позиция:   ({x_final_expected:.2f}, {y_final_expected:.2f})")
    
    diff_x = x_final - x_final_expected
    diff_y = y_final - y_final_expected
    print(f"  Разность: ({diff_x:.2f}, {diff_y:.2f})")
    
    if abs(diff_x) < 0.1 and abs(diff_y) < 0.1:
        print(f"  ✅ КООРДИНАТЫ СОВПАДАЮТ!")
    else:
        print(f"  ❌ КООРДИНАТЫ НЕ СОВПАДАЮТ!")
        
        # Анализируем причины
        if norm_bounds != orig_bounds:
            print(f"  💡 Причина: Разные bounds для нормализации!")
            print(f"     SPLINE bounds: {norm_bounds}")
            print(f"     Combined bounds: {orig_bounds}")
        else:
            print(f"  💡 Bounds одинаковые, проблема в другом!")

if __name__ == "__main__":
    print("🔍 Детальная отладка трансформации SPLINE элементов")
    print("=" * 60)
    
    debug_spline_transformation_detailed()
    
    print("\\n" + "=" * 60)
    print("✅ АНАЛИЗ ЗАВЕРШЕН")