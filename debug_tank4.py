#!/usr/bin/env python3
"""
Исследуем файл TANK 300/4.dxf который отображается неверно
"""

import sys
sys.path.insert(0, '.')

import os
from layout_optimizer import parse_dxf_complete

def debug_tank4():
    """Сравниваем TANK 1.dxf и 4.dxf"""
    print("🔍 СРАВНЕНИЕ TANK 1.dxf и 4.dxf")
    print("=" * 60)
    
    files_to_check = [
        "dxf_samples/TANK 300/1.dxf",
        "dxf_samples/TANK 300/4.dxf"
    ]
    
    for file_path in files_to_check:
        if not os.path.exists(file_path):
            print(f"❌ Файл {file_path} не найден!")
            continue
            
        print(f"\n📋 АНАЛИЗ: {os.path.basename(file_path)}")
        
        try:
            result = parse_dxf_complete(file_path, verbose=False)
            
            print(f"  Полигонов: {len(result.get('polygons', []))}")
            print(f"  Исходных объектов: {len(result.get('original_entities', []))}")
            print(f"  Слоев: {len(set(e['layer'] for e in result.get('original_entities', [])))}")
            
            # Информация о слоях
            layer_info = {}
            for entity_data in result.get('original_entities', []):
                layer = entity_data['layer']
                if layer not in layer_info:
                    layer_info[layer] = {'count': 0, 'types': set()}
                layer_info[layer]['count'] += 1
                layer_info[layer]['types'].add(entity_data['type'])
            
            for layer, info in layer_info.items():
                print(f"    Слой '{layer}': {info['count']} объектов, типы: {list(info['types'])}")
            
            # Размеры полигонов
            if 'polygons' in result and result['polygons']:
                for i, poly in enumerate(result['polygons']):
                    bounds = poly.bounds
                    width = bounds[2] - bounds[0]
                    height = bounds[3] - bounds[1]
                    print(f"    Полигон {i+1}: {width:.1f}×{height:.1f}, площадь: {poly.area:.0f}")
            
            # Bounds общие
            if 'bounds' in result and result['bounds']:
                bounds = result['bounds']
                total_width = bounds[2] - bounds[0]
                total_height = bounds[3] - bounds[1]
                print(f"    Общие габариты: {total_width:.1f}×{total_height:.1f}")
            
        except Exception as e:
            print(f"    ❌ Ошибка: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    debug_tank4()