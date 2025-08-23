#!/usr/bin/env python3
"""
Исследуем как parse_dxf_complete фильтрует полигоны по слоям
"""

import sys
sys.path.insert(0, '.')

import ezdxf
from layout_optimizer import convert_entity_to_polygon_improved
import os
from collections import defaultdict

def debug_layers():
    """Исследуем слои и их полигоны"""
    print("🔍 ОТЛАДКА СЛОЕВ В TANK FILE")
    print("=" * 60)
    
    tank_file = "dxf_samples/TANK 300/1.dxf"
    if not os.path.exists(tank_file):
        print(f"❌ Файл {tank_file} не найден!")
        return
    
    try:
        doc = ezdxf.readfile(tank_file)
        modelspace = doc.modelspace()
        
        layer_polygons = defaultdict(list)
        layer_entities = defaultdict(list)
        layer_appearance_order = {}
        
        print(f"\n📋 АНАЛИЗ ОБЪЕКТОВ ПО СЛОЯМ:")
        
        # Первый проход - группируем по слоям
        for i, entity in enumerate(modelspace):
            entity_type = entity.dxftype()
            layer = getattr(entity.dxf, 'layer', '0')
            
            layer_entities[layer].append({
                'entity': entity,
                'type': entity_type,
                'index': i
            })
            
            if layer not in layer_appearance_order:
                layer_appearance_order[layer] = i
                
            polygon = convert_entity_to_polygon_improved(entity)
            if polygon and not polygon.is_empty:
                layer_polygons[layer].append(polygon)
        
        print(f"Найдено слоев: {len(layer_entities)}")
        for layer_name in sorted(layer_entities.keys()):
            entities = layer_entities[layer_name]
            polygons = layer_polygons[layer_name]
            appearance = layer_appearance_order.get(layer_name, 'N/A')
            
            print(f"\n  СЛОЙ '{layer_name}' (появился на позиции {appearance}):")
            print(f"    Объектов: {len(entities)}")
            print(f"    Валидных полигонов: {len(polygons)}")
            
            # Размеры полигонов в этом слое
            if polygons:
                total_area = sum(p.area for p in polygons)
                all_x = []
                all_y = []
                for poly in polygons:
                    bounds = poly.bounds
                    all_x.extend([bounds[0], bounds[2]])
                    all_y.extend([bounds[1], bounds[3]])
                
                layer_width = max(all_x) - min(all_x)
                layer_height = max(all_y) - min(all_y)
                print(f"    Габариты слоя: {layer_width:.3f}×{layer_height:.3f}")
                print(f"    Общая площадь: {total_area:.1f}")
                
                # Показываем размеры первых полигонов
                for j, poly in enumerate(polygons[:3]):
                    bounds = poly.bounds
                    width = bounds[2] - bounds[0]
                    height = bounds[3] - bounds[1]
                    print(f"      Полигон {j+1}: {width:.3f}×{height:.3f}")
            
            # Типы объектов в слое
            entity_types = {}
            for entity_data in entities:
                et = entity_data['type']
                entity_types[et] = entity_types.get(et, 0) + 1
            
            print(f"    Типы объектов: {entity_types}")
        
        # Определяем outer_layer так же, как в parse_dxf_complete
        print(f"\n🎯 ЛОГИКА ВЫБОРА OUTER LAYER:")
        
        bottom_layer = None
        min_appearance = float('inf')
        for layer_name, polygons in layer_polygons.items():
            if polygons and layer_appearance_order.get(layer_name, float('inf')) < min_appearance:
                min_appearance = layer_appearance_order[layer_name]
                bottom_layer = layer_name
        
        outer_layer = bottom_layer
        
        print(f"Выбранный outer_layer: '{outer_layer}' (позиция: {min_appearance})")
        
        if outer_layer and layer_polygons[outer_layer]:
            selected_polygons = layer_polygons[outer_layer]
            print(f"Полигонов в выбранном слое: {len(selected_polygons)}")
            
            # Размеры выбранного слоя
            if selected_polygons:
                all_x = []
                all_y = []
                for poly in selected_polygons:
                    bounds = poly.bounds
                    all_x.extend([bounds[0], bounds[2]])
                    all_y.extend([bounds[1], bounds[3]])
                
                selected_width = max(all_x) - min(all_x)
                selected_height = max(all_y) - min(all_y)
                print(f"Габариты выбранного слоя: {selected_width:.3f}×{selected_height:.3f}")
        
        print(f"\n💡 ВЫВОД:")
        print(f"parse_dxf_complete выбирает только слой '{outer_layer}', игнорируя остальные слои!")
        print(f"Поэтому объекты кажутся маленькими - берется только часть всего DXF файла!")
                
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_layers()