#!/usr/bin/env python3
"""
Тестируем исправленную работу с файлом TANK 300/4.dxf
"""

import sys
sys.path.insert(0, '.')

import os
from layout_optimizer import parse_dxf_complete

def test_tank4_fixed():
    """Проверяем как теперь работает файл 4.dxf"""
    print("🔍 ТЕСТ TANK 300/4.dxf ПОСЛЕ ИСПРАВЛЕНИЙ")
    print("=" * 60)
    
    tank4_file = "dxf_samples/TANK 300/4.dxf"
    if not os.path.exists(tank4_file):
        print(f"❌ Файл {tank4_file} не найден!")
        return
    
    try:
        result = parse_dxf_complete(tank4_file, verbose=False)
        
        print(f"📊 РЕЗУЛЬТАТ ПАРСИНГА:")
        print(f"  Полигонов для визуализации: {len(result.get('polygons', []))}")
        print(f"  Исходных объектов всего: {len(result.get('original_entities', []))}")
        print(f"  Выбранный слой: {result.get('bottom_layer_name', 'неизвестен')}")
        
        # Подсчитываем элементы в каждом слое с площадями
        layer_info = {}
        for entity_data in result.get('original_entities', []):
            layer = entity_data['layer']
            if layer not in layer_info:
                layer_info[layer] = {'count': 0, 'entities': []}
            layer_info[layer]['count'] += 1
            layer_info[layer]['entities'].append(entity_data)
        
        # Вычисляем площади полигонов по слоям
        from layout_optimizer import convert_entity_to_polygon_improved
        from shapely.ops import unary_union
        
        layer_polygons = {}
        for layer, info in layer_info.items():
            polygons = []
            for entity_data in info['entities']:
                poly = convert_entity_to_polygon_improved(entity_data['entity'])
                if poly and not poly.is_empty:
                    polygons.append(poly)
            
            if polygons:
                if len(polygons) == 1:
                    combined = polygons[0]
                else:
                    combined = unary_union(polygons)
                    if hasattr(combined, 'geoms'):
                        # MultiPolygon - берем самый большой
                        combined = max(combined.geoms, key=lambda p: p.area)
                
                layer_polygons[layer] = combined
                layer_info[layer]['area'] = combined.area
                layer_info[layer]['polygon_count'] = len(polygons)
        
        print(f"\n📋 ИНФОРМАЦИЯ ПО СЛОЯМ:")
        for layer, info in layer_info.items():
            marker = "👑" if layer == result.get('bottom_layer_name') else "  "
            area = info.get('area', 0)
            poly_count = info.get('polygon_count', 0)
            print(f"  {marker} {layer}: {info['count']} объектов → {poly_count} полигонов, площадь: {area:.0f}")
        
        # Итоговый полигон для визуализации
        if result.get('polygons'):
            final_poly = result['polygons'][0] if len(result['polygons']) == 1 else result['polygons']
            if hasattr(final_poly, 'area'):
                final_area = final_poly.area
                bounds = final_poly.bounds
                width = bounds[2] - bounds[0]
                height = bounds[3] - bounds[1]
                print(f"\n🎯 ИТОГОВЫЙ ПОЛИГОН ДЛЯ ВИЗУАЛИЗАЦИИ:")
                print(f"  Размер: {width:.1f}×{height:.1f}")
                print(f"  Площадь: {final_area:.0f}")
        
        # Сравниваем с тем, что было бы при старой логике
        print(f"\n🔄 СРАВНЕНИЕ ЛОГИКИ ВЫБОРА СЛОЯ:")
        
        # Старая логика (первый по порядку)
        old_layer = min(layer_info.keys(), key=lambda l: min(i for i, e in enumerate(result.get('original_entities', [])) if e['layer'] == l))
        old_area = layer_info[old_layer].get('area', 0)
        
        # Новая логика (максимальная площадь)
        new_layer = result.get('bottom_layer_name')
        new_area = layer_info[new_layer].get('area', 0)
        
        print(f"  Старая логика выбрала бы: '{old_layer}' (площадь: {old_area:.0f})")
        print(f"  Новая логика выбрала: '{new_layer}' (площадь: {new_area:.0f})")
        
        if new_area > old_area:
            improvement = new_area / old_area if old_area > 0 else float('inf')
            print(f"  ✅ УЛУЧШЕНИЕ: площадь увеличена в {improvement:.1f} раз!")
        else:
            print(f"  ⚠️ Новая логика выбрала слой с меньшей площадью")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_tank4_fixed()