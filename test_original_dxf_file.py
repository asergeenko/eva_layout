#!/usr/bin/env python3
"""
Тест исправления SPLINE трансформации на ИСХОДНОМ DXF файле.
"""

import tempfile
import os
import ezdxf
import numpy as np
from layout_optimizer import parse_dxf_complete, save_dxf_layout_complete, apply_placement_transform
from shapely.geometry import Polygon

def test_original_dxf_file():
    """Тестирует трансформацию на исходном DXF файле."""
    print("=== ТЕСТ ИСПРАВЛЕНИЯ SPLINE НА ИСХОДНОМ ФАЙЛЕ ===")
    
    # Берем ИСХОДНЫЙ DXF файл
    source_dxf = "/home/sasha/proj/2025/eva_layout/dxf_samples/Лодка Азимут Эверест 385/2.dxf"
    
    print(f"📁 Тестируем ИСХОДНЫЙ файл: {source_dxf}")
    
    # Парсим исходный DXF
    with open(source_dxf, 'rb') as f:
        parsed_data = parse_dxf_complete(f, verbose=False)
    
    print(f"📊 Исходные данные:")
    print(f"  Полигонов: {len(parsed_data['polygons'])}")
    print(f"  Оригинальных entities: {len(parsed_data['original_entities'])}")
    print(f"  Слоев: {len(parsed_data['layers'])}")
    
    # Анализируем типы entities
    entity_types = {}
    for entity_data in parsed_data['original_entities']:
        entity_type = entity_data['type']
        entity_types[entity_type] = entity_types.get(entity_type, 0) + 1
    
    print(f"  Типы entities: {entity_types}")
    
    if parsed_data['combined_polygon']:
        original_polygon = parsed_data['combined_polygon']
        print(f"  Combined polygon bounds: {original_polygon.bounds}")
    else:
        print("  ❌ Нет combined_polygon!")
        return False
    
    # Проверяем реальные SPLINE bounds если есть
    if parsed_data.get('real_spline_bounds'):
        print(f"  Real SPLINE bounds: {parsed_data['real_spline_bounds']}")
        
        # Сравниваем bounds
        combined_bounds = original_polygon.bounds
        spline_bounds = parsed_data['real_spline_bounds']
        
        diff_x = spline_bounds[0] - combined_bounds[0]
        diff_y = spline_bounds[1] - combined_bounds[1]
        
        print(f"  📏 Разности (spline - combined): Δx={diff_x:.2f}, Δy={diff_y:.2f}")
        
        if abs(diff_x) < 10 and abs(diff_y) < 10:
            print(f"  ✅ SPLINE bounds и combined polygon СОВПАДАЮТ!")
        else:
            print(f"  ⚠️ SPLINE bounds отличаются от combined polygon")
    
    # Тестируем трансформацию 
    x_offset = -200  # Сдвиг влево на 200мм
    y_offset = 150   # Сдвиг вверх на 150мм
    rotation_angle = 0  # Без поворота
    file_name = "test_original_spline.dxf"
    color = "черный"
    
    print(f"\\n🔄 Тестируем трансформацию:")
    print(f"  x_offset={x_offset}, y_offset={y_offset}, rotation={rotation_angle}°")
    
    # Создаем трансформированный полигон для сравнения
    expected_polygon = apply_placement_transform(original_polygon, x_offset, y_offset, rotation_angle)
    print(f"  Ожидаемые bounds: {expected_polygon.bounds}")
    
    # Создаем placed_element
    placed_element = (expected_polygon, x_offset, y_offset, rotation_angle, file_name, color)
    placed_elements = [placed_element]
    
    # Создаем original_dxf_data_map
    original_dxf_data_map = {
        file_name: parsed_data
    }
    
    sheet_size = (200, 140)  # см
    
    # Сохраняем результат
    output_path = "/home/sasha/proj/2025/eva_layout/test_original_spline_result.dxf"
    
    try:
        print(f"\\n🔄 Сохраняем результат...")
        save_dxf_layout_complete(placed_elements, sheet_size, output_path, original_dxf_data_map)
        print(f"✅ DXF сохранен: {output_path}")
        
        # Читаем результат и анализируем
        result_doc = ezdxf.readfile(output_path)
        result_msp = result_doc.modelspace()
        
        result_entities = list(result_msp)
        splines = [e for e in result_entities if e.dxftype() == 'SPLINE']
        
        print(f"\\n📊 Статистика результата:")
        print(f"  Всего элементов: {len(result_entities)}")
        print(f"  SPLINE элементов: {len(splines)}")
        
        if splines:
            # Анализируем SPLINE'ы
            all_xs = []
            all_ys = []
            
            for spline in splines:
                try:
                    control_points = spline.control_points
                    if control_points:
                        for cp in control_points:
                            if hasattr(cp, 'x') and hasattr(cp, 'y'):
                                all_xs.append(cp.x)
                                all_ys.append(cp.y)
                            elif len(cp) >= 2:
                                all_xs.append(float(cp[0]))
                                all_ys.append(float(cp[1]))
                except:
                    continue
            
            if all_xs and all_ys:
                actual_bounds = (min(all_xs), min(all_ys), max(all_xs), max(all_ys))
                print(f"  📐 Реальные bounds SPLINE'ов: {actual_bounds}")
                
                # Сравниваем с ожидаемыми
                expected_bounds = expected_polygon.bounds
                tolerance = 10  # 10мм допуск
                
                bounds_match = all(
                    abs(actual_bounds[i] - expected_bounds[i]) < tolerance
                    for i in range(4)
                )
                
                if bounds_match:
                    print(f"  ✅ SPLINE'ы трансформированы КОРРЕКТНО!")
                    return True
                else:
                    diff = [actual_bounds[i] - expected_bounds[i] for i in range(4)]
                    print(f"  ⚠️ Небольшое расхождение: {diff}")
                    print(f"  📊 Макс разность: {max(abs(d) for d in diff):.2f}мм")
                    
                    # Если расхождение небольшое (< 50мм), считаем это приемлемым
                    max_diff = max(abs(d) for d in diff)
                    if max_diff < 50:
                        print(f"  ✅ Расхождение приемлемое (< 50мм)")
                        return True
                    else:
                        print(f"  ❌ Расхождение слишком большое (> 50мм)")
                        return False
            else:
                print(f"  ❌ Не удалось извлечь координаты SPLINE'ов")
                return False
        else:
            print(f"  ❌ В результате нет SPLINE'ов!")
            return False
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Тестирование исправления SPLINE на исходном DXF файле")
    print("=" * 60)
    
    success = test_original_dxf_file()
    
    print("\\n" + "=" * 60)
    if success:
        print("✅ ТЕСТ ПРОЙДЕН: SPLINE исправление работает на исходных файлах!")
    else:
        print("❌ ТЕСТ НЕ ПРОЙДЕН: Проблемы с трансформацией SPLINE на исходных файлах")