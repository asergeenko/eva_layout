#!/usr/bin/env python3
"""
Анализ проблемы наложений в DXF файле
"""

import sys
sys.path.insert(0, '.')

import os
import tempfile
import ezdxf
from layout_optimizer import (
    parse_dxf_complete, bin_packing_with_inventory, 
    save_dxf_layout_complete
)

def debug_overlaps_in_dxf():
    """Диагностика наложений в DXF"""
    print("🔍 ДИАГНОСТИКА НАЛОЖЕНИЙ В DXF")
    print("=" * 50)
    
    # Воспроизводим пользовательский тест
    tank_files = [
        "dxf_samples/TANK 300/1.dxf",
        "dxf_samples/TANK 300/2.dxf", 
        "dxf_samples/TANK 300/3.dxf",
        "dxf_samples/TANK 300/4.dxf"
    ]
    
    # Создаем 5 копий (как пользователь)
    all_polygons = []
    original_dxf_data_map = {}
    
    print("📦 СОЗДАНИЕ ДАННЫХ (как в пользовательском тесте)")
    
    for copy_num in range(1, 6):  # 5 копий
        for file_path in tank_files:
            if not os.path.exists(file_path):
                continue
                
            file_name = os.path.basename(file_path)
            copy_name = f"{copy_num}_копия_{file_name}"
            
            # Парсим файл
            result = parse_dxf_complete(file_path, verbose=False)
            if result['polygons']:
                # Добавляем полигоны
                for i, poly in enumerate(result['polygons']):
                    poly_name = f"{copy_name}_poly_{i}"
                    all_polygons.append((poly, poly_name, "черный", copy_num))
                
                # Сохраняем данные для DXF
                original_dxf_data_map[copy_name] = result
    
    print(f"  Всего полигонов: {len(all_polygons)}")
    print(f"  Файлов DXF: {len(original_dxf_data_map)}")
    
    # Создаем листы
    available_sheets = []
    sheet_size = (140, 200)  # 140x200 см
    for i in range(1):  # только 1 лист для анализа
        available_sheets.append({
            'name': f'sheet_{i+1}',
            'width': sheet_size[0],
            'height': sheet_size[1], 
            'count': 1,
            'used': 0,
            'color': 'черный'
        })
    
    print(f"\n🎯 РАЗМЕЩЕНИЕ НА 1 ЛИСТЕ {sheet_size[0]}×{sheet_size[1]}см")
    
    # Размещаем полигоны
    placed_layouts, unplaced = bin_packing_with_inventory(
        all_polygons, available_sheets, verbose=False
    )
    
    if not placed_layouts:
        print("❌ Не удалось создать размещение!")
        return
    
    layout = placed_layouts[0]
    placed_polygons = layout['placed_polygons']
    
    print(f"  Размещено объектов: {len(placed_polygons)}")
    
    # Анализируем размещение в визуализации
    print(f"\n📊 АНАЛИЗ РАЗМЕЩЕНИЯ В ВИЗУАЛИЗАЦИИ")
    
    placed_info = []
    for i, placed_item in enumerate(placed_polygons):
        # Формат может быть разным - проверяем длину
        if len(placed_item) >= 6:
            polygon, x_offset, y_offset, rotation, filename, color = placed_item[:6]
        else:
            polygon, x_offset, y_offset, rotation, filename = placed_item[:5]
            color = 'черный'
        
        # Вычисляем центр полигона в размещении
        bounds = polygon.bounds
        center_x = (bounds[0] + bounds[2]) / 2
        center_y = (bounds[1] + bounds[3]) / 2
        
        placed_info.append({
            'index': i,
            'filename': filename,
            'center': (center_x, center_y),
            'bounds': bounds,
            'size': (bounds[2] - bounds[0], bounds[3] - bounds[1])
        })
        
        print(f"  Объект {i}: {filename}")
        print(f"    Центр: ({center_x:.1f}, {center_y:.1f})")
        print(f"    Размер: {bounds[2] - bounds[0]:.1f}×{bounds[3] - bounds[1]:.1f}мм")
    
    # Проверяем расстояния между объектами в визуализации
    print(f"\n📏 РАССТОЯНИЯ В ВИЗУАЛИЗАЦИИ")
    for i in range(len(placed_info)):
        for j in range(i + 1, len(placed_info)):
            obj1 = placed_info[i]
            obj2 = placed_info[j]
            
            distance = ((obj2['center'][0] - obj1['center'][0])**2 + 
                       (obj2['center'][1] - obj1['center'][1])**2)**0.5
            
            print(f"  {obj1['filename']} ↔ {obj2['filename']}: {distance:.1f}мм")
            
            if distance < 200:  # меньше 20см
                print(f"    ⚠️ БЛИЗКО! Может быть наложение")
    
    # Создаем DXF и анализируем
    print(f"\n💾 СОЗДАНИЕ И АНАЛИЗ DXF")
    
    # Создаем original_dxf_data_map для размещенных объектов
    layout_dxf_map = {}
    for placed_item in placed_polygons:
        poly_name = placed_item[4]  # имя полигона
        
        # Извлекаем исходное имя файла
        if '_poly_' in poly_name:
            base_name = poly_name.split('_poly_')[0]
            if base_name in original_dxf_data_map:
                layout_dxf_map[poly_name] = original_dxf_data_map[base_name]
    
    # Сохраняем DXF
    with tempfile.NamedTemporaryFile(suffix='.dxf', delete=False) as tmp_file:
        test_output = tmp_file.name
    
    save_dxf_layout_complete(
        placed_polygons, 
        sheet_size, 
        test_output, 
        layout_dxf_map, 
        verbose=False
    )
    
    # Анализируем созданный DXF
    saved_doc = ezdxf.readfile(test_output)
    saved_msp = saved_doc.modelspace()
    
    # Группируем элементы по файлам
    elements_by_file = {}
    for entity in saved_msp:
        if entity.dxftype() == 'SPLINE':
            layer = getattr(entity.dxf, 'layer', '0')
            file_part = layer.split('_')[0] + '_' + layer.split('_')[1] + '_' + layer.split('_')[2] + '.dxf'  # например "1_копия_1.dxf"
            
            if file_part not in elements_by_file:
                elements_by_file[file_part] = []
            elements_by_file[file_part].append(entity)
    
    print(f"  Файлов в DXF: {len(elements_by_file)}")
    
    # Анализируем позиции файлов в DXF
    print(f"\n📍 ПОЗИЦИИ ФАЙЛОВ В DXF")
    
    file_centers = {}
    for file_name, entities in elements_by_file.items():
        all_x, all_y = [], []
        
        for entity in entities:
            if hasattr(entity, 'control_points') and entity.control_points:
                for cp in entity.control_points:
                    if hasattr(cp, 'x'):
                        all_x.append(cp.x)
                        all_y.append(cp.y)
                    else:
                        all_x.append(cp[0])
                        all_y.append(cp[1])
        
        if all_x and all_y:
            center_x = (min(all_x) + max(all_x)) / 2
            center_y = (min(all_y) + max(all_y)) / 2
            width = max(all_x) - min(all_x)
            height = max(all_y) - min(all_y)
            
            file_centers[file_name] = (center_x, center_y)
            
            print(f"  {file_name}:")
            print(f"    Центр в DXF: ({center_x:.1f}, {center_y:.1f})")
            print(f"    Размер в DXF: {width:.1f}×{height:.1f}мм")
    
    # Проверяем расстояния в DXF
    print(f"\n📏 РАССТОЯНИЯ В DXF")
    file_list = list(file_centers.keys())
    for i in range(len(file_list)):
        for j in range(i + 1, len(file_list)):
            file1 = file_list[i]
            file2 = file_list[j]
            
            center1 = file_centers[file1]
            center2 = file_centers[file2]
            
            distance = ((center2[0] - center1[0])**2 + 
                       (center2[1] - center1[1])**2)**0.5
            
            print(f"  {file1} ↔ {file2}: {distance:.1f}мм")
            
            if distance < 100:  # меньше 10см
                print(f"    🚨 НАЛОЖЕНИЕ В DXF!")
    
    # Очистка
    try:
        os.unlink(test_output)
    except:
        pass

if __name__ == "__main__":
    debug_overlaps_in_dxf()