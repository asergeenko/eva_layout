#!/usr/bin/env python3
"""
Проверка реальных размеров полигонов в визуализации
"""

import sys
sys.path.insert(0, '.')

import os
from layout_optimizer import parse_dxf_complete

def debug_polygon_sizes():
    """Проверяем размеры полигонов"""
    print("🔍 ПРОВЕРКА РАЗМЕРОВ ПОЛИГОНОВ")
    print("=" * 50)
    
    tank_files = [
        "dxf_samples/TANK 300/1.dxf",
        "dxf_samples/TANK 300/4.dxf"
    ]
    
    for tank_file in tank_files:
        if not os.path.exists(tank_file):
            print(f"❌ Файл {tank_file} не найден!")
            continue
            
        print(f"\n📋 ФАЙЛ: {os.path.basename(tank_file)}")
        
        result = parse_dxf_complete(tank_file, verbose=False)
        
        print(f"  Полигонов: {len(result['polygons'])}")
        
        for i, poly in enumerate(result['polygons']):
            bounds = poly.bounds
            width = bounds[2] - bounds[0]
            height = bounds[3] - bounds[1]
            area = poly.area
            
            print(f"  Полигон {i}: {width:.1f}×{height:.1f}мм, площадь: {area:.0f}")
            print(f"    Bounds: ({bounds[0]:.1f}, {bounds[1]:.1f}, {bounds[2]:.1f}, {bounds[3]:.1f})")
            
            # Вычисляем адаптивный зазор
            min_gap = max(5.0, min(width, height) * 0.2)
            print(f"    Адаптивный зазор: {min_gap:.1f}мм")

if __name__ == "__main__":
    debug_polygon_sizes()