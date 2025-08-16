#!/usr/bin/env python3
"""
Тест полного процесса раскроя с исходными файлами для проверки исправлений SPLINE.
"""

import tempfile
import os
import sys
import time
from layout_optimizer import (
    parse_dxf_complete, 
    bin_packing, 
    save_dxf_layout_complete
)

def test_full_layout_process():
    """Тестирует полный процесс раскроя с исходными файлами."""
    print("=== ТЕСТ ПОЛНОГО ПРОЦЕССА РАСКРОЯ ===")
    
    # Файлы, которые видны на visualization.png
    test_files = [
        "/home/sasha/proj/2025/eva_layout/dxf_samples/Лодка Азимут Эверест 385/2.dxf",
        "/home/sasha/proj/2025/eva_layout/dxf_samples/Лодка АГУЛ 270/2.dxf", 
        "/home/sasha/proj/2025/eva_layout/dxf_samples/TOYOTA COROLLA VERSO/2.dxf",
        "/home/sasha/proj/2025/eva_layout/dxf_samples/ДЕКА KUGOO M4 PRO JILONG/1.dxf"
    ]
    
    print(f"📁 Тестируем файлы:")
    for i, file_path in enumerate(test_files, 1):
        print(f"  {i}. {os.path.basename(os.path.dirname(file_path))}/{os.path.basename(file_path)}")
    
    # Проверяем, что файлы существуют
    existing_files = []
    for file_path in test_files:
        if os.path.exists(file_path):
            existing_files.append(file_path)
            print(f"  ✅ {os.path.basename(file_path)} - найден")
        else:
            print(f"  ❌ {os.path.basename(file_path)} - НЕ найден")
    
    if not existing_files:
        print("❌ Нет доступных файлов для тестирования!")
        return False
    
    print(f"\\n📊 Используем {len(existing_files)} файлов для раскроя")
    
    # Парсим файлы
    polygons = []
    original_dxf_data_map = {}
    
    for file_path in existing_files:
        print(f"\\n📖 Парсим: {os.path.basename(file_path)}")
        try:
            with open(file_path, 'rb') as f:
                parsed_data = parse_dxf_complete(f, verbose=False)
            
            if parsed_data['combined_polygon']:
                file_name = os.path.basename(file_path)
                color = "черный"  # Для простоты
                
                # Добавляем в список полигонов
                polygon_tuple = (parsed_data['combined_polygon'], file_name, color)
                polygons.append(polygon_tuple)
                
                # Сохраняем исходные данные
                original_dxf_data_map[file_name] = parsed_data
                
                print(f"  ✅ Полигон: {parsed_data['combined_polygon'].bounds}")
                print(f"  📊 Entities: {len(parsed_data['original_entities'])}")
                
                # Проверяем real_spline_bounds
                if parsed_data.get('real_spline_bounds'):
                    print(f"  📊 Real SPLINE bounds: {parsed_data['real_spline_bounds']}")
                    
                    # Проверяем расхождение
                    combined_bounds = parsed_data['combined_polygon'].bounds
                    spline_bounds = parsed_data['real_spline_bounds']
                    diff_x = abs(spline_bounds[0] - combined_bounds[0])
                    diff_y = abs(spline_bounds[1] - combined_bounds[1])
                    
                    if diff_x > 10 or diff_y > 10:
                        print(f"  ⚠️ БОЛЬШОЕ расхождение SPLINE vs Combined: Δx={diff_x:.1f}, Δy={diff_y:.1f}")
                    else:
                        print(f"  ✅ SPLINE bounds совпадают с Combined")
                else:
                    print(f"  📊 Нет SPLINE элементов")
                    
            else:
                print(f"  ❌ Не удалось создать полигон")
                
        except Exception as e:
            print(f"  ❌ Ошибка: {e}")
    
    if not polygons:
        print("❌ Нет полигонов для раскроя!")
        return False
    
    print(f"\\n🔄 Запускаем bin packing для {len(polygons)} полигонов...")
    
    # Параметры листа
    sheet_size = (200.0, 140.0)  # см -> 2000x1400 мм
    
    try:
        # Запускаем bin packing
        placed_elements, rejected_elements = bin_packing(
            polygons, 
            sheet_size, 
            max_attempts=1000, 
            verbose=True
        )
        
        print(f"\\n📊 Результат bin packing:")
        print(f"  Размещено: {len(placed_elements)} элементов")
        print(f"  Отклонено: {len(rejected_elements)} элементов")
        
        if not placed_elements:
            print("❌ Нет размещенных элементов!")
            return False
        
        # Анализируем размещенные элементы
        for i, element in enumerate(placed_elements):
            if len(element) >= 5:
                polygon, x_offset, y_offset, rotation_angle, file_name = element[:5]
                print(f"  {i+1}. {file_name}: offset=({x_offset:.1f}, {y_offset:.1f}), rotation={rotation_angle:.1f}°")
        
        # Сохраняем результат
        output_path = "/home/sasha/proj/2025/eva_layout/test_full_layout_result.dxf"
        
        print(f"\\n💾 Сохраняем результат: {output_path}")
        save_dxf_layout_complete(placed_elements, sheet_size, output_path, original_dxf_data_map)
        
        print(f"✅ Результат сохранен!")
        
        # Быстрый анализ результата
        import ezdxf
        result_doc = ezdxf.readfile(output_path)
        result_msp = result_doc.modelspace()
        
        result_entities = list(result_msp)
        splines = [e for e in result_entities if e.dxftype() == 'SPLINE']
        
        print(f"\\n📊 Анализ результата:")
        print(f"  Всего элементов: {len(result_entities)}")
        print(f"  SPLINE элементов: {len(splines)}")
        
        if splines:
            # Получаем bounds SPLINE'ов
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
                print(f"  📐 Bounds всех SPLINE'ов: {actual_bounds}")
                
                # Проверяем, помещаются ли в лист
                sheet_mm = (sheet_size[0] * 10, sheet_size[1] * 10)  # см -> мм
                
                within_sheet = (
                    actual_bounds[0] >= -10 and
                    actual_bounds[1] >= -10 and  
                    actual_bounds[2] <= sheet_mm[0] + 10 and
                    actual_bounds[3] <= sheet_mm[1] + 10
                )
                
                if within_sheet:
                    print(f"  ✅ SPLINE элементы помещаются в лист {sheet_mm}")
                    return True
                else:
                    print(f"  ❌ SPLINE элементы выходят за границы листа {sheet_mm}")
                    print(f"  🔍 Проверьте трансформацию SPLINE элементов")
                    return False
        else:
            print(f"  ❌ Нет SPLINE элементов в результате!")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка bin packing: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Тестирование полного процесса раскроя с исправлениями SPLINE")
    print("=" * 70)
    
    success = test_full_layout_process()
    
    print("\\n" + "=" * 70)
    if success:
        print("✅ ПОЛНЫЙ ПРОЦЕСС РАСКРОЯ РАБОТАЕТ КОРРЕКТНО!")
        print("🎯 SPLINE исправления успешно применены к основному алгоритму")
    else:
        print("❌ ПРОБЛЕМЫ В ПОЛНОМ ПРОЦЕССЕ РАСКРОЯ")
        print("🔍 Необходимо дополнительное исследование")