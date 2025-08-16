#!/usr/bin/env python3

"""
Простой тест для вызова save_dxf_layout_complete с маленькими полигонами
"""

import sys
import os
sys.path.append('.')

from layout_optimizer import (
    parse_dxf_complete, 
    save_dxf_layout_complete
)
from shapely.geometry import Polygon

def test_simple_dxf_save():
    """Простой тест с фиктивными данными"""
    
    print("=== ПРОСТОЙ ТЕСТ СОХРАНЕНИЯ DXF ===")
    
    # Создадим простые фиктивные данные
    small_polygon = Polygon([(0, 0), (100, 0), (100, 50), (0, 50)])
    
    # Загрузим один реальный файл с IMAGE сущностями для original_dxf_data_map
    test_file = "dxf_samples/TOYOTA COROLLA VERSO/2.dxf"
    
    if not os.path.exists(test_file):
        print(f"❌ Тестовый файл не найден: {test_file}")
        return
    
    try:
        print(f"Загружаем {test_file}...")
        dxf_data = parse_dxf_complete(test_file)
        
        # Проверяем наличие IMAGE сущностей
        image_count = sum(1 for ed in dxf_data['original_entities'] if ed['type'] == 'IMAGE')
        print(f"  Найдено IMAGE сущностей: {image_count}")
        
        if image_count == 0:
            print("❌ В файле нет IMAGE сущностей")
            return
        
        # Создаем фиктивные placed_elements
        placed_elements = [
            (small_polygon, 50, 50, 0, test_file)  # (polygon, x_offset, y_offset, rotation_angle, file_name)
        ]
        
        # Создаем original_dxf_data_map
        original_dxf_data_map = {
            test_file: dxf_data
        }
        
        # Параметры листа
        sheet_size = (1400, 2000)  # 140x200 см
        output_file = "test_simple_image_save.dxf"
        
        print(f"\nВызываем save_dxf_layout_complete...")
        print(f"  placed_elements: {len(placed_elements)}")
        print(f"  sheet_size: {sheet_size}")
        print(f"  output_file: {output_file}")
        print(f"  original_dxf_data_map: {list(original_dxf_data_map.keys())}")
        
        # ГЛАВНЫЙ ВЫЗОВ - здесь должна сработать отладка
        save_dxf_layout_complete(
            placed_elements, 
            sheet_size, 
            output_file, 
            original_dxf_data_map
        )
        
        print(f"\n✅ Функция выполнилась")
        
        # Проверим отладочный лог
        if os.path.exists("save_dxf_debug.log"):
            print(f"\n📋 Содержимое save_dxf_debug.log:")
            with open("save_dxf_debug.log", "r", encoding="utf-8") as f:
                content = f.read()
                print(content)
        else:
            print(f"\n❌ Отладочный лог save_dxf_debug.log НЕ создан")
        
        # Проверим созданный файл
        if os.path.exists(output_file):
            print(f"\n✅ DXF файл создан: {output_file}")
            
            # Анализируем IMAGE позиции в созданном файле
            import ezdxf
            doc = ezdxf.readfile(output_file)
            msp = doc.modelspace()
            
            image_entities = [e for e in msp if e.dxftype() == 'IMAGE']
            print(f"IMAGE сущностей в результате: {len(image_entities)}")
            
            for i, img in enumerate(image_entities):
                if hasattr(img.dxf, 'insert'):
                    pos = img.dxf.insert
                    print(f"  IMAGE {i+1}: позиция ({pos[0]:.1f}, {pos[1]:.1f})")
                    
                    # Проверим, в пределах ли листа
                    if 0 <= pos[0] <= sheet_size[0] and 0 <= pos[1] <= sheet_size[1]:
                        print(f"    ✅ В пределах листа")
                    else:
                        print(f"    ❌ ВНЕ пределов листа! (ожидаемо: 0-{sheet_size[0]}, 0-{sheet_size[1]})")
        else:
            print(f"\n❌ DXF файл НЕ создан")
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_simple_dxf_save()