#!/usr/bin/env python3
"""
Детальный анализ одного файла для понимания проблемы
"""

import sys
sys.path.insert(0, '.')

import os
from layout_optimizer import parse_dxf_complete

def analyze_single_file():
    """Анализ одного файла детально"""
    print("🔍 ДЕТАЛЬНЫЙ АНАЛИЗ ОДНОГО ФАЙЛА")
    print("=" * 50)
    
    file_path = "dxf_samples/Лодка АГУЛ 270/2.dxf"
    if not os.path.exists(file_path):
        print(f"❌ Файл {file_path} не найден!")
        return
    
    print(f"📋 Анализируем: {file_path}")
    
    # Парсим файл с подробностями
    result = parse_dxf_complete(file_path, verbose=False)
    
    print(f"\n📊 РЕЗУЛЬТАТЫ ПАРСИНГА:")
    print(f"  Всего исходных элементов: {len(result['original_entities'])}")
    print(f"  Полигонов для визуализации: {len(result['polygons'])}")
    print(f"  Главный слой: {result['bottom_layer_name']}")
    
    if result['combined_polygon']:
        bounds = result['combined_polygon'].bounds
        print(f"  Combined polygon размер: {bounds[2]-bounds[0]:.1f}×{bounds[3]-bounds[1]:.1f}мм")
        print(f"  Combined polygon bounds: {bounds}")
    
    # Анализируем элементы по слоям
    print(f"\n🔍 АНАЛИЗ ЭЛЕМЕНТОВ ПО СЛОЯМ:")
    elements_by_layer = {}
    
    for entity_data in result['original_entities']:
        layer = entity_data['layer']
        entity_type = entity_data['type']
        
        if layer not in elements_by_layer:
            elements_by_layer[layer] = {}
        
        if entity_type not in elements_by_layer[layer]:
            elements_by_layer[layer][entity_type] = 0
        
        elements_by_layer[layer][entity_type] += 1
    
    for layer, types in elements_by_layer.items():
        total = sum(types.values())
        print(f"  {layer}: {total} элементов")
        for entity_type, count in types.items():
            print(f"    {entity_type}: {count}")
    
    # Вычисляем bounds всех SPLINE элементов
    print(f"\n📏 BOUNDS ВСЕХ SPLINE ЭЛЕМЕНТОВ:")
    all_spline_points = []
    spline_by_layer = {}
    
    for entity_data in result['original_entities']:
        if entity_data['type'] == 'SPLINE':
            layer = entity_data['layer']
            entity = entity_data['entity']
            
            if layer not in spline_by_layer:
                spline_by_layer[layer] = []
            
            if hasattr(entity, 'control_points') and entity.control_points:
                layer_points = []
                for cp in entity.control_points:
                    if hasattr(cp, 'x') and hasattr(cp, 'y'):
                        x, y = cp.x, cp.y
                    elif len(cp) >= 2:
                        x, y = float(cp[0]), float(cp[1])
                    else:
                        continue
                    
                    all_spline_points.append((x, y))
                    layer_points.append((x, y))
                
                spline_by_layer[layer].extend(layer_points)
    
    if all_spline_points:
        min_x = min(p[0] for p in all_spline_points)
        max_x = max(p[0] for p in all_spline_points)
        min_y = min(p[1] for p in all_spline_points)
        max_y = max(p[1] for p in all_spline_points)
        
        print(f"  Все SPLINE: {max_x-min_x:.1f}×{max_y-min_y:.1f}мм")
        print(f"  Bounds: ({min_x:.1f}, {min_y:.1f}, {max_x:.1f}, {max_y:.1f})")
    
    # Bounds по слоям
    for layer, points in spline_by_layer.items():
        if points:
            min_x = min(p[0] for p in points)
            max_x = max(p[0] for p in points)
            min_y = min(p[1] for p in points)
            max_y = max(p[1] for p in points)
            
            print(f"  {layer}: {max_x-min_x:.1f}×{max_y-min_y:.1f}мм")
            print(f"    Bounds: ({min_x:.1f}, {min_y:.1f}, {max_x:.1f}, {max_y:.1f})")

if __name__ == "__main__":
    analyze_single_file()