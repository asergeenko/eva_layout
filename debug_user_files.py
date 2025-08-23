#!/usr/bin/env python3
"""
Диагностика проблем с пользовательскими файлами
"""

import sys
sys.path.insert(0, '.')

import os
import tempfile
import ezdxf
from layout_optimizer import (
    parse_dxf_complete, bin_packing_with_inventory, 
    save_dxf_layout_complete, plot_layout
)

def debug_user_files():
    """Диагностика проблем с пользовательскими файлами"""
    print("🔍 ДИАГНОСТИКА ПОЛЬЗОВАТЕЛЬСКИХ ФАЙЛОВ")
    print("=" * 60)
    
    # Берем файлы соответствующие пользовательскому списку
    target_files = [
        "dxf_samples/Лодка Азимут Эверест 385/2.dxf",
        "dxf_samples/VOLKSWAGEN TIGUAN 2/2.dxf", 
        "dxf_samples/Лодка АГУЛ 270/2.dxf",
        "dxf_samples/SSANG YONG KYRON/1.dxf",
        "dxf_samples/TOYOTA FORTUNER/3.dxf",
        "dxf_samples/Коврик для обуви придверный/1.dxf",
        "dxf_samples/VOLVO S80 1/3.dxf",
        "dxf_samples/VOLKSWAGEN TIGUAN 2/3.dxf"
    ]
    
    # Проверяем какие файлы существуют
    found_files = []
    for file_path in target_files:
        if os.path.exists(file_path):
            found_files.append(file_path)
        else:
            print(f"  ❌ Не найден: {file_path}")
    
    # Если не нашли точные, ищем похожие
    if len(found_files) < 4:
        print("\n🔍 Ищем похожие файлы...")
        for root, dirs, files in os.walk("dxf_samples"):
            folder_name = os.path.basename(root)
            if any(name in folder_name for name in ["Лодка", "VOLKSWAGEN", "SSANG", "TOYOTA", "Коврик", "VOLVO"]):
                for file in files[:3]:  # берем первые 3 файла из папки
                    if file.endswith('.dxf'):
                        full_path = os.path.join(root, file)
                        if full_path not in found_files:
                            found_files.append(full_path)
    
    print(f"📋 Найдено файлов: {len(found_files)}")
    for f in found_files:
        print(f"  • {f}")
    
    if not found_files:
        print("❌ Пользовательские файлы не найдены!")
        return
    
    # Создаем полигоны для размещения
    all_polygons = []
    original_dxf_data_map = {}
    
    print(f"\n📦 ПАРСИНГ ФАЙЛОВ")
    for file_path in found_files:
        file_name = os.path.basename(file_path)
        
        try:
            result = parse_dxf_complete(file_path, verbose=False)
            if result['polygons']:
                poly = result['polygons'][0]  # объединенный полигон
                all_polygons.append((poly, file_name, "черный", 1))
                original_dxf_data_map[file_name] = result
                
                bounds = poly.bounds
                print(f"  ✅ {file_name}: {bounds[2]-bounds[0]:.1f}×{bounds[3]-bounds[1]:.1f}мм")
            else:
                print(f"  ❌ {file_name}: нет полигонов")
        except Exception as e:
            print(f"  ❌ {file_name}: ошибка парсинга - {e}")
    
    print(f"\n  Готово полигонов для размещения: {len(all_polygons)}")
    
    # Размещаем на одном листе 140×200см
    available_sheets = [{
        'name': 'test_sheet',
        'width': 140,
        'height': 200, 
        'count': 1,
        'used': 0,
        'color': 'черный'
    }]
    
    print(f"\n🎯 РАЗМЕЩЕНИЕ НА ЛИСТЕ 140×200см")
    
    placed_layouts, unplaced = bin_packing_with_inventory(
        all_polygons, available_sheets, verbose=False
    )
    
    if not placed_layouts:
        print("❌ Не удалось создать размещение!")
        return
        
    layout = placed_layouts[0]
    placed_polygons = layout['placed_polygons']
    
    print(f"  Размещено объектов: {len(placed_polygons)}")
    print(f"  Не размещено: {len(unplaced)}")
    
    # Анализируем размещение
    print(f"\n📊 АНАЛИЗ РАЗМЕЩЕНИЯ В ВИЗУАЛИЗАЦИИ")
    
    for i, placed_item in enumerate(placed_polygons):
        if len(placed_item) >= 6:
            polygon, x_offset, y_offset, rotation, filename, color = placed_item[:6]
        else:
            polygon, x_offset, y_offset, rotation, filename = placed_item[:5]
            color = 'черный'
        
        bounds = polygon.bounds
        center_x = (bounds[0] + bounds[2]) / 2
        center_y = (bounds[1] + bounds[3]) / 2
        
        print(f"  {i}: {filename}")
        print(f"    Центр: ({center_x:.1f}, {center_y:.1f})")
        print(f"    Поворот: {rotation}°")
        print(f"    Размер: {bounds[2]-bounds[0]:.1f}×{bounds[3]-bounds[1]:.1f}мм")
        print(f"    Offsets: x={x_offset:.1f}, y={y_offset:.1f}")
    
    # Создаем DXF и анализируем
    print(f"\n💾 СОЗДАНИЕ И АНАЛИЗ DXF")
    
    # Готовим данные для DXF
    layout_dxf_map = {}
    for placed_item in placed_polygons:
        filename = placed_item[4]  # имя файла
        if filename in original_dxf_data_map:
            layout_dxf_map[filename] = original_dxf_data_map[filename]
    
    print(f"  Подготовлено данных для {len(layout_dxf_map)} файлов")
    
    # Сохраняем DXF
    with tempfile.NamedTemporaryFile(suffix='.dxf', delete=False) as tmp_file:
        test_output = tmp_file.name
    
    try:
        save_dxf_layout_complete(
            placed_polygons, 
            (140, 200), 
            test_output, 
            layout_dxf_map, 
            verbose=True  # включаем verbose для диагностики
        )
        
        print(f"  DXF создан: {test_output}")
        
        # Анализируем созданный DXF
        saved_doc = ezdxf.readfile(test_output)
        saved_msp = saved_doc.modelspace()
        
        # Группируем элементы по файлам
        elements_by_file = {}
        for entity in saved_msp:
            if entity.dxftype() == 'SPLINE':
                layer = getattr(entity.dxf, 'layer', '0')
                # Извлекаем базовое имя файла из слоя
                file_base = layer.rsplit('_', 1)[0] if '_' in layer else layer
                
                if file_base not in elements_by_file:
                    elements_by_file[file_base] = []
                elements_by_file[file_base].append(entity)
        
        print(f"\n📍 ПОЗИЦИИ В DXF")
        for file_base, entities in elements_by_file.items():
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
                min_x, max_x = min(all_x), max(all_x)
                min_y, max_y = min(all_y), max(all_y)
                center_x = (min_x + max_x) / 2
                center_y = (min_y + max_y) / 2
                width = max_x - min_x
                height = max_y - min_y
                
                print(f"  {file_base}:")
                print(f"    Центр в DXF: ({center_x:.1f}, {center_y:.1f})")
                print(f"    Размер в DXF: {width:.1f}×{height:.1f}мм")
                print(f"    Границы: ({min_x:.1f}, {min_y:.1f}) - ({max_x:.1f}, {max_y:.1f})")
        
    except Exception as e:
        print(f"  ❌ Ошибка создания DXF: {e}")
        import traceback
        traceback.print_exc()
    
    # Очистка
    try:
        os.unlink(test_output)
    except:
        pass

if __name__ == "__main__":
    debug_user_files()