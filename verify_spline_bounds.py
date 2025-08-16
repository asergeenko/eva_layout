#!/usr/bin/env python3
"""
Проверка bounds трансформированных SPLINE элементов.
"""

import tempfile
import os
import ezdxf
import numpy as np
from layout_optimizer import parse_dxf_complete, save_dxf_layout_complete, apply_placement_transform
from shapely.geometry import Polygon

def verify_spline_bounds():
    """Проверяет bounds трансформированных SPLINE элементов."""
    print("=== ПРОВЕРКА BOUNDS ТРАНСФОРМИРОВАННЫХ SPLINE ===")
    
    # Берем реальный DXF файл с SPLINE'ами
    source_dxf = "/home/sasha/proj/2025/eva_layout/200_140_1_black.dxf"
    
    # Парсим исходный DXF
    with open(source_dxf, 'rb') as f:
        parsed_data = parse_dxf_complete(f, verbose=False)
    
    original_polygon = parsed_data['combined_polygon']
    orig_bounds = original_polygon.bounds
    
    print(f"📊 Исходные данные:")
    print(f"  Combined polygon bounds: {orig_bounds}")
    
    # Параметры трансформации
    x_offset = -1000
    y_offset = 100
    rotation_angle = 0
    
    print(f"  Трансформация: x_offset={x_offset}, y_offset={y_offset}")
    
    # Анализируем все SPLINE элементы вручную
    spline_entities = [e for e in parsed_data['original_entities'] if e['type'] == 'SPLINE']
    print(f"  SPLINE'ов: {len(spline_entities)}")
    
    # Вычисляем ожидаемые bounds всех SPLINE'ов после трансформации
    expected_xs = []
    expected_ys = []
    
    for spline_data in spline_entities:
        entity = spline_data['entity']
        control_points = entity.control_points
        
        if not control_points:
            continue
            
        for cp in control_points:
            # Извлекаем координаты
            if hasattr(cp, 'x') and hasattr(cp, 'y'):
                x, y = cp.x, cp.y
            elif len(cp) >= 2:
                x, y = float(cp[0]), float(cp[1])
            else:
                continue
            
            # Применяем трансформацию
            # Step 1: Normalize to origin
            x_norm = x - orig_bounds[0]
            y_norm = y - orig_bounds[1]
            
            # Step 2: Skip rotation (rotation_angle = 0)
            
            # Step 3: Apply final position
            x_final = x_norm + x_offset
            y_final = y_norm + y_offset
            
            expected_xs.append(x_final)
            expected_ys.append(y_final)
    
    if expected_xs and expected_ys:
        expected_bounds = (min(expected_xs), min(expected_ys), max(expected_xs), max(expected_ys))
        print(f"  📐 Ожидаемые bounds ВСЕХ SPLINE'ов: {expected_bounds}")
    else:
        print(f"  ❌ Не удалось вычислить ожидаемые bounds")
        return
    
    # Теперь проверим реальный результат
    file_name = "test_spline.dxf"
    color = "черный"
    
    # Создаем трансформированный полигон для save_dxf_layout_complete
    expected_polygon_for_saving = apply_placement_transform(original_polygon, x_offset, y_offset, rotation_angle)
    placed_element = (expected_polygon_for_saving, x_offset, y_offset, rotation_angle, file_name, color)
    placed_elements = [placed_element]
    
    # Создаем original_dxf_data_map
    original_dxf_data_map = {
        file_name: parsed_data
    }
    
    sheet_size = (200, 140)  # см
    
    # Сохраняем
    with tempfile.NamedTemporaryFile(suffix='.dxf', delete=False) as tmp_file:
        output_path = tmp_file.name
    
    try:
        save_dxf_layout_complete(placed_elements, sheet_size, output_path, original_dxf_data_map)
        print(f"✅ DXF сохранен: {output_path}")
        
        # Читаем результат и анализируем реальные bounds
        result_doc = ezdxf.readfile(output_path)
        result_msp = result_doc.modelspace()
        
        # Ищем SPLINE'ы в результате
        splines = [e for e in result_msp if e.dxftype() == 'SPLINE']
        
        actual_xs = []
        actual_ys = []
        
        for spline in splines:
            try:
                control_points = spline.control_points
                if control_points:
                    for cp in control_points:
                        if hasattr(cp, 'x') and hasattr(cp, 'y'):
                            actual_xs.append(cp.x)
                            actual_ys.append(cp.y)
                        elif len(cp) >= 2:
                            actual_xs.append(float(cp[0]))
                            actual_ys.append(float(cp[1]))
            except Exception as e:
                print(f"    Ошибка анализа SPLINE: {e}")
        
        if actual_xs and actual_ys:
            actual_bounds = (min(actual_xs), min(actual_ys), max(actual_xs), max(actual_ys))
            print(f"  📐 Реальные bounds ВСЕХ SPLINE'ов: {actual_bounds}")
            
            # Сравниваем
            tolerance = 1.0  # 1мм допуск
            bounds_match = all(
                abs(actual_bounds[i] - expected_bounds[i]) < tolerance
                for i in range(4)
            )
            
            if bounds_match:
                print(f"  ✅ BOUNDS СОВПАДАЮТ! SPLINE'ы трансформированы КОРРЕКТНО!")
                return True
            else:
                diff = [actual_bounds[i] - expected_bounds[i] for i in range(4)]
                print(f"  ❌ BOUNDS НЕ СОВПАДАЮТ!")
                print(f"  📊 Разности: {diff}")
                print(f"  📊 Макс разность: {max(abs(d) for d in diff):.2f}")
                return False
        else:
            print(f"  ❌ Не удалось извлечь реальные bounds")
            return False
        
    finally:
        if os.path.exists(output_path):
            print(f"💾 Результат сохранен: {output_path}")

if __name__ == "__main__":
    success = verify_spline_bounds()
    print(f"\n{'✅ ТЕСТ ПРОЙДЕН' if success else '❌ ТЕСТ НЕ ПРОЙДЕН'}")