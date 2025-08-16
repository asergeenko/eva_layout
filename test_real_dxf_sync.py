#!/usr/bin/env python3
"""
Тест с реальными DXF файлами для проверки синхронизации.
"""

import tempfile
import os
from shapely.geometry import Polygon
import ezdxf
from layout_optimizer import (
    bin_packing, save_dxf_layout_complete, parse_dxf_complete
)

def test_with_real_complex_shapes():
    """Тест с реальными сложными формами."""
    print("=== ТЕСТ С РЕАЛЬНЫМИ СЛОЖНЫМИ ФОРМАМИ ===")
    
    # Создаем более сложные полигоны, похожие на те, что в лодках
    polygons = []
    original_dxf_data_map = {}
    
    # Полигон 1: Сложная форма (имитируем лодку)
    complex_shape1 = Polygon([
        (0, 0), (150, 0), (180, 20), (190, 50), (185, 80), 
        (170, 100), (140, 110), (100, 115), (60, 110), 
        (30, 100), (10, 80), (5, 50), (15, 20)
    ])
    
    display_name1 = "Лодка АГУЛ 270_2.dxf"
    polygons.append((complex_shape1, display_name1, "черный", "order1"))
    
    # Имитируем original_dxf_data как в streamlit_demo
    original_dxf_data_map[display_name1] = {
        'combined_polygon': complex_shape1,
        'original_entities': [],  # Упрощенно, без реальных entities
        'polygons': [complex_shape1],
        'bounds': complex_shape1.bounds
    }
    
    # Полигон 2: Еще одна сложная форма
    complex_shape2 = Polygon([
        (0, 0), (100, 0), (120, 15), (130, 40), (125, 65),
        (110, 80), (80, 85), (50, 80), (20, 65), (10, 40), (15, 15)
    ])
    
    display_name2 = "TOYOTA COROLLA VERSO_2.dxf"
    polygons.append((complex_shape2, display_name2, "черный", "order2"))
    
    original_dxf_data_map[display_name2] = {
        'combined_polygon': complex_shape2,
        'original_entities': [],
        'polygons': [complex_shape2], 
        'bounds': complex_shape2.bounds
    }
    
    sheet_size = (300, 200)  # см
    
    print(f"Тестируем {len(polygons)} сложных полигонов")
    print(f"Ключи в original_dxf_data_map: {list(original_dxf_data_map.keys())}")
    
    # Размещение
    placed, unplaced = bin_packing(polygons, sheet_size, verbose=False)
    
    print(f"Размещено: {len(placed)}, не размещено: {len(unplaced)}")
    
    if not placed:
        print("❌ Не удалось разместить полигоны")
        return False
    
    # Анализируем file_name в placed
    print("\nФайлы в placed_polygons:")
    for i, placed_item in enumerate(placed):
        if len(placed_item) >= 5:
            _, _, _, _, file_name = placed_item[:5]
            print(f"  {i+1}: '{file_name}'")
            
            # Проверяем, найдется ли ключ
            file_basename = os.path.basename(file_name)
            found_key = None
            
            if file_name in original_dxf_data_map:
                found_key = file_name
                print(f"    Найден exact match: '{found_key}'")
            elif file_basename in original_dxf_data_map:
                found_key = file_basename
                print(f"    Найден basename match: '{found_key}'")
            else:
                for key in original_dxf_data_map.keys():
                    if os.path.basename(key) == file_basename:
                        found_key = key
                        print(f"    Найден key basename match: '{found_key}'")
                        break
            
            if not found_key:
                print(f"    ❌ НЕ НАЙДЕН КЛЮЧ для '{file_name}'")
                return False
    
    # Тестируем DXF сохранение
    with tempfile.NamedTemporaryFile(suffix='.dxf', delete=False) as tmp_file:
        dxf_path = tmp_file.name
    
    try:
        print(f"\nСохраняем DXF...")
        save_dxf_layout_complete(placed, sheet_size, dxf_path, original_dxf_data_map)
        print(f"✅ DXF сохранен: {dxf_path}")
        
        # Читаем и проверяем
        doc = ezdxf.readfile(dxf_path)
        msp = doc.modelspace()
        
        polylines = [e for e in msp if e.dxftype() == 'LWPOLYLINE' and 'BOUNDARY' not in e.dxf.layer]
        
        print(f"Найдено {len(polylines)} polylines в DXF")
        
        if len(polylines) != len(placed):
            print(f"❌ НЕСООТВЕТСТВИЕ: ожидалось {len(placed)} polylines, найдено {len(polylines)}")
            return False
        
        # Проверяем каждый polyline
        sync_errors = 0
        for i, polyline in enumerate(polylines):
            layer = polyline.dxf.layer
            points = list(polyline.get_points())
            
            if points and i < len(placed):
                xs = [p[0] for p in points]
                ys = [p[1] for p in points]
                dxf_bounds = (min(xs), min(ys), max(xs), max(ys))
                
                placed_polygon = placed[i][0]
                viz_bounds = placed_polygon.bounds
                
                diff = [abs(viz_bounds[j] - dxf_bounds[j]) for j in range(4)]
                max_diff = max(diff)
                
                print(f"Polyline {i+1} (layer: {layer}):")
                print(f"  Визуализация: {viz_bounds}")
                print(f"  DXF:          {dxf_bounds}")
                print(f"  Макс. разность: {max_diff:.3f}мм")
                
                if max_diff > 2.0:  # 2мм допуск
                    print(f"  ❌ РАССОГЛАСОВАНИЕ!")
                    sync_errors += 1
                else:
                    print(f"  ✅ Синхронизировано")
        
        if sync_errors == 0:
            print(f"\n✅ ВСЕ {len(placed)} ПОЛИГОНОВ СИНХРОНИЗИРОВАНЫ")
            return True
        else:
            print(f"\n❌ НАЙДЕНО {sync_errors} ОШИБОК СИНХРОНИЗАЦИИ")
            return False
            
    finally:
        if os.path.exists(dxf_path):
            print(f"Сохранен тестовый файл: {dxf_path}")
            # os.unlink(dxf_path)  # Сохраняем для анализа
    
    return False

if __name__ == "__main__":
    success = test_with_real_complex_shapes()
    print(f"\nРезультат теста реальных форм: {'✅ УСПЕХ' if success else '❌ НЕУДАЧА'}")
    exit(0 if success else 1)