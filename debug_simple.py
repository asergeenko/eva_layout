#!/usr/bin/env python3

"""
Very simple debug to understand what's happening
"""

import sys
import importlib

# Force reload of the module to ensure we get the latest version
if 'layout_optimizer' in sys.modules:
    importlib.reload(sys.modules['layout_optimizer'])

from layout_optimizer import bin_packing_with_inventory
from shapely.geometry import Polygon

def simple_debug():
    """Simple debug with just one multi-file and one single-file order"""
    
    # Very simple test case
    available_sheets = [
        {
            "name": "Лист чёрный", 
            "width": 2000,  # Large
            "height": 2000,
            "color": "чёрный", 
            "count": 5,
            "used": 0,
        }
    ]
    
    polygons = []
    
    # One multi-file order
    for i in range(2):
        filename = f"multi_{i}.dxf"
        width = 300
        height = 300
        polygon = Polygon([(0, 0), (width, 0), (width, height), (0, height)])
        priority = 1
        polygons.append((polygon, filename, "чёрный", "MULTI_ORDER", priority))
    
    # One single-file order
    filename = "single.dxf"
    width = 200
    height = 200
    polygon = Polygon([(0, 0), (width, 0), (width, height), (0, height)])
    priority = 1
    polygons.append((polygon, filename, "чёрный", "SINGLE_ORDER", priority))
    
    print(f"=== ПРОСТОЙ ТЕСТ ===")
    print(f"Полигонов: {len(polygons)}")
    print("MULTI_ORDER: multi_0.dxf, multi_1.dxf")  
    print("SINGLE_ORDER: single.dxf")
    print("ОЖИДАНИЕ: 1 лист с 3 полигонами из 2 заказов")
    
    placed_layouts, unplaced_polygons = bin_packing_with_inventory(
        polygons,
        available_sheets,
        verbose=True,  # Enable verbose to trace execution
        max_sheets_per_order=3,
    )
    
    print(f"\n=== РЕЗУЛЬТАТ ===")
    print(f"Листов создано: {len(placed_layouts)}")
    for layout in placed_layouts:
        usage = layout['usage_percent']
        orders = layout['orders_on_sheet']
        polygons_count = len(layout['placed_polygons'])
        
        print(f"Лист {layout['sheet_number']}: {polygons_count} полигонов, {usage:.1f}% заполнение")
        print(f"  Заказы: {', '.join(orders)}")
    
    print(f"Неразмещено: {len(unplaced_polygons)} полигонов")
    
    if len(placed_layouts) == 1:
        layout = placed_layouts[0]
        if len(layout['orders_on_sheet']) > 1:
            print("✅ СМЕШИВАНИЕ ЗАКАЗОВ РАБОТАЕТ")
        else:
            print("❌ СМЕШИВАНИЯ ЗАКАЗОВ НЕТ - только один заказ на листе")
            print(f"  Проблема: ожидали заказы ['MULTI_ORDER', 'SINGLE_ORDER']")
            print(f"  Получили: {layout['orders_on_sheet']}")

if __name__ == "__main__":
    simple_debug()