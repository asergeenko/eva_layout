#!/usr/bin/env python3
"""
Трассировка где теряется масштаб объектов
"""

import sys
import os
import glob
sys.path.insert(0, '.')

import ezdxf
from layout_optimizer import parse_dxf_complete, convert_entity_to_polygon_improved
from shapely.geometry import Polygon
from shapely.affinity import scale, translate

def trace_scale_issue():
    """Прослеживаем весь путь объекта от DXF до финального размера"""
    print("🔍 ТРАССИРОВКА МАСШТАБА ОБЪЕКТОВ")
    print("=" * 60)
    
    tank_file = "dxf_samples/TANK 300/1.dxf"
    if not os.path.exists(tank_file):
        print(f"❌ Файл {tank_file} не найден!")
        return
    
    print(f"Анализируем файл: {tank_file}")
    
    # ШАГ 1: Читаем DXF напрямую
    print(f"\n📋 ШАГ 1: ПРЯМОЕ ЧТЕНИЕ DXF")
    try:
        doc = ezdxf.readfile(tank_file)
        modelspace = doc.modelspace()
        entities = list(modelspace)
        
        print(f"Всего сущностей: {len(entities)}")
        
        # Находим габариты первой сущности
        first_entity = None
        for entity in entities:
            try:
                bbox = entity.bbox()
                if bbox:
                    width = bbox.extmax.x - bbox.extmin.x
                    height = bbox.extmax.y - bbox.extmin.y
                    print(f"Первая сущность ({entity.dxftype()}): {width:.2f}×{height:.2f} единиц")
                    first_entity = entity
                    break
            except:
                continue
                
    except Exception as e:
        print(f"❌ Ошибка чтения DXF: {e}")
        return
    
    # ШАГ 2: Конвертация через convert_entity_to_polygon_improved
    print(f"\n🔄 ШАГ 2: КОНВЕРТАЦИЯ В ПОЛИГОН")
    if first_entity:
        try:
            polygon = convert_entity_to_polygon_improved(first_entity)
            if polygon:
                bounds = polygon.bounds
                width = bounds[2] - bounds[0]
                height = bounds[3] - bounds[1]
                print(f"После convert_entity_to_polygon_improved: {width:.2f}×{height:.2f} единиц")
                print(f"Площадь: {polygon.area:.2f}")
                
                # Проверяем, есть ли масштабирование в функции
                print(f"Bounds: {bounds}")
            else:
                print("❌ convert_entity_to_polygon_improved вернул None")
        except Exception as e:
            print(f"❌ Ошибка конвертации: {e}")
            import traceback
            traceback.print_exc()
    
    # ШАГ 3: Полный parse_dxf_complete
    print(f"\n📦 ШАГ 3: ПОЛНЫЙ ПАРСИНГ parse_dxf_complete")
    try:
        result = parse_dxf_complete(tank_file)
        polygons = result['polygons']
        
        if polygons:
            poly = polygons[0]
            bounds = poly.bounds
            width = bounds[2] - bounds[0]
            height = bounds[3] - bounds[1]
            print(f"После parse_dxf_complete: {width:.2f}×{height:.2f} единиц")
            print(f"Площадь: {poly.area:.2f}")
            
            # Проверяем другие результаты parse_dxf_complete
            if 'bounds' in result:
                file_bounds = result['bounds']
                file_width = file_bounds[2] - file_bounds[0]
                file_height = file_bounds[3] - file_bounds[1]
                print(f"Общие габариты файла: {file_width:.2f}×{file_height:.2f}")
                
        else:
            print("❌ parse_dxf_complete не вернул полигоны")
            
    except Exception as e:
        print(f"❌ Ошибка parse_dxf_complete: {e}")
        import traceback
        traceback.print_exc()
    
    # ШАГ 4: Проверяем функции масштабирования в коде
    print(f"\n🔍 ШАГ 4: ПОИСК МАСШТАБИРОВАНИЯ В КОДЕ")
    
    # Ищем все места где может быть масштабирование
    import layout_optimizer
    import inspect
    
    # Проверяем функции, которые могут изменять размер
    functions_to_check = [
        'convert_entity_to_polygon_improved',
        'parse_dxf_complete', 
        'place_polygon_at_origin',
        'scale_polygons_to_fit'
    ]
    
    for func_name in functions_to_check:
        if hasattr(layout_optimizer, func_name):
            func = getattr(layout_optimizer, func_name)
            source = inspect.getsource(func)
            
            # Ищем ключевые слова связанные с масштабированием
            scale_keywords = ['scale', 'Scale', 'SCALE', '*', 'multiply', 'transform', '/10', '*10']
            found_scaling = []
            
            for keyword in scale_keywords:
                if keyword in source:
                    lines = source.split('\n')
                    for i, line in enumerate(lines):
                        if keyword in line:
                            found_scaling.append(f"  Строка {i+1}: {line.strip()}")
            
            if found_scaling:
                print(f"\n⚠️ В функции {func_name} найдено возможное масштабирование:")
                for scale_line in found_scaling[:3]:  # первые 3
                    print(scale_line)
            else:
                print(f"✅ В функции {func_name} масштабирование не найдено")

if __name__ == "__main__":
    trace_scale_issue()