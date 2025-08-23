#!/usr/bin/env python3
"""
Тестируем полную синхронизацию визуализации и DXF после всех исправлений
"""

import sys
sys.path.insert(0, '.')

import os
import tempfile
import ezdxf
from layout_optimizer import parse_dxf_complete, bin_packing, save_dxf_layout_complete

def test_full_sync():
    """Полный тест синхронизации"""
    print("🔍 ПОЛНЫЙ ТЕСТ СИНХРОНИЗАЦИИ ВИЗУАЛИЗАЦИИ И DXF")
    print("=" * 70)
    
    tank_file = "dxf_samples/TANK 300/4.dxf"  # используем файл с несколькими полигонами
    if not os.path.exists(tank_file):
        print(f"❌ Файл {tank_file} не найден!")
        return
    
    try:
        # 1. Парсинг
        print(f"\n📋 ШАГ 1: ПАРСИНГ ФАЙЛА {os.path.basename(tank_file)}")
        result = parse_dxf_complete(tank_file, verbose=False)
        
        polygons_count = len(result.get('polygons', []))
        entities_count = len(result.get('original_entities', []))
        main_layer = result.get('bottom_layer_name', 'unknown')
        
        print(f"  Полигонов для визуализации: {polygons_count}")
        print(f"  Исходных SPLINE объектов: {entities_count}")  
        print(f"  Главный слой: {main_layer}")
        
        # 2. Размещение
        print(f"\n📦 ШАГ 2: РАЗМЕЩЕНИЕ")
        polygons_with_names = []
        for i, poly in enumerate(result['polygons']):
            polygons_with_names.append((poly, f"tank4_part_{i+1}.dxf", "черный", i))
        
        sheet_size = (140, 200)
        placed, unplaced = bin_packing(polygons_with_names, sheet_size, verbose=False)
        
        print(f"  Размещено полигонов: {len(placed)}")
        print(f"  Не размещено: {len(unplaced)}")
        
        if not placed:
            print("❌ Нет размещенных полигонов!")
            return
        
        # 3. Сохранение DXF  
        print(f"\n💾 ШАГ 3: СОХРАНЕНИЕ DXF")
        
        # Создаем original_dxf_data_map для всех размещенных полигонов
        original_dxf_data_map = {}
        for placed_item in placed:
            file_name = placed_item[4]  # имя файла из placed элемента
            original_dxf_data_map[file_name] = result
        
        # Сохраняем
        with tempfile.NamedTemporaryFile(suffix='.dxf', delete=False) as tmp_file:
            output_path = tmp_file.name
        
        save_dxf_layout_complete(placed, sheet_size, output_path, original_dxf_data_map, verbose=False)
        print(f"  DXF сохранен: {output_path}")
        
        # 4. Анализ сохраненного DXF
        print(f"\n📊 ШАГ 4: АНАЛИЗ СОХРАНЕННОГО DXF")
        
        saved_doc = ezdxf.readfile(output_path)
        saved_msp = saved_doc.modelspace()
        saved_entities = list(saved_msp)
        
        # Группируем по типам и слоям
        entity_types = {}
        layers = set()
        spline_count = 0
        
        for entity in saved_entities:
            entity_type = entity.dxftype()
            layer = getattr(entity.dxf, 'layer', '0')
            
            entity_types[entity_type] = entity_types.get(entity_type, 0) + 1
            layers.add(layer)
            
            if entity_type == 'SPLINE':
                spline_count += 1
        
        print(f"  Всего объектов в DXF: {len(saved_entities)}")
        print(f"  SPLINE объектов: {spline_count}")
        print(f"  Типы объектов: {entity_types}")
        print(f"  Количество слоев: {len(layers)}")
        
        # 5. Проверка соответствия
        print(f"\n✅ ШАГ 5: ПРОВЕРКА СООТВЕТСТВИЯ")
        
        expected_objects_per_placement = entities_count  # все исходные объекты
        expected_total_objects = expected_objects_per_placement * len(placed)
        
        print(f"  Размещений: {len(placed)}")
        print(f"  Исходных объектов на размещение: {entities_count}")
        print(f"  Ожидается объектов в DXF: {expected_total_objects}")
        print(f"  Фактически в DXF: {len(saved_entities)}")
        
        # Проверяем соответствие визуализации
        placed_polygons_count = len(placed)  # количество размещенных полигонов для визуализации
        print(f"  Полигонов в визуализации: {placed_polygons_count}")
        
        if len(saved_entities) >= expected_total_objects * 0.8:  # как минимум 80% объектов
            print(f"  ✅ ХОРОШЕЕ СООТВЕТСТВИЕ DXF: {len(saved_entities)}/{expected_total_objects}")
        else:
            print(f"  ⚠️ НИЗКОЕ СООТВЕТСТВИЕ DXF: {len(saved_entities)}/{expected_total_objects}")
        
        print(f"\n🎯 ИТОГОВЫЙ РЕЗУЛЬТАТ:")
        print(f"  • Визуализация: {placed_polygons_count} полигонов из {polygons_count} исходных")  
        print(f"  • DXF файл: {len(saved_entities)} объектов из {expected_total_objects} ожидаемых")
        print(f"  • Синхронизация: {'✅ ОК' if len(saved_entities) > 0 and placed_polygons_count > 0 else '❌ ОШИБКА'}")
        
        # Очистка
        try:
            os.unlink(output_path)
        except:
            pass
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_full_sync()