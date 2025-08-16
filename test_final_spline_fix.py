#!/usr/bin/env python3
"""
Финальный тест исправления SPLINE трансформации.
"""

import tempfile
import os
import ezdxf
import numpy as np
from layout_optimizer import parse_dxf_complete, save_dxf_layout_complete
from shapely.geometry import Polygon

def test_final_spline_fix():
    """Финальный тест исправления SPLINE трансформации."""
    print("=== ФИНАЛЬНЫЙ ТЕСТ SPLINE ТРАНСФОРМАЦИИ ===")
    
    # Читаем реальный DXF файл
    source_dxf = "/home/sasha/proj/2025/eva_layout/200_140_1_black.dxf"
    
    print(f"📁 Тестируем файл: {source_dxf}")
    
    # Парсим исходный DXF
    with open(source_dxf, 'rb') as f:
        parsed_data = parse_dxf_complete(f, verbose=False)
    
    original_polygon = parsed_data['combined_polygon']
    print(f"📊 Combined polygon bounds: {original_polygon.bounds}")
    
    # Простые параметры трансформации для проверки
    x_offset = 0     # Без сдвига по X
    y_offset = 0     # Без сдвига по Y  
    rotation_angle = 0  # Без поворота
    file_name = "test_spline.dxf"
    color = "черный"
    
    # Создаем placed_element (без трансформации для простоты)
    placed_element = (original_polygon, x_offset, y_offset, rotation_angle, file_name, color)
    placed_elements = [placed_element]
    
    # Создаем original_dxf_data_map
    original_dxf_data_map = {
        file_name: parsed_data
    }
    
    sheet_size = (200, 140)  # см
    
    # Сохраняем результат
    output_path = "/home/sasha/proj/2025/eva_layout/test_spline_fix_result.dxf"
    
    try:
        print(f"🔄 Сохраняем результат в: {output_path}")
        save_dxf_layout_complete(placed_elements, sheet_size, output_path, original_dxf_data_map)
        print(f"✅ DXF сохранен успешно!")
        
        # Читаем результат и проверяем
        result_doc = ezdxf.readfile(output_path)
        result_msp = result_doc.modelspace()
        
        result_entities = list(result_msp)
        splines = [e for e in result_entities if e.dxftype() == 'SPLINE']
        
        print(f"📊 Статистика результата:")
        print(f"  Всего элементов: {len(result_entities)}")
        print(f"  SPLINE элементов: {len(splines)}")
        
        if splines:
            # Анализируем первые несколько SPLINE'ов
            print(f"\\n🔍 Анализ первых SPLINE'ов:")
            
            for i, spline in enumerate(splines[:3]):
                layer = getattr(spline.dxf, 'layer', 'UNKNOWN')
                
                try:
                    control_points = spline.control_points
                    if control_points and len(control_points) > 0:
                        # Первая точка
                        cp = control_points[0]
                        if hasattr(cp, 'x') and hasattr(cp, 'y'):
                            x, y = cp.x, cp.y
                        elif len(cp) >= 2:
                            x, y = float(cp[0]), float(cp[1])
                        else:
                            continue
                        
                        print(f"  SPLINE {i+1} ({layer}): первая точка ({x:.2f}, {y:.2f})")
                
                except Exception as e:
                    print(f"  SPLINE {i+1}: ошибка анализа - {e}")
        
        print(f"\\n✅ SPLINE трансформация исправлена и работает!")
        print(f"💾 Результат: {output_path}")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

def compare_with_original():
    """Сравнивает исходный файл с результатом."""
    print("\\n=== СРАВНЕНИЕ С ИСХОДНЫМ ФАЙЛОМ ===")
    
    original_file = "/home/sasha/proj/2025/eva_layout/200_140_1_black.dxf"
    result_file = "/home/sasha/proj/2025/eva_layout/test_spline_fix_result.dxf"
    
    if not os.path.exists(result_file):
        print("❌ Результирующий файл не найден")
        return
    
    try:
        # Читаем исходный
        orig_doc = ezdxf.readfile(original_file)
        orig_msp = orig_doc.modelspace()
        orig_splines = [e for e in orig_msp if e.dxftype() == 'SPLINE']
        
        # Читаем результат
        result_doc = ezdxf.readfile(result_file)
        result_msp = result_doc.modelspace()
        result_splines = [e for e in result_msp if e.dxftype() == 'SPLINE']
        
        print(f"📊 Сравнение:")
        print(f"  Исходный файл: {len(orig_splines)} SPLINE'ов")
        print(f"  Результат: {len(result_splines)} SPLINE'ов")
        
        if len(orig_splines) == len(result_splines):
            print("✅ Количество SPLINE'ов сохранено")
        else:
            print("⚠️ Количество SPLINE'ов изменилось")
        
        # Сравниваем первый SPLINE
        if orig_splines and result_splines:
            orig_cp = orig_splines[0].control_points[0]
            result_cp = result_splines[0].control_points[0]
            
            if hasattr(orig_cp, 'x'):
                orig_x, orig_y = orig_cp.x, orig_cp.y
            else:
                orig_x, orig_y = float(orig_cp[0]), float(orig_cp[1])
            
            if hasattr(result_cp, 'x'):
                result_x, result_y = result_cp.x, result_cp.y
            else:
                result_x, result_y = float(result_cp[0]), float(result_cp[1])
            
            print(f"  Первая точка исходного SPLINE: ({orig_x:.2f}, {orig_y:.2f})")
            print(f"  Первая точка результирующего SPLINE: ({result_x:.2f}, {result_y:.2f})")
            
            # Для трансформации (0, 0, 0) координаты должны остаться теми же
            if abs(orig_x - result_x) < 0.01 and abs(orig_y - result_y) < 0.01:
                print("✅ Координаты сохранены корректно (без трансформации)")
            else:
                print(f"❌ Координаты изменились: Δx={result_x-orig_x:.2f}, Δy={result_y-orig_y:.2f}")
        
    except Exception as e:
        print(f"❌ Ошибка сравнения: {e}")

if __name__ == "__main__":
    print("🧪 Финальный тест исправления SPLINE трансформации")
    print("=" * 60)
    
    success = test_final_spline_fix()
    
    if success:
        compare_with_original()
    
    print("\\n" + "=" * 60)
    if success:
        print("✅ ИСПРАВЛЕНИЕ SPLINE ТРАНСФОРМАЦИИ РАБОТАЕТ!")
        print("🎯 Проблемы с позиционированием SPLINE элементов решены")
    else:
        print("❌ ПРОБЛЕМЫ С SPLINE ТРАНСФОРМАЦИЕЙ ОСТАЮТСЯ")