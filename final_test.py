#!/usr/bin/env python3
"""
Финальный тест алгоритма с пользовательскими файлами
"""

import sys
sys.path.insert(0, '.')

import os
import tempfile
from layout_optimizer import (
    parse_dxf_complete, bin_packing_with_inventory, 
    save_dxf_layout_complete, plot_layout
)

def final_test():
    """Финальный тест алгоритма"""
    print("🎯 ФИНАЛЬНЫЙ ТЕСТ АЛГОРИТМА")
    print("=" * 50)
    
    # Используем TANK файлы с несколькими слоями для тестирования
    test_files = [
        "dxf_samples/TANK 300/1.dxf",
        "dxf_samples/TANK 300/4.dxf"
    ]
    
    found_files = [f for f in test_files if os.path.exists(f)]
    print(f"📋 Используем файлы: {len(found_files)}")
    for f in found_files:
        print(f"  • {os.path.basename(f)}")
    
    if len(found_files) < 2:
        print("❌ Недостаточно файлов для тестирования!")
        return
    
    # Парсим файлы
    all_polygons = []
    original_dxf_data_map = {}
    
    print(f"\n📦 ПАРСИНГ И ПОДГОТОВКА")
    for file_path in found_files:
        file_name = os.path.basename(file_path)
        
        result = parse_dxf_complete(file_path, verbose=False)
        if result['polygons']:
            poly = result['polygons'][0]
            all_polygons.append((poly, file_name, "черный", 1))
            original_dxf_data_map[file_name] = result
            
            bounds = poly.bounds
            print(f"  ✅ {file_name}: {bounds[2]-bounds[0]:.1f}×{bounds[3]-bounds[1]:.1f}мм")
    
    # Размещение
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
        print("❌ Размещение не удалось!")
        return
        
    layout = placed_layouts[0]
    placed_polygons = layout['placed_polygons']
    
    print(f"  Размещено: {len(placed_polygons)} объектов")
    print(f"  Не размещено: {len(unplaced)} объектов")
    print(f"  Использование материала: {layout['usage_percent']:.1f}%")
    
    # Проверяем расстояния в визуализации
    print(f"\n📏 РАССТОЯНИЯ В ВИЗУАЛИЗАЦИИ")
    if len(placed_polygons) >= 2:
        p1 = placed_polygons[0][0]  # полигон 1
        p2 = placed_polygons[1][0]  # полигон 2
        
        bounds1 = p1.bounds
        bounds2 = p2.bounds
        
        center1_x = (bounds1[0] + bounds1[2]) / 2
        center1_y = (bounds1[1] + bounds1[3]) / 2
        center2_x = (bounds2[0] + bounds2[2]) / 2  
        center2_y = (bounds2[1] + bounds2[3]) / 2
        
        distance = ((center2_x - center1_x)**2 + (center2_y - center1_y)**2)**0.5
        print(f"  Расстояние между центрами: {distance:.1f}мм")
        
        # Проверяем на наложение
        min_gap = 100  # минимум 10см
        if distance < min_gap:
            print(f"  ❌ ВОЗМОЖНОЕ НАЛОЖЕНИЕ! Расстояние {distance:.1f}мм < {min_gap}мм")
        else:
            print(f"  ✅ Объекты не накладываются")
    
    # Создание DXF
    print(f"\n💾 СОЗДАНИЕ DXF")
    
    layout_dxf_map = {}
    for placed_item in placed_polygons:
        filename = placed_item[4]
        if filename in original_dxf_data_map:
            layout_dxf_map[filename] = original_dxf_data_map[filename]
    
    with tempfile.NamedTemporaryFile(suffix='.dxf', delete=False) as tmp_file:
        output_path = tmp_file.name
    
    save_dxf_layout_complete(
        placed_polygons, 
        (140, 200), 
        output_path, 
        layout_dxf_map, 
        verbose=False
    )
    
    print(f"  DXF создан: {output_path}")
    
    print(f"\n🎉 ТЕСТ ЗАВЕРШЕН")
    print(f"  Файл DXF: {output_path}")
    print(f"  Для проверки откройте в AutoCAD или аналогичном ПО")
    
    # НЕ удаляем файл для проверки пользователем
    # try:
    #     os.unlink(output_path)
    # except:
    #     pass

if __name__ == "__main__":
    final_test()