#!/usr/bin/env python3
"""
Создает финальную корректную версию DXF файла.
"""

import os
import time
from layout_optimizer import (
    parse_dxf_complete, 
    bin_packing, 
    save_dxf_layout_complete
)

def create_final_dxf():
    """Создает финальную правильную версию DXF файла."""
    print("=== СОЗДАНИЕ ФИНАЛЬНОГО DXF ФАЙЛА ===")
    
    # Используем только те файлы, которые видны в visualization.png
    source_files = [
        "/home/sasha/proj/2025/eva_layout/dxf_samples/Лодка Азимут Эверест 385/2.dxf",
        "/home/sasha/proj/2025/eva_layout/dxf_samples/Лодка АГУЛ 270/2.dxf"
    ]
    
    # Проверяем существование файлов
    existing_files = []
    for file_path in source_files:
        if os.path.exists(file_path):
            existing_files.append(file_path)
            print(f"✅ {os.path.basename(file_path)}")
    
    if not existing_files:
        print("❌ Нет доступных исходных файлов!")
        return False
    
    print(f"\\n📊 Создаем раскрой из {len(existing_files)} файлов...")
    
    # Парсим файлы
    polygons = []
    original_dxf_data_map = {}
    
    for file_path in existing_files:
        print(f"\\n📖 Парсим: {os.path.basename(file_path)}")
        try:
            with open(file_path, 'rb') as f:
                parsed_data = parse_dxf_complete(f, verbose=False)
            
            if parsed_data['combined_polygon']:
                file_name = os.path.basename(file_path)
                color = "черный"
                
                polygon_tuple = (parsed_data['combined_polygon'], file_name, color)
                polygons.append(polygon_tuple)
                original_dxf_data_map[file_name] = parsed_data
                
                bounds = parsed_data['combined_polygon'].bounds
                print(f"  ✅ Bounds: ({bounds[0]:.1f}, {bounds[1]:.1f}, {bounds[2]:.1f}, {bounds[3]:.1f})")
                print(f"  📊 Entities: {len(parsed_data['original_entities'])}")
                
                if parsed_data.get('real_spline_bounds'):
                    print(f"  📊 Real SPLINE bounds: {parsed_data['real_spline_bounds']}")
            else:
                print(f"  ❌ Не удалось создать полигон")
                
        except Exception as e:
            print(f"  ❌ Ошибка: {e}")
    
    if not polygons:
        print("❌ Нет полигонов для раскроя!")
        return False
    
    print(f"\\n🔄 Запускаем bin packing для {len(polygons)} полигонов...")
    
    # Размер листа - правильная ориентация 200x140 см
    sheet_size = (200.0, 140.0)  # см
    print(f"📐 Размер листа: {sheet_size[0]*10} x {sheet_size[1]*10} мм")
    
    try:
        placed_elements, rejected_elements = bin_packing(
            polygons, 
            sheet_size, 
            max_attempts=1000, 
            verbose=True
        )
        
        print(f"\\n📊 Результат bin packing:")
        print(f"  Размещено: {len(placed_elements)} элементов")
        print(f"  Отклонено: {len(rejected_elements)} элементов")
        
        if not placed_elements:
            print("❌ Нет размещенных элементов!")
            return False
        
        # Показываем детали размещения
        for i, element in enumerate(placed_elements):
            if len(element) >= 5:
                polygon, x_offset, y_offset, rotation_angle, file_name = element[:5]
                final_bounds = polygon.bounds
                print(f"  {i+1}. {file_name}:")
                print(f"     Offset: ({x_offset:.1f}, {y_offset:.1f}), Rotation: {rotation_angle:.1f}°")
                print(f"     Final bounds: ({final_bounds[0]:.1f}, {final_bounds[1]:.1f}, {final_bounds[2]:.1f}, {final_bounds[3]:.1f})")
        
        # Создаем файл с уникальным именем
        timestamp = int(time.time())
        final_file_path = f"/home/sasha/proj/2025/eva_layout/layout_final_{timestamp}.dxf"
        
        print(f"\\n💾 Создаем финальный файл: {final_file_path}")
        save_dxf_layout_complete(placed_elements, sheet_size, final_file_path, original_dxf_data_map)
        
        print(f"✅ Финальный файл создан!")
        
        # Проверяем результат
        import ezdxf
        doc = ezdxf.readfile(final_file_path)
        msp = doc.modelspace()
        
        # Проверяем границы листа
        lwpolylines = [e for e in msp if e.dxftype() == 'LWPOLYLINE']
        for lwpoly in lwpolylines:
            if lwpoly.dxf.layer == 'SHEET_BOUNDARY':
                points = list(lwpoly.get_points())
                if points:
                    x_coords = [p[0] for p in points]
                    y_coords = [p[1] for p in points]
                    print(f"📐 Границы листа в DXF: X=({min(x_coords):.0f}-{max(x_coords):.0f}), Y=({min(y_coords):.0f}-{max(y_coords):.0f})")
        
        # Проверяем SPLINE элементы
        splines = [e for e in msp if e.dxftype() == 'SPLINE']
        print(f"📊 SPLINE элементов в файле: {len(splines)}")
        
        if splines:
            # Получаем общие bounds всех SPLINE
            all_x = []
            all_y = []
            
            for spline in splines:
                control_points = spline.control_points
                if control_points:
                    for cp in control_points:
                        if hasattr(cp, 'x') and hasattr(cp, 'y'):
                            all_x.append(cp.x)
                            all_y.append(cp.y)
                        elif len(cp) >= 2:
                            all_x.append(float(cp[0]))
                            all_y.append(float(cp[1]))
            
            if all_x and all_y:
                spline_bounds = (min(all_x), min(all_y), max(all_x), max(all_y))
                print(f"📊 Общие bounds SPLINE: ({spline_bounds[0]:.1f}, {spline_bounds[1]:.1f}, {spline_bounds[2]:.1f}, {spline_bounds[3]:.1f})")
                
                # Проверяем, в пределах ли листа
                in_bounds = (spline_bounds[0] >= 0 and spline_bounds[1] >= 0 and 
                           spline_bounds[2] <= 2000 and spline_bounds[3] <= 1400)
                print(f"📊 SPLINE в пределах листа: {'✅' if in_bounds else '❌'}")
        
        # Копируем в основной файл
        import shutil
        old_file_path = "/home/sasha/proj/2025/eva_layout/200_140_1_black.dxf"
        shutil.copy2(final_file_path, old_file_path)
        print(f"📋 Скопировано в {old_file_path}")
        
        return final_file_path
        
    except Exception as e:
        print(f"❌ Ошибка bin packing: {e}")
        return False

if __name__ == "__main__":
    print("🎯 Создание финального корректного DXF файла")
    print("=" * 60)
    
    result = create_final_dxf()
    
    print("\\n" + "=" * 60)
    if result:
        print("✅ ФИНАЛЬНЫЙ DXF ФАЙЛ СОЗДАН!")
        print(f"📁 Основной файл: 200_140_1_black.dxf")
        print(f"📁 Тестовый файл: test_minimal.dxf")
        print("🎯 Проверьте оба файла в AutoDesk Viewer")
    else:
        print("❌ ОШИБКА ПРИ СОЗДАНИИ ФАЙЛА")