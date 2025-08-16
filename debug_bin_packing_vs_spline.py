#!/usr/bin/env python3
"""
Отладка расхождения между bin packing и SPLINE трансформацией.
"""

import tempfile
import os
from layout_optimizer import (
    parse_dxf_complete, 
    bin_packing, 
    save_dxf_layout_complete,
    apply_placement_transform
)

def debug_bin_packing_vs_spline():
    """Отлаживает расхождение между bin packing и SPLINE трансформацией."""
    print("=== ОТЛАДКА BIN PACKING VS SPLINE ===")
    
    # Берем простой файл для отладки
    test_file = "/home/sasha/proj/2025/eva_layout/dxf_samples/Лодка АГУЛ 270/2.dxf"
    
    print(f"📁 Отлаживаем файл: {os.path.basename(test_file)}")
    
    # Парсим файл
    with open(test_file, 'rb') as f:
        parsed_data = parse_dxf_complete(f, verbose=False)
    
    original_polygon = parsed_data['combined_polygon']
    real_spline_bounds = parsed_data.get('real_spline_bounds')
    
    print(f"📊 Combined polygon bounds: {original_polygon.bounds}")
    print(f"📊 Real SPLINE bounds: {real_spline_bounds}")
    
    # Настройки
    file_name = os.path.basename(test_file)
    color = "черный"
    sheet_size = (200.0, 140.0)  # см -> 2000x1400 мм
    
    # Запускаем bin packing
    polygons = [(original_polygon, file_name, color)]
    placed_elements, rejected_elements = bin_packing(polygons, sheet_size, max_attempts=1000, verbose=True)
    
    if not placed_elements:
        print("❌ Bin packing не разместил элементы!")
        return
    
    placed_element = placed_elements[0]
    polygon, x_offset, y_offset, rotation_angle, file_name_result = placed_element[:5]
    
    print(f"\\n🔄 Результат bin packing:")
    print(f"  Размещение: x_offset={x_offset:.2f}, y_offset={y_offset:.2f}, rotation={rotation_angle:.1f}°")
    print(f"  Полигон bounds: {polygon.bounds}")
    
    # Проверяем, что получается с apply_placement_transform
    expected_polygon = apply_placement_transform(original_polygon, x_offset, y_offset, rotation_angle)
    print(f"\\n📊 apply_placement_transform result:")
    print(f"  Expected bounds: {expected_polygon.bounds}")
    
    # Сравниваем с результатом bin packing
    placed_bounds = polygon.bounds
    expected_bounds = expected_polygon.bounds
    
    bounds_match = all(abs(placed_bounds[i] - expected_bounds[i]) < 1.0 for i in range(4))
    
    if bounds_match:
        print(f"  ✅ Bin packing и apply_placement_transform СОВПАДАЮТ")
    else:
        diff = [placed_bounds[i] - expected_bounds[i] for i in range(4)]
        print(f"  ❌ РАСХОЖДЕНИЕ: {diff}")
    
    # Теперь имитируем SPLINE трансформацию вручную
    print(f"\\n🔧 Имитация SPLINE трансформации:")
    
    # Берем первый SPLINE
    spline_entities = [e for e in parsed_data['original_entities'] if e['type'] == 'SPLINE']
    if not spline_entities:
        print("  ❌ Нет SPLINE элементов!")
        return
    
    first_spline = spline_entities[0]
    entity = first_spline['entity']
    control_points = entity.control_points
    
    if not control_points:
        print("  ❌ Нет контрольных точек!")
        return
    
    # Первая контрольная точка
    cp = control_points[0]
    if hasattr(cp, 'x') and hasattr(cp, 'y'):
        x_orig, y_orig = cp.x, cp.y
    elif len(cp) >= 2:
        x_orig, y_orig = float(cp[0]), float(cp[1])
    else:
        print("  ❌ Неизвестный формат точки!")
        return
    
    print(f"  Исходная точка SPLINE: ({x_orig:.2f}, {y_orig:.2f})")
    
    # Применяем трансформацию как в коде
    if real_spline_bounds:
        # Используем real_spline_bounds
        norm_bounds = real_spline_bounds
        print(f"  Нормализация по real_spline_bounds: {norm_bounds}")
    else:
        # Fallback к combined polygon bounds
        norm_bounds = original_polygon.bounds
        print(f"  Нормализация по combined bounds: {norm_bounds}")
    
    # Step 1: Normalize to origin
    x_norm = x_orig - norm_bounds[0]
    y_norm = y_orig - norm_bounds[1]
    print(f"  После нормализации: ({x_norm:.2f}, {y_norm:.2f})")
    
    # Step 2: Skip rotation (rotation_angle = 0)
    
    # Step 3: Apply final position  
    x_final = x_norm + x_offset
    y_final = y_norm + y_offset
    print(f"  После трансформации: ({x_final:.2f}, {y_final:.2f})")
    
    # Ожидаемая позиция точки согласно apply_placement_transform
    combined_bounds = original_polygon.bounds
    x_norm_expected = x_orig - combined_bounds[0]
    y_norm_expected = y_orig - combined_bounds[1]
    x_final_expected = x_norm_expected + x_offset
    y_final_expected = y_norm_expected + y_offset
    print(f"  Ожидаемая позиция (apply_placement_transform): ({x_final_expected:.2f}, {y_final_expected:.2f})")
    
    # Разность
    diff_x = x_final - x_final_expected
    diff_y = y_final - y_final_expected
    print(f"  Разность SPLINE vs Expected: ({diff_x:.2f}, {diff_y:.2f})")
    
    if abs(diff_x) < 0.1 and abs(diff_y) < 0.1:
        print(f"  ✅ SPLINE трансформация корректна!")
    else:
        print(f"  ❌ SPLINE трансформация НЕКОРРЕКТНА!")
        
        if norm_bounds != combined_bounds:
            print(f"  💡 Причина: Разные bounds для нормализации!")
            print(f"     SPLINE нормализация: {norm_bounds}")
            print(f"     Expected нормализация: {combined_bounds}")
    
    # Проверим реальный результат save_dxf_layout_complete
    print(f"\\n💾 Проверяем save_dxf_layout_complete:")
    
    original_dxf_data_map = {file_name: parsed_data}
    
    with tempfile.NamedTemporaryFile(suffix='.dxf', delete=False) as tmp_file:
        output_path = tmp_file.name
    
    try:
        save_dxf_layout_complete(placed_elements, sheet_size, output_path, original_dxf_data_map)
        
        import ezdxf
        result_doc = ezdxf.readfile(output_path)
        result_msp = result_doc.modelspace()
        
        splines = [e for e in result_msp if e.dxftype() == 'SPLINE']
        print(f"  SPLINE'ов в результате: {len(splines)}")
        
        if splines:
            # Проверяем первую точку первого SPLINE
            first_result_spline = splines[0]
            result_cp = first_result_spline.control_points[0]
            
            if hasattr(result_cp, 'x') and hasattr(result_cp, 'y'):
                x_result, y_result = result_cp.x, result_cp.y
            elif len(result_cp) >= 2:
                x_result, y_result = float(result_cp[0]), float(result_cp[1])
            else:
                print("  ❌ Неизвестный формат результирующей точки!")
                return
            
            print(f"  Реальная позиция в DXF: ({x_result:.2f}, {y_result:.2f})")
            print(f"  Ожидаемая позиция: ({x_final_expected:.2f}, {y_final_expected:.2f})")
            
            diff_real_x = x_result - x_final_expected
            diff_real_y = y_result - y_final_expected
            print(f"  Разность реальная vs ожидаемая: ({diff_real_x:.2f}, {diff_real_y:.2f})")
            
            if abs(diff_real_x) < 1.0 and abs(diff_real_y) < 1.0:
                print(f"  ✅ DXF результат КОРРЕКТЕН!")
            else:
                print(f"  ❌ DXF результат НЕКОРРЕКТЕН!")
                print(f"  🔍 Проблема в save_dxf_layout_complete")
        
    finally:
        if os.path.exists(output_path):
            os.unlink(output_path)

if __name__ == "__main__":
    print("🔍 Отладка расхождения между bin packing и SPLINE трансформацией")
    print("=" * 70)
    
    debug_bin_packing_vs_spline()
    
    print("\\n" + "=" * 70)
    print("✅ АНАЛИЗ ЗАВЕРШЕН")