#!/usr/bin/env python3
"""
Принудительный тест синхронизации поворотов.
"""

import tempfile
import os
from shapely.geometry import Polygon
import ezdxf
from layout_optimizer import (
    save_dxf_layout_complete, rotate_polygon, translate_polygon, 
    apply_placement_transform
)

def test_forced_rotation():
    """Принудительный тест поворота."""
    print("=== Принудительный тест поворота ===")
    
    # Создаем исходный прямоугольник
    rect = Polygon([(0, 0), (40, 0), (40, 15), (0, 15)])
    print(f"Исходный rect bounds: {rect.bounds}")
    
    # Параметры трансформации
    x_offset = 50
    y_offset = 30
    rotation_angle = 90
    
    # Применяем поворот как в bin_packing
    rotated = rotate_polygon(rect, rotation_angle)
    print(f"После поворота bounds: {rotated.bounds}")
    
    # Применяем смещение
    final_polygon = translate_polygon(rotated, x_offset, y_offset)
    print(f"После смещения bounds: {final_polygon.bounds}")
    
    # Создаем placed_element как в bin_packing
    placed_element = (final_polygon, x_offset, y_offset, rotation_angle, "test_rotated.dxf", "красный")
    placed_elements = [placed_element]
    
    # Original data map
    original_dxf_data_map = {
        "test_rotated.dxf": {
            'combined_polygon': rect,
            'original_entities': [],
            'polygons': [rect],
            'bounds': rect.bounds
        }
    }
    
    sheet_size = (150, 100)
    
    # Тестируем DXF сохранение
    with tempfile.NamedTemporaryFile(suffix='.dxf', delete=False) as tmp_file:
        dxf_path = tmp_file.name
    
    try:
        print(f"\nСохраняем DXF с принудительным поворотом...")
        save_dxf_layout_complete(placed_elements, sheet_size, dxf_path, original_dxf_data_map)
        print(f"✅ DXF сохранен: {dxf_path}")
        
        # Читаем DXF
        doc = ezdxf.readfile(dxf_path)
        msp = doc.modelspace()
        
        # Находим polylines (исключая boundary)
        polylines = [e for e in msp if e.dxftype() == 'LWPOLYLINE' and 'BOUNDARY' not in e.dxf.layer]
        
        if polylines:
            polyline = polylines[0]
            points = list(polyline.get_points())
            
            print(f"\nDXF полигон после поворота:")
            print(f"  Точки (первые 4): {[(p[0], p[1]) for p in points[:4]]}")
            
            if points:
                xs = [p[0] for p in points]
                ys = [p[1] for p in points]
                dxf_bounds = (min(xs), min(ys), max(xs), max(ys))
                
                print(f"  DXF bounds: {dxf_bounds}")
                
                # Сравниваем с ожидаемым результатом
                viz_bounds = final_polygon.bounds
                tolerance = 2.0
                
                differences = [abs(viz_bounds[i] - dxf_bounds[i]) for i in range(4)]
                max_diff = max(differences)
                
                print(f"\nСравнение поворота:")
                print(f"  Ожидаемые bounds: {viz_bounds}")
                print(f"  DXF bounds:       {dxf_bounds}")
                print(f"  Разности:         {differences}")
                print(f"  Макс. разность:   {max_diff:.2f}мм")
                
                # Дополнительная проверка - сравниваем размеры
                viz_width = viz_bounds[2] - viz_bounds[0]
                viz_height = viz_bounds[3] - viz_bounds[1]
                dxf_width = dxf_bounds[2] - dxf_bounds[0]
                dxf_height = dxf_bounds[3] - dxf_bounds[1]
                
                print(f"\nПроверка размеров:")
                print(f"  Визуализация: {viz_width:.1f} x {viz_height:.1f}")
                print(f"  DXF:          {dxf_width:.1f} x {dxf_height:.1f}")
                
                # Проверяем, что поворот на 90° сработал (размеры поменялись местами)
                original_width = 40.0
                original_height = 15.0
                
                if rotation_angle == 90:
                    expected_width = original_height  # 15
                    expected_height = original_width  # 40
                    
                    width_ok = abs(dxf_width - expected_width) < 1.0
                    height_ok = abs(dxf_height - expected_height) < 1.0
                    
                    print(f"  Ожидаемые размеры после поворота: {expected_width} x {expected_height}")
                    print(f"  Размеры совпадают: width={width_ok}, height={height_ok}")
                    
                    if width_ok and height_ok and max_diff < tolerance:
                        print(f"✅ ПОВОРОТ КОРРЕКТНО СИНХРОНИЗИРОВАН!")
                        return True
                    else:
                        print(f"❌ ОШИБКА СИНХРОНИЗАЦИИ ПОВОРОТА")
                        return False
                else:
                    if max_diff < tolerance:
                        print(f"✅ ПОЗИЦИЯ СИНХРОНИЗИРОВАНА")
                        return True
                    else:
                        print(f"❌ ОШИБКА СИНХРОНИЗАЦИИ ПОЗИЦИИ")
                        return False
        else:
            print("❌ Не найдено polylines в DXF")
            return False
            
    finally:
        if os.path.exists(dxf_path):
            os.unlink(dxf_path)
    
    return False

if __name__ == "__main__":
    success = test_forced_rotation()
    print(f"\nРезультат принудительного теста поворота: {'✅ УСПЕХ' if success else '❌ НЕУДАЧА'}")
    exit(0 if success else 1)