#!/usr/bin/env python3

"""
Тест для прямого вызова save_dxf_layout_complete с отладкой IMAGE трансформации
"""

import sys
import os
sys.path.append('.')

from layout_optimizer import (
    parse_dxf_complete, 
    bin_packing_with_inventory,
    save_dxf_layout_complete,
    get_color_for_file
)

def test_direct_save_with_image_debug():
    """Тест прямого сохранения DXF с IMAGE элементами"""
    
    print("=== ТЕСТ ПРЯМОГО СОХРАНЕНИЯ DXF С IMAGE ===")
    
    # Используем настоящие файлы для теста
    sample_files = [
        "dxf_samples/TOYOTA COROLLA VERSO/2.dxf",
        "dxf_samples/ДЕКА KUGOO M4 PRO JILONG/1.dxf",
        "dxf_samples/Лодка АГУЛ 270/2.dxf"
    ]
    
    # Загружаем данные файлов
    original_dxf_data_map = {}
    polygons_for_placement = []
    
    for file_path in sample_files:
        if os.path.exists(file_path):
            try:
                print(f"Загружаем {file_path}...")
                dxf_data = parse_dxf_complete(file_path)
                
                # Проверяем наличие IMAGE сущностей
                image_count = sum(1 for ed in dxf_data['original_entities'] if ed['type'] == 'IMAGE')
                print(f"  Найдено IMAGE сущностей: {image_count}")
                
                if image_count > 0:
                    print(f"  ✅ Файл содержит IMAGE сущности")
                    original_dxf_data_map[file_path] = dxf_data
                    
                    # Добавляем полигон для размещения
                    polygon = dxf_data['combined_polygon']
                    if polygon:
                        color = get_color_for_file(file_path)
                        polygons_for_placement.append((polygon, os.path.basename(file_path), color, f"order_{len(polygons_for_placement)}"))
                else:
                    print(f"  ⚠️  Файл НЕ содержит IMAGE сущности")
            except Exception as e:
                print(f"  Ошибка загрузки {file_path}: {e}")
    
    if not polygons_for_placement:
        print("❌ Не найдено файлов с IMAGE сущностями для теста")
        return
    
    print(f"\nЗагружено {len(polygons_for_placement)} полигонов с IMAGE сущностями")
    
    # Параметры листа (140x200 см)
    sheet_size = (1400, 2000)  # в мм
    
    # Выполняем размещение
    print(f"\nВыполняем размещение на листе {sheet_size[0]/10}x{sheet_size[1]/10} см...")
    
    try:
        # Используем правильные параметры для bin_packing_with_inventory
        available_sheets = [
            {'width': sheet_size[0], 'height': sheet_size[1], 'count': 1, 'used': 0, 'color': 'черный'}
        ]
        
        layouts, unplaced = bin_packing_with_inventory(
            polygons_for_placement,
            available_sheets,
            verbose=True
        )
        if layouts:
            layout = layouts[0]  # Берем первый лист
            
            print(f"\nРазмещение завершено. Полигонов на листе: {len(layout['placed_polygons'])}")
            
            # Вызываем save_dxf_layout_complete с отладкой
            output_file = "test_image_transformation.dxf"
            
            print(f"\nВызываем save_dxf_layout_complete...")
            print(f"  placed_polygons: {len(layout['placed_polygons'])}")
            print(f"  sheet_size: {layout['sheet_size']}")
            print(f"  output_file: {output_file}")
            print(f"  original_dxf_data_map keys: {list(original_dxf_data_map.keys())}")
            
            # ГЛАВНЫЙ ВЫЗОВ - здесь должна сработать отладка IMAGE
            save_dxf_layout_complete(
                layout['placed_polygons'], 
                layout['sheet_size'], 
                output_file, 
                original_dxf_data_map
            )
            
            print(f"\n✅ DXF файл сохранен: {output_file}")
            
            # Проверим созданный файл
            if os.path.exists(output_file):
                print(f"✅ Файл создан успешно")
                
                # Анализируем IMAGE позиции в созданном файле
                import ezdxf
                doc = ezdxf.readfile(output_file)
                msp = doc.modelspace()
                
                image_entities = [e for e in msp if e.dxftype() == 'IMAGE']
                print(f"IMAGE сущностей в результате: {len(image_entities)}")
                
                for i, img in enumerate(image_entities[:3]):
                    if hasattr(img.dxf, 'insert'):
                        pos = img.dxf.insert
                        print(f"  IMAGE {i+1}: позиция ({pos[0]:.1f}, {pos[1]:.1f})")
                        
                        # Проверим, в пределах ли листа
                        if 0 <= pos[0] <= sheet_size[0] and 0 <= pos[1] <= sheet_size[1]:
                            print(f"    ✅ В пределах листа")
                        else:
                            print(f"    ❌ ВНЕ пределов листа! (ожидаемо: 0-{sheet_size[0]}, 0-{sheet_size[1]})")
                            
            else:
                print(f"❌ Файл НЕ создан")
        else:
            print("❌ Размещение не удалось")
    
    except Exception as e:
        print(f"❌ Ошибка выполнения теста: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_direct_save_with_image_debug()