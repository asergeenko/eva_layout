#!/usr/bin/env python3
"""
Проверка трансформации всех SPLINE элементов.
"""

import tempfile
import os
import ezdxf
import numpy as np
from layout_optimizer import parse_dxf_complete, save_dxf_layout_complete, apply_placement_transform
from shapely.geometry import Polygon

def verify_all_splines_transformation():
    """Проверяет трансформацию всех SPLINE элементов."""
    print("=== ПРОВЕРКА ТРАНСФОРМАЦИИ ВСЕХ SPLINE ЭЛЕМЕНТОВ ===")
    
    # Исходный DXF файл
    source_dxf = "/home/sasha/proj/2025/eva_layout/dxf_samples/Лодка Азимут Эверест 385/2.dxf"
    
    # Парсим исходный DXF
    with open(source_dxf, 'rb') as f:
        parsed_data = parse_dxf_complete(f, verbose=False)
    
    original_polygon = parsed_data['combined_polygon']
    print(f"📊 Combined polygon bounds: {original_polygon.bounds}")
    
    spline_bounds = parsed_data['real_spline_bounds']
    print(f"📊 Real SPLINE bounds: {spline_bounds}")
    
    # Параметры трансформации
    x_offset = -200
    y_offset = 150
    rotation_angle = 0
    file_name = "test_verify.dxf"
    color = "черный"
    
    print(f"\\n🔄 Трансформация: x_offset={x_offset}, y_offset={y_offset}, rotation={rotation_angle}°")
    
    # Создаем ожидаемый результат
    expected_polygon = apply_placement_transform(original_polygon, x_offset, y_offset, rotation_angle)
    expected_bounds = expected_polygon.bounds
    print(f"📊 Ожидаемые bounds: {expected_bounds}")
    
    # Вычисляем ожидаемые bounds всех SPLINE элементов вручную
    spline_entities = [e for e in parsed_data['original_entities'] if e['type'] == 'SPLINE']
    print(f"📊 SPLINE элементов: {len(spline_entities)}")
    
    # Трансформируем все контрольные точки вручную
    expected_xs = []
    expected_ys = []
    
    for spline_data in spline_entities:
        entity = spline_data['entity']
        control_points = entity.control_points
        
        if not control_points:
            continue
            
        for cp in control_points:
            if hasattr(cp, 'x') and hasattr(cp, 'y'):
                x, y = cp.x, cp.y
            elif len(cp) >= 2:
                x, y = float(cp[0]), float(cp[1])
            else:
                continue
            
            # Применяем ту же трансформацию что и в коде
            x_norm = x - spline_bounds[0]
            y_norm = y - spline_bounds[1]
            x_final = x_norm + x_offset
            y_final = y_norm + y_offset
            
            expected_xs.append(x_final)
            expected_ys.append(y_final)
    
    if expected_xs and expected_ys:
        manual_expected_bounds = (min(expected_xs), min(expected_ys), max(expected_xs), max(expected_ys))
        print(f"📊 Ожидаемые bounds (вручную): {manual_expected_bounds}")
        
        # Сравниваем с apply_placement_transform
        diff = [manual_expected_bounds[i] - expected_bounds[i] for i in range(4)]
        max_diff = max(abs(d) for d in diff)
        print(f"📊 Разность с apply_placement_transform: {diff} (макс: {max_diff:.2f})")
        
        if max_diff > 10:
            print(f"  ⚠️ БОЛЬШАЯ разность между методами!")
        else:
            print(f"  ✅ Методы дают похожий результат")
    
    # Теперь проверяем реальный результат save_dxf_layout_complete
    placed_element = (expected_polygon, x_offset, y_offset, rotation_angle, file_name, color)
    placed_elements = [placed_element]
    
    original_dxf_data_map = {
        file_name: parsed_data
    }
    
    sheet_size = (200, 140)
    
    with tempfile.NamedTemporaryFile(suffix='.dxf', delete=False) as tmp_file:
        output_path = tmp_file.name
    
    try:
        save_dxf_layout_complete(placed_elements, sheet_size, output_path, original_dxf_data_map)
        
        # Читаем результат
        result_doc = ezdxf.readfile(output_path)
        result_msp = result_doc.modelspace()
        
        splines = [e for e in result_msp if e.dxftype() == 'SPLINE']
        print(f"\\n📊 Результат save_dxf_layout_complete:")
        print(f"  SPLINE элементов в результате: {len(splines)}")
        
        if splines:
            # Извлекаем bounds
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
                except:
                    continue
            
            if actual_xs and actual_ys:
                actual_bounds = (min(actual_xs), min(actual_ys), max(actual_xs), max(actual_ys))
                print(f"  Реальные bounds: {actual_bounds}")
                
                # Сравниваем с ожидаемыми (ручной расчет)
                diff_manual = [actual_bounds[i] - manual_expected_bounds[i] for i in range(4)]
                max_diff_manual = max(abs(d) for d in diff_manual)
                print(f"  Разность с ожидаемыми (ручной расчет): {diff_manual}")
                print(f"  Максимальная разность: {max_diff_manual:.2f}мм")
                
                if max_diff_manual < 10:
                    print(f"  ✅ SPLINE'ы трансформированы КОРРЕКТНО!")
                    return True
                else:
                    print(f"  ❌ SPLINE'ы трансформированы НЕКОРРЕКТНО!")
                    
                    # Проверим, может ли проблема быть в sheet boundary
                    if actual_bounds[0] == 0.0 or actual_bounds[1] == 0.0:
                        print(f"  💡 Возможная причина: элементы обрезаны sheet boundary")
                    
                    return False
        else:
            print(f"  ❌ Нет SPLINE элементов в результате!")
            return False
    
    finally:
        if os.path.exists(output_path):
            os.unlink(output_path)

if __name__ == "__main__":
    print("🧪 Проверка трансформации всех SPLINE элементов")
    print("=" * 60)
    
    success = verify_all_splines_transformation()
    
    print("\\n" + "=" * 60)
    if success:
        print("✅ ВСЕ SPLINE ЭЛЕМЕНТЫ ТРАНСФОРМИРОВАНЫ КОРРЕКТНО!")
    else:
        print("❌ ПРОБЛЕМЫ С ТРАНСФОРМАЦИЕЙ SPLINE ЭЛЕМЕНТОВ")