#!/usr/bin/env python3
"""
Тест синхронизации поворотов между визуализацией и DXF.
"""

import tempfile
import os
from shapely.geometry import Polygon
import ezdxf
from layout_optimizer import bin_packing, save_dxf_layout_complete, rotate_polygon

def test_rotation_sync():
    """Тест синхронизации с поворотом."""
    print("=== Тест синхронизации поворотов ===")
    
    # Создаем прямоугольник, который нужно будет повернуть
    rect = Polygon([(0, 0), (40, 0), (40, 15), (0, 15)])  # Узкий прямоугольник
    polygons = [(rect, "narrow_rect.dxf", "синий", "test_order")]
    
    # Original data map
    original_dxf_data_map = {
        "narrow_rect.dxf": {
            'combined_polygon': rect,
            'original_entities': [],
            'polygons': [rect],
            'bounds': rect.bounds
        }
    }
    
    # Используем узкий лист, чтобы заставить поворот
    sheet_size = (30, 50)  # см - узкий лист
    
    # Размещение
    placed, unplaced = bin_packing(polygons, sheet_size, verbose=True)
    
    print(f"Размещено: {len(placed)}, не размещено: {len(unplaced)}")
    
    if not placed:
        print("❌ Не удалось разместить полигон")
        return False
    
    # Анализируем результат
    placed_item = placed[0]
    if len(placed_item) >= 5:
        transformed_polygon, x_offset, y_offset, rotation_angle, file_name = placed_item[:5]
        
        print(f"\nРезультат размещения:")
        print(f"  Файл: {file_name}")
        print(f"  Смещение: x={x_offset:.2f}, y={y_offset:.2f}")
        print(f"  Поворот: {rotation_angle}°")
        print(f"  Исходные bounds: {rect.bounds}")
        print(f"  Финальные bounds: {transformed_polygon.bounds}")
        
        # Проверяем применение поворота
        if rotation_angle != 0:
            print(f"✅ Обнаружен поворот на {rotation_angle}°")
            
            # Проверяем, что поворот применен корректно
            test_rotated = rotate_polygon(rect, rotation_angle)
            print(f"  Тестовый поворот bounds: {test_rotated.bounds}")
        else:
            print("ℹ️ Поворот не применен")
        
        # Тестируем DXF
        with tempfile.NamedTemporaryFile(suffix='.dxf', delete=False) as tmp_file:
            dxf_path = tmp_file.name
        
        try:
            # Сохраняем DXF
            save_dxf_layout_complete(placed, sheet_size, dxf_path, original_dxf_data_map)
            print(f"✅ DXF сохранен: {dxf_path}")
            
            # Читаем и анализируем DXF
            doc = ezdxf.readfile(dxf_path)
            msp = doc.modelspace()
            
            # Находим polylines
            polylines = [e for e in msp if e.dxftype() == 'LWPOLYLINE' and 'BOUNDARY' not in e.dxf.layer]
            
            if polylines:
                polyline = polylines[0]
                points = list(polyline.get_points())
                
                print(f"\nDXF полигон:")
                print(f"  Точки: {points}")
                
                if points:
                    xs = [p[0] for p in points]
                    ys = [p[1] for p in points]
                    dxf_bounds = (min(xs), min(ys), max(xs), max(ys))
                    
                    print(f"  DXF bounds: {dxf_bounds}")
                    
                    # Сравниваем с визуализацией
                    viz_bounds = transformed_polygon.bounds
                    tolerance = 2.0
                    
                    differences = [abs(viz_bounds[i] - dxf_bounds[i]) for i in range(4)]
                    max_diff = max(differences)
                    
                    print(f"\nСравнение:")
                    print(f"  Визуализация: {viz_bounds}")
                    print(f"  DXF:          {dxf_bounds}")
                    print(f"  Разности:     {differences}")
                    print(f"  Макс. разность: {max_diff:.2f}мм")
                    
                    if max_diff < tolerance:
                        print(f"✅ ПОВОРОТ СИНХРОНИЗИРОВАН (допуск {tolerance}мм)")
                        return True
                    else:
                        print(f"❌ РАССОГЛАСОВАНИЕ ПОВОРОТА! {max_diff:.2f}мм > {tolerance}мм")
                        return False
            else:
                print("❌ Не найдено polylines в DXF")
                return False
                
        finally:
            if os.path.exists(dxf_path):
                os.unlink(dxf_path)
    
    return False

if __name__ == "__main__":
    success = test_rotation_sync()
    print(f"\nРезультат теста поворота: {'✅ УСПЕХ' if success else '❌ НЕУДАЧА'}")
    exit(0 if success else 1)