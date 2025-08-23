#!/usr/bin/env python3

import sys
import os
sys.path.append('/home/sasha/proj/2025/eva_layout')

from layout_optimizer import parse_dxf_complete, bin_packing, save_dxf_layout_complete

# Use multiple files to test full layout
test_files = [
    '/home/sasha/proj/2025/eva_layout/dxf_samples/TOYOTA COROLLA 11/1.dxf',
    '/home/sasha/proj/2025/eva_layout/dxf_samples/SSANG YONG REXTON 4/1.dxf',
    '/home/sasha/proj/2025/eva_layout/dxf_samples/VOLKSWAGEN TOUAREG 1/1.dxf',
    '/home/sasha/proj/2025/eva_layout/dxf_samples/VOLVO S80 1/1.dxf',
    '/home/sasha/proj/2025/eva_layout/dxf_samples/SUZUKI XBEE/1.dxf'
]

print("Создание полного DXF файла со всеми SPLINE элементами...")

# Load files and create elements list
elements = []
original_dxf_data_map = {}

for i, file_path in enumerate(test_files):
    if os.path.exists(file_path):
        print(f"Обрабатываем: {os.path.basename(file_path)}")
        # Parse DXF
        result = parse_dxf_complete(file_path, verbose=False)
        polygon = result.get('polygon')
        if polygon and not polygon.is_empty:
            elements.append((polygon, 0.0, 0.0, 0.0, "black", file_path, 1))
            original_dxf_data_map[file_path] = result
        else:
            print(f"  ⚠️ Не удалось создать полигон для {file_path}")

if elements:
    print(f"\nЗагружено {len(elements)} элементов для размещения")
    
    # Run bin packing
    placed_elements, unplaced_elements = bin_packing(elements, (1400, 2000), verbose=True)
    
    if placed_elements:
        print(f"\nРазмещено: {len(placed_elements)} элементов")
        print(f"Не размещено: {len(unplaced_elements)} элементов")
        
        # Save with ALL original elements restored
        save_dxf_layout_complete(placed_elements, (1400, 2000), '200_140_10_black.dxf', original_dxf_data_map)
        print("\n✅ DXF файл создан: 200_140_10_black.dxf")
        print("Теперь проверьте в Autodesk Viewer на наличие наложений")
    else:
        print("❌ Ни один элемент не был размещен")
else:
    print("❌ Нет валидных элементов для размещения")