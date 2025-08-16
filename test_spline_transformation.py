#!/usr/bin/env python3
"""
Тест трансформации SPLINE элементов в save_dxf_layout_complete.
"""

import tempfile
import os
import ezdxf
import numpy as np
from layout_optimizer import parse_dxf_complete, save_dxf_layout_complete
from shapely.geometry import Polygon

def test_spline_transformation():
    """Тестирует трансформацию SPLINE элементов."""
    print("=== ТЕСТ ТРАНСФОРМАЦИИ SPLINE ЭЛЕМЕНТОВ ===")
    
    # Берем реальный DXF файл с SPLINE'ами
    source_dxf = "/home/sasha/proj/2025/eva_layout/200_140_1_black.dxf"
    
    print(f"📁 Читаем исходный файл: {source_dxf}")
    
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
    
    if not parsed_data['original_entities']:
        print("❌ Нет оригинальных entities для трансформации!")
        return False
    
    # Создаем fake placed element для тестирования трансформации
    # Используем combined_polygon из parse_dxf_complete или создаем fake
    if parsed_data['combined_polygon']:
        original_polygon = parsed_data['combined_polygon']
        print(f"✅ Используем combined_polygon: {original_polygon.bounds}")
    else:
        # Создаем fake полигон
        original_polygon = Polygon([(1000, 0), (1500, 0), (1500, 500), (1000, 500)])
        print(f"⚠️ Создан fake полигон: {original_polygon.bounds}")
    
    # Параметры трансформации - сдвигаем полигон влево и вниз
    x_offset = -1000  # Сдвиг влево на 1000 мм
    y_offset = 100    # Сдвиг вверх на 100 мм  
    rotation_angle = 0  # Без поворота для простоты
    file_name = "test_spline.dxf"
    color = "черный"
    
    # Создаем трансформированный полигон (как должно быть)
    from layout_optimizer import apply_placement_transform
    expected_polygon = apply_placement_transform(original_polygon, x_offset, y_offset, rotation_angle)
    
    print(f"🎯 Ожидаемый результат:")
    print(f"  Исходный bounds: {original_polygon.bounds}")
    print(f"  Трансформация: x_offset={x_offset}, y_offset={y_offset}, rotation={rotation_angle}°")
    print(f"  Ожидаемый bounds: {expected_polygon.bounds}")
    
    # Создаем placed_element для save_dxf_layout_complete
    placed_element = (expected_polygon, x_offset, y_offset, rotation_angle, file_name, color)
    placed_elements = [placed_element]
    
    # Создаем original_dxf_data_map
    original_dxf_data_map = {
        file_name: parsed_data
    }
    
    sheet_size = (200, 140)  # см
    
    # Тестируем сохранение
    with tempfile.NamedTemporaryFile(suffix='.dxf', delete=False) as tmp_file:
        output_path = tmp_file.name
    
    try:
        print(f"\\n🔄 Применяем save_dxf_layout_complete...")
        save_dxf_layout_complete(placed_elements, sheet_size, output_path, original_dxf_data_map)
        
        print(f"✅ DXF сохранен: {output_path}")
        
        # Читаем результат и анализируем
        print(f"\\n📊 Анализ результата:")
        
        result_doc = ezdxf.readfile(output_path)
        result_msp = result_doc.modelspace()
        
        result_entities = list(result_msp)
        print(f"  Элементов в результате: {len(result_entities)}")
        
        # Анализируем типы результирующих entities
        result_types = {}
        for entity in result_entities:
            entity_type = entity.dxftype()
            result_types[entity_type] = result_types.get(entity_type, 0) + 1
        
        print(f"  Типы в результате: {result_types}")
        
        # Ищем трансформированные SPLINE'ы
        splines = [e for e in result_entities if e.dxftype() == 'SPLINE']
        print(f"  SPLINE'ов в результате: {len(splines)}")
        
        if splines:
            print(f"\\n🔍 Анализ трансформированных SPLINE'ов:")
            
            all_xs = []
            all_ys = []
            
            for i, spline in enumerate(splines[:5]):  # Первые 5 для примера
                layer = getattr(spline.dxf, 'layer', 'UNKNOWN')
                
                try:
                    control_points = spline.control_points
                    if control_points is not None and len(control_points) > 0:
                        # Извлекаем координаты
                        points = []
                        for cp in control_points:
                            if hasattr(cp, 'x') and hasattr(cp, 'y'):
                                points.append((cp.x, cp.y))
                            elif len(cp) >= 2:
                                points.append((float(cp[0]), float(cp[1])))
                        
                        if points:
                            xs = [p[0] for p in points]
                            ys = [p[1] for p in points]
                            bounds = (min(xs), min(ys), max(xs), max(ys))
                            
                            all_xs.extend(xs)
                            all_ys.extend(ys)
                            
                            print(f"    SPLINE {i+1} ({layer}): bounds={bounds}")
                
                except Exception as e:
                    print(f"    SPLINE {i+1}: ошибка анализа - {e}")
            
            if all_xs and all_ys:
                overall_bounds = (min(all_xs), min(all_ys), max(all_xs), max(all_ys))
                print(f"  📐 Общие bounds всех SPLINE'ов: {overall_bounds}")
                print(f"  📐 Ожидаемые bounds: {expected_polygon.bounds}")
                
                # Сравниваем результат
                expected_bounds = expected_polygon.bounds
                tolerance = 100  # 100мм допуск
                
                bounds_match = all(
                    abs(overall_bounds[i] - expected_bounds[i]) < tolerance
                    for i in range(4)
                )
                
                if bounds_match:
                    print(f"  ✅ SPLINE'ы трансформированы КОРРЕКТНО!")
                    return True
                else:
                    diff = [overall_bounds[i] - expected_bounds[i] for i in range(4)]
                    print(f"  ❌ SPLINE'ы трансформированы НЕПРАВИЛЬНО!")
                    print(f"  📊 Разности: {diff}")
                    return False
            else:
                print(f"  ❌ Не удалось извлечь координаты SPLINE'ов")
                return False
        else:
            print(f"  ❌ В результате нет SPLINE'ов!")
            return False
        
    finally:
        if os.path.exists(output_path):
            print(f"💾 Результат сохранен: {output_path}")
            # os.unlink(output_path)  # Оставляем для анализа

if __name__ == "__main__":
    print("🧪 Тестирование трансформации SPLINE элементов")
    print("=" * 60)
    
    success = test_spline_transformation()
    
    print("\\n" + "=" * 60)
    if success:
        print("✅ ТЕСТ ПРОЙДЕН: SPLINE элементы трансформируются корректно")
    else:
        print("❌ ТЕСТ НЕ ПРОЙДЕН: Проблемы с трансформацией SPLINE элементов")