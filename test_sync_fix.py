#!/usr/bin/env python3
"""
Простой тест синхронизации между визуализацией и сохранением DXF.
"""

import tempfile
import os
from shapely.geometry import Polygon
import ezdxf
from layout_optimizer import bin_packing, save_dxf_layout_complete

def test_simple_sync():
    """Простой тест синхронизации."""
    print("=== Тест синхронизации DXF и визуализации ===")
    
    # Создаем простой тестовый полигон
    rect = Polygon([(0, 0), (30, 0), (30, 20), (0, 20)])
    polygons = [(rect, "test_rect.dxf", "красный", "test_order")]
    
    # Создаем fake original data
    original_dxf_data_map = {
        "test_rect.dxf": {
            'combined_polygon': rect,
            'original_entities': [],
            'polygons': [rect],
            'bounds': rect.bounds
        }
    }
    
    sheet_size = (100, 80)  # см
    
    # Выполняем размещение
    placed, unplaced = bin_packing(polygons, sheet_size, verbose=False)
    
    print(f"Размещено: {len(placed)}, не размещено: {len(unplaced)}")
    
    if not placed:
        print("❌ Не удалось разместить полигон")
        return False
    
    # Анализируем результат размещения
    placed_item = placed[0]
    if len(placed_item) >= 5:
        transformed_polygon, x_offset, y_offset, rotation_angle, file_name = placed_item[:5]
        
        print(f"Размещенный полигон:")
        print(f"  Файл: {file_name}")
        print(f"  Смещение: x={x_offset:.2f}, y={y_offset:.2f}")
        print(f"  Поворот: {rotation_angle}°")
        print(f"  Финальные bounds: {transformed_polygon.bounds}")
        
        # Создаем временный DXF файл
        with tempfile.NamedTemporaryFile(suffix='.dxf', delete=False) as tmp_file:
            dxf_path = tmp_file.name
        
        try:
            # Сохраняем DXF
            save_dxf_layout_complete(placed, sheet_size, dxf_path, original_dxf_data_map)
            print(f"✅ DXF сохранен: {dxf_path}")
            
            # Читаем DXF и проверяем позиции
            doc = ezdxf.readfile(dxf_path)
            msp = doc.modelspace()
            
            # Ищем элементы (исключая boundary)
            polylines = [e for e in msp if e.dxftype() == 'LWPOLYLINE' and 'BOUNDARY' not in e.dxf.layer]
            
            if polylines:
                polyline = polylines[0]
                points = list(polyline.get_points())
                
                if points:
                    xs = [p[0] for p in points]
                    ys = [p[1] for p in points]
                    dxf_bounds = (min(xs), min(ys), max(xs), max(ys))
                    
                    print(f"DXF bounds: {dxf_bounds}")
                    
                    # Сравниваем bounds
                    viz_bounds = transformed_polygon.bounds
                    tolerance = 2.0  # 2мм допуск
                    
                    differences = [abs(viz_bounds[i] - dxf_bounds[i]) for i in range(4)]
                    max_diff = max(differences)
                    
                    print(f"Максимальная разность: {max_diff:.2f}мм")
                    
                    if max_diff < tolerance:
                        print(f"✅ СИНХРОНИЗАЦИЯ ОК (допуск {tolerance}мм)")
                        return True
                    else:
                        print(f"❌ РАССОГЛАСОВАНИЕ! Разность {max_diff:.2f}мм > {tolerance}мм")
                        print(f"Детали разностей: {differences}")
                        return False
            else:
                print("❌ Не найдено polylines в DXF")
                return False
                
        finally:
            # Удаляем временный файл
            if os.path.exists(dxf_path):
                os.unlink(dxf_path)
    
    return False

if __name__ == "__main__":
    success = test_simple_sync()
    print(f"\nРезультат: {'✅ УСПЕХ' if success else '❌ НЕУДАЧА'}")
    exit(0 if success else 1)