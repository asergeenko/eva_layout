#!/usr/bin/env python3

"""
Создание исправленного DXF файла с правильной IMAGE трансформацией
"""

import sys
import os
sys.path.append('.')

from layout_optimizer import (
    parse_dxf_complete, 
    bin_packing_with_inventory,
    save_dxf_layout_complete
)
from shapely.geometry import Polygon

def create_fixed_dxf():
    """Создание DXF с исправленной IMAGE трансформацией"""
    
    print("=== СОЗДАНИЕ ИСПРАВЛЕННОГО DXF ===")
    
    # Используем те же файлы, что и в оригинальном 200_140_1_black.dxf
    sample_files = [
        "dxf_samples/Лодка Азимут Эверест 385/2.dxf",
        "dxf_samples/Лодка АГУЛ 270/2.dxf", 
        "dxf_samples/TOYOTA COROLLA VERSO/2.dxf",
        "dxf_samples/ДЕКА KUGOO M4 PRO JILONG/1.dxf"
    ]
    
    # Загружаем DXF данные
    original_dxf_data_map = {}
    polygons_for_placement = []
    
    for file_path in sample_files:
        if os.path.exists(file_path):
            try:
                print(f"Загружаем {file_path}...")
                dxf_data = parse_dxf_complete(file_path)
                
                # Проверяем наличие IMAGE сущностей
                image_count = sum(1 for ed in dxf_data['original_entities'] if ed['type'] == 'IMAGE')
                spline_count = sum(1 for ed in dxf_data['original_entities'] if ed['type'] == 'SPLINE')
                print(f"  IMAGE: {image_count}, SPLINE: {spline_count}")
                
                original_dxf_data_map[file_path] = dxf_data
                
                # Добавляем полигон
                polygon = dxf_data['combined_polygon']
                if polygon:
                    color = "черный"
                    order_id = f"order_{len(polygons_for_placement)}"
                    polygons_for_placement.append((polygon, os.path.basename(file_path), color, order_id))
                    
            except Exception as e:
                print(f"  ❌ Ошибка: {e}")
        else:
            print(f"  ❌ Файл не найден: {file_path}")
    
    if not polygons_for_placement:
        print("❌ Нет полигонов для размещения")
        return
    
    print(f"\n✅ Подготовлено {len(polygons_for_placement)} полигонов")
    
    # Выполняем размещение на листе 140x200 см
    sheet_size = (140, 200)  # в сантиметрах - bin_packing конвертирует в мм внутри
    available_sheets = [
        {'width': sheet_size[0], 'height': sheet_size[1], 'count': 1, 'used': 0, 'color': 'черный', 'name': '140x200'}
    ]
    
    print(f"\nВыполняем размещение...")
    try:
        layouts, unplaced = bin_packing_with_inventory(
            polygons_for_placement,
            available_sheets,
            verbose=True
        )
        
        if layouts:
            layout = layouts[0]
            print(f"✅ Размещено {len(layout['placed_polygons'])} полигонов")
            
            # Создаем исправленный DXF файл
            output_file = "200_140_1_black_FIXED.dxf"
            
            print(f"\nСохраняем исправленный DXF: {output_file}")
            save_dxf_layout_complete(
                layout['placed_polygons'], 
                layout['sheet_size'], 
                output_file, 
                original_dxf_data_map
            )
            
            print(f"✅ Исправленный DXF сохранен: {output_file}")
            
            # Анализируем результат
            import ezdxf
            doc = ezdxf.readfile(output_file)
            msp = doc.modelspace()
            
            image_entities = [e for e in msp if e.dxftype() == 'IMAGE']
            spline_entities = [e for e in msp if e.dxftype() == 'SPLINE']
            
            print(f"\n📊 Анализ результата:")
            print(f"  IMAGE сущностей: {len(image_entities)}")
            print(f"  SPLINE сущностей: {len(spline_entities)}")
            
            # Проверяем координаты IMAGE
            in_bounds_count = 0
            for i, img in enumerate(image_entities):
                if hasattr(img.dxf, 'insert'):
                    pos = img.dxf.insert
                    
                    if 0 <= pos[0] <= sheet_size[0] and 0 <= pos[1] <= sheet_size[1]:
                        in_bounds_count += 1
                        status = "✅"
                    else:
                        status = "❌"
                    
                    print(f"  IMAGE {i+1}: {status} ({pos[0]:.1f}, {pos[1]:.1f})")
            
            print(f"\n🎯 Результат:")
            print(f"  IMAGE в пределах листа: {in_bounds_count}/{len(image_entities)}")
            
            if in_bounds_count > len(image_entities) // 2:
                print(f"🎉 Большинство IMAGE в правильных координатах!")
                print(f"\n📝 Теперь замените файл:")
                print(f"  cp {output_file} 200_140_1_black.dxf")
                print(f"  Затем проверьте autodesk.png")
            else:
                print(f"⚠️  Все еще есть проблемы с IMAGE координатами")
                
        else:
            print("❌ Размещение не удалось")
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    create_fixed_dxf()