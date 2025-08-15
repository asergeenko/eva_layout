#!/usr/bin/env python3
"""
Тест для проверки исправления проблемы с поворотом ковров.
Этот тест проверяет, что повернутые ковры остаются в правильном положении.
"""

from layout_optimizer import parse_dxf_complete, save_dxf_layout_complete, rotate_polygon
from shapely.geometry import Polygon
import tempfile
import os

def test_rotation_consistency():
    """Тест на соответствие поворота между bin_packing и save_dxf_layout_complete"""
    
    # Создаем простой прямоугольник (имитируем ковер)
    original_polygon = Polygon([(0, 0), (100, 0), (100, 50), (0, 50)])
    print(f"Исходный ковер: bounds={original_polygon.bounds}")
    
    # Имитируем результат bin_packing - ковер размещен с поворотом на 90°
    angle = 90
    x_offset = 200  # смещение после размещения
    y_offset = 100
    
    # Применяем поворот (как это делает bin_packing)
    rotated_polygon = rotate_polygon(original_polygon, angle)
    print(f"После поворота: bounds={rotated_polygon.bounds}")
    
    # Применяем смещение (как это делает bin_packing)
    from layout_optimizer import translate_polygon
    final_polygon = translate_polygon(rotated_polygon, x_offset, y_offset)
    print(f"После смещения: bounds={final_polygon.bounds}")
    
    # Создаем имитацию данных для сохранения DXF
    placed_elements = [(final_polygon, x_offset, y_offset, angle, "test_carpet.dxf", "серый")]
    
    # Создаем имитацию исходных DXF данных
    original_dxf_data = {
        'combined_polygon': original_polygon,
        'original_entities': []  # Упрощенно, пустой список
    }
    
    original_dxf_data_map = {"test_carpet.dxf": original_dxf_data}
    
    # Тестируем сохранение DXF
    with tempfile.NamedTemporaryFile(suffix='.dxf', delete=False) as tmp_file:
        output_path = tmp_file.name
    
    try:
        save_dxf_layout_complete(
            placed_elements, 
            (300, 200), 
            output_path, 
            original_dxf_data_map
        )
        print(f"✅ DXF файл успешно сохранен: {output_path}")
        
        # Читаем результат и проверяем
        from layout_optimizer import parse_dxf_complete
        result = parse_dxf_complete(output_path, verbose=False)
        
        if result['polygons'] and len(result['polygons']) >= 2:
            # Первый полигон - границы листа, второй - наш ковер
            carpet_polygon = result['polygons'][1]  # Пропускаем границу листа
            result_bounds = carpet_polygon.bounds
            print(f"Результат после чтения DXF (ковер): bounds={result_bounds}")
            
            # Проверяем, что положение соответствует ожидаемому
            expected_bounds = final_polygon.bounds
            tolerance = 2.0  # 2мм погрешность для учета DXF конверсии
            
            bounds_match = (
                abs(result_bounds[0] - expected_bounds[0]) < tolerance and
                abs(result_bounds[1] - expected_bounds[1]) < tolerance and
                abs(result_bounds[2] - expected_bounds[2]) < tolerance and
                abs(result_bounds[3] - expected_bounds[3]) < tolerance
            )
            
            if bounds_match:
                print("✅ ТЕСТ ПРОЙДЕН: Положение ковра после поворота соответствует ожидаемому")
                return True
            else:
                print(f"❌ ТЕСТ НЕ ПРОЙДЕН: Положение не соответствует")
                print(f"  Ожидалось: {expected_bounds}")
                print(f"  Получено: {result_bounds}")
                print(f"  Погрешности: dx={abs(result_bounds[0] - expected_bounds[0]):.2f}, dy={abs(result_bounds[1] - expected_bounds[1]):.2f}")
                return False
        else:
            print("❌ ТЕСТ НЕ ПРОЙДЕН: Не найдено достаточно полигонов в DXF")
            print(f"Найдено полигонов: {len(result['polygons']) if result['polygons'] else 0}")
            return False
            
    finally:
        if os.path.exists(output_path):
            os.unlink(output_path)

if __name__ == "__main__":
    print("=== Тест исправления поворота ковров ===")
    success = test_rotation_consistency()
    print("=== Результат ===")
    if success:
        print("🎉 Проблема с поворотом ковров ИСПРАВЛЕНА!")
    else:
        print("🚨 Проблема с поворотом ковров НЕ ИСПРАВЛЕНА!")