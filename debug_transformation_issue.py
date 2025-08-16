#!/usr/bin/env python3
"""
Диагностика проблемы трансформации между визуализацией и DXF.
"""

import tempfile
import os
from shapely.geometry import Polygon
import ezdxf
import numpy as np
from layout_optimizer import (
    bin_packing, save_dxf_layout_complete, parse_dxf_complete,
    rotate_polygon, translate_polygon
)

def debug_transformation_problem():
    """Детальная диагностика проблемы трансформации."""
    print("=== ДИАГНОСТИКА ПРОБЛЕМЫ ТРАНСФОРМАЦИИ ===")
    
    # Создаем простые тестовые полигоны
    polygons = []
    
    # Прямоугольник 1
    rect1 = Polygon([(0, 0), (100, 0), (100, 50), (0, 50)])
    polygons.append((rect1, "rect1.dxf", "красный", "order1"))
    
    # Прямоугольник 2
    rect2 = Polygon([(0, 0), (80, 0), (80, 40), (0, 40)])
    polygons.append((rect2, "rect2.dxf", "синий", "order2"))
    
    # Создаем fake original DXF data
    original_dxf_data_map = {}
    for i, (polygon, filename, color, order_id) in enumerate(polygons):
        original_dxf_data_map[filename] = {
            'combined_polygon': polygon,
            'original_entities': [],
            'polygons': [polygon],
            'bounds': polygon.bounds
        }
    
    sheet_size = (200, 150)  # см
    
    print(f"Тестируем {len(polygons)} полигонов на листе {sheet_size[0]}x{sheet_size[1]} см")
    
    # Выполняем bin_packing
    placed, unplaced = bin_packing(polygons, sheet_size, verbose=False)
    
    print(f"Результат bin_packing: размещено {len(placed)}, не размещено {len(unplaced)}")
    
    # Анализируем каждый размещенный полигон
    print("\n=== АНАЛИЗ РАЗМЕЩЕННЫХ ПОЛИГОНОВ ===")
    for i, placed_item in enumerate(placed):
        if len(placed_item) >= 5:
            polygon, x_offset, y_offset, rotation_angle, file_name = placed_item[:5]
            
            print(f"\nПолигон {i+1}: {file_name}")
            print(f"  Исходный bounds: {polygons[i][0].bounds}")
            print(f"  Финальный bounds: {polygon.bounds}")
            print(f"  Смещения: x={x_offset:.2f}, y={y_offset:.2f}")
            print(f"  Поворот: {rotation_angle}°")
            
            # Проверяем, как должна работать трансформация
            original_polygon = polygons[i][0]
            
            print(f"  ПОШАГОВАЯ ПРОВЕРКА ТРАНСФОРМАЦИИ:")
            
            # Шаг 1: Нормализация к origin
            orig_bounds = original_polygon.bounds
            step1 = translate_polygon(original_polygon, -orig_bounds[0], -orig_bounds[1])
            print(f"    Шаг 1 (нормализация): {step1.bounds}")
            
            # Шаг 2: Поворот
            if rotation_angle != 0:
                step2 = rotate_polygon(step1, rotation_angle)
                print(f"    Шаг 2 (поворот {rotation_angle}°): {step2.bounds}")
            else:
                step2 = step1
                print(f"    Шаг 2 (без поворота): {step2.bounds}")
            
            # Шаг 3: Финальное смещение
            # Внимание! x_offset и y_offset могут НЕ включать исходные bounds
            final_bounds_expected = (
                step2.bounds[0] + x_offset + orig_bounds[0],
                step2.bounds[1] + y_offset + orig_bounds[1],
                step2.bounds[2] + x_offset + orig_bounds[0],
                step2.bounds[3] + y_offset + orig_bounds[1]
            )
            print(f"    Ожидаемый финальный bounds: {final_bounds_expected}")
            print(f"    Фактический финальный bounds: {polygon.bounds}")
            
            # Проверяем соответствие
            diff = [abs(polygon.bounds[j] - final_bounds_expected[j]) for j in range(4)]
            max_diff = max(diff)
            print(f"    Максимальная разность: {max_diff:.3f}")
            
            if max_diff > 0.01:
                print(f"    ⚠️ ВОЗМОЖНАЯ ПРОБЛЕМА В ТРАНСФОРМАЦИИ!")
    
    # Теперь сохраняем DXF и проверяем результат
    print("\n=== ТЕСТ СОХРАНЕНИЯ DXF ===")
    
    with tempfile.NamedTemporaryFile(suffix='.dxf', delete=False) as tmp_file:
        dxf_path = tmp_file.name
    
    try:
        # Сохраняем DXF
        save_dxf_layout_complete(placed, sheet_size, dxf_path, original_dxf_data_map)
        print(f"✅ DXF сохранен: {dxf_path}")
        
        # Читаем DXF и анализируем
        doc = ezdxf.readfile(dxf_path)
        msp = doc.modelspace()
        
        # Находим все polylines (исключая boundary)
        polylines = [e for e in msp if e.dxftype() == 'LWPOLYLINE' and 'BOUNDARY' not in e.dxf.layer]
        
        print(f"Найдено {len(polylines)} polylines в DXF")
        
        # Анализируем каждый polyline
        for i, polyline in enumerate(polylines):
            layer = polyline.dxf.layer
            points = list(polyline.get_points())
            
            if points:
                xs = [p[0] for p in points]
                ys = [p[1] for p in points]
                dxf_bounds = (min(xs), min(ys), max(xs), max(ys))
                
                print(f"\nPolyline {i+1} (layer: {layer}):")
                print(f"  DXF bounds: {dxf_bounds}")
                print(f"  Точки: {[(p[0], p[1]) for p in points[:4]]}")  # Первые 4 точки
                
                # Сравниваем с ожидаемым из placed
                if i < len(placed):
                    placed_polygon = placed[i][0]
                    viz_bounds = placed_polygon.bounds
                    
                    diff = [abs(viz_bounds[j] - dxf_bounds[j]) for j in range(4)]
                    max_diff = max(diff)
                    
                    print(f"  Ожидаемые bounds: {viz_bounds}")
                    print(f"  Разности: {diff}")
                    print(f"  Макс. разность: {max_diff:.3f}")
                    
                    if max_diff > 1.0:  # 1мм допуск
                        print(f"  ❌ РАССОГЛАСОВАНИЕ!")
                    else:
                        print(f"  ✅ Соответствует")
        
        print(f"\n=== ИТОГОВАЯ ДИАГНОСТИКА ===")
        
        total_errors = 0
        for i, polyline in enumerate(polylines[:len(placed)]):
            points = list(polyline.get_points())
            if points:
                xs = [p[0] for p in points]
                ys = [p[1] for p in points]
                dxf_bounds = (min(xs), min(ys), max(xs), max(ys))
                
                placed_polygon = placed[i][0]
                viz_bounds = placed_polygon.bounds
                
                diff = [abs(viz_bounds[j] - dxf_bounds[j]) for j in range(4)]
                max_diff = max(diff)
                
                if max_diff > 1.0:
                    total_errors += 1
        
        if total_errors == 0:
            print("✅ ВСЕ ПОЛИГОНЫ СИНХРОНИЗИРОВАНЫ")
            return True
        else:
            print(f"❌ НАЙДЕНО {total_errors} ОШИБОК СИНХРОНИЗАЦИИ")
            return False
            
    finally:
        if os.path.exists(dxf_path):
            print(f"Сохранен тестовый DXF: {dxf_path}")
            # os.unlink(dxf_path)  # Оставляем для анализа
    
    return False

if __name__ == "__main__":
    success = debug_transformation_problem()
    print(f"\nРезультат диагностики: {'✅ ОК' if success else '❌ ПРОБЛЕМА ОБНАРУЖЕНА'}")
    exit(0 if success else 1)