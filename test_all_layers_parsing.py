#!/usr/bin/env python3
"""
Тестируем новую логику parse_dxf_complete с использованием всех слоев
"""

import sys
sys.path.insert(0, '.')

import os
from layout_optimizer import parse_dxf_complete

def test_all_layers_parsing():
    """Проверяем парсинг всех слоев для TANK файлов"""
    print("🔍 ТЕСТ ПАРСИНГА ВСЕХ СЛОЕВ")
    print("=" * 60)
    
    tank_files = [
        "dxf_samples/TANK 300/1.dxf",
        "dxf_samples/TANK 300/4.dxf"
    ]
    
    for tank_file in tank_files:
        if not os.path.exists(tank_file):
            print(f"❌ Файл {tank_file} не найден!")
            continue
            
        print(f"\n📋 АНАЛИЗ: {os.path.basename(tank_file)}")
        
        try:
            result = parse_dxf_complete(tank_file, verbose=False)
            
            # Подсчитываем исходные объекты по слоям
            layer_entities = {}
            for entity_data in result.get('original_entities', []):
                layer = entity_data['layer']
                layer_entities[layer] = layer_entities.get(layer, 0) + 1
            
            print(f"  Исходных объектов по слоям:")
            total_entities = 0
            for layer, count in layer_entities.items():
                marker = "👑" if layer == result.get('bottom_layer_name') else "  "
                print(f"    {marker} {layer}: {count} объектов")
                total_entities += count
            
            # Полигоны для визуализации
            polygons_count = len(result.get('polygons', []))
            print(f"  Полигонов для визуализации: {polygons_count}")
            print(f"  Главный слой: {result.get('bottom_layer_name', 'неизвестен')}")
            
            # Размеры полигонов
            if result.get('polygons'):
                total_area = sum(p.area for p in result['polygons'])
                print(f"  Общая площадь полигонов: {total_area:.0f}")
                
                # Показываем размеры первых полигонов
                for i, poly in enumerate(result['polygons'][:5]):
                    bounds = poly.bounds
                    width = bounds[2] - bounds[0]
                    height = bounds[3] - bounds[1]
                    print(f"    Полигон {i+1}: {width:.1f}×{height:.1f}, площадь: {poly.area:.0f}")
            
            # Проверяем соответствие
            print(f"\n✅ СООТВЕТСТВИЕ:")
            print(f"  Исходных объектов: {total_entities}")
            print(f"  Полигонов визуализации: {polygons_count}")
            
            if polygons_count >= total_entities * 0.5:  # как минимум половина объектов должна стать полигонами
                print(f"  ✅ ХОРОШЕЕ СООТВЕТСТВИЕ: {polygons_count}/{total_entities} объектов конвертированы")
            else:
                print(f"  ⚠️ НИЗКОЕ СООТВЕТСТВИЕ: {polygons_count}/{total_entities} объектов конвертированы")
                
        except Exception as e:
            print(f"    ❌ Ошибка: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    test_all_layers_parsing()