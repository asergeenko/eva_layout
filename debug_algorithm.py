#!/usr/bin/env python3

"""
Debug script to understand current algorithm behavior
"""

import sys
import importlib

# Force reload of the module to ensure we get the latest version
if 'layout_optimizer' in sys.modules:
    importlib.reload(sys.modules['layout_optimizer'])

from layout_optimizer import bin_packing_with_inventory
from shapely.geometry import Polygon

def debug_current_algorithm():
    """Debug current algorithm step by step"""
    
    # Very simple test case
    available_sheets = [
        {
            "name": "Лист чёрный", 
            "width": 1000,
            "height": 1000,
            "color": "чёрный", 
            "count": 5,
            "used": 0,
        }
    ]
    
    polygons = []
    
    # Create one multi-file order
    for i in range(2):  # Only 2 files
        filename = f"multi_file_{i}.dxf"
        width = 200  # Small
        height = 200  
        polygon = Polygon([(0, 0), (width, 0), (width, height), (0, height)])
        priority = 1
        polygons.append((polygon, filename, "чёрный", "MULTI_ORDER", priority))
    
    # Create single-file orders that should fill gaps
    for i in range(3):
        filename = f"single_{i}.dxf"
        width = 100  # Very small
        height = 100  
        polygon = Polygon([(0, 0), (width, 0), (width, height), (0, height)])
        priority = 1
        polygons.append((polygon, filename, "чёрный", f"SINGLE_ORDER_{i}", priority))
    
    print(f"=== ВХОДНЫЕ ДАННЫЕ ===")
    print(f"Полигонов: {len(polygons)}")
    print("MULTI_ORDER: 2 файла")  
    print("SINGLE_ORDER_0, SINGLE_ORDER_1, SINGLE_ORDER_2: по 1 файлу")
    print("Все чёрного цвета, размеры позволяют разместиться на одном листе")
    
    print(f"\n=== АНАЛИЗ ЗАКАЗОВ ПЕРЕД ЗАПУСКОМ ===")
    # Group polygons by order to understand structure  
    orders_analysis = {}
    for polygon, filename, color, order_id, priority in polygons:
        if order_id not in orders_analysis:
            orders_analysis[order_id] = []
        orders_analysis[order_id].append((filename, color))
    
    for order_id, files in orders_analysis.items():
        file_count = len(files)
        colors = list(set(f[1] for f in files))
        print(f"Заказ {order_id}: {file_count} файлов, цвета: {colors}")
    
    placed_layouts, unplaced_polygons = bin_packing_with_inventory(
        polygons,
        available_sheets,
        verbose=True,  # Enable verbose logging
        max_sheets_per_order=3,
    )
    
    print(f"\n=== АНАЛИЗ РЕЗУЛЬТАТА ===")
    print(f"Листов создано: {len(placed_layouts)}")
    for layout in placed_layouts:
        usage = layout['usage_percent']
        orders = layout['orders_on_sheet']
        polygons_count = len(layout['placed_polygons'])
        
        print(f"Лист {layout['sheet_number']}: {polygons_count} полигонов, {usage:.1f}% заполнение")
        print(f"  Заказы: {', '.join(orders)}")
        
        # Analyze if there's room for more
        if usage < 50:
            print(f"  ⚠️  НЕДОЗАПОЛНЕН: {100-usage:.1f}% свободного места!")
    
    print(f"\nНеразмещено: {len(unplaced_polygons)} полигонов")
    
    # Expected vs actual
    print(f"\n=== ОЖИДАНИЕ vs ФАКТ ===")
    print("ОЖИДАНИЕ: 1 лист с 5 полигонами из 4 заказов (~40% заполнение)")
    print(f"ФАКТ: {len(placed_layouts)} листов")
    
    if len(placed_layouts) == 1:
        layout = placed_layouts[0]
        if len(layout['orders_on_sheet']) > 1:
            print("✅ СМЕШИВАНИЕ ЗАКАЗОВ РАБОТАЕТ")
        else:
            print("❌ СМЕШИВАНИЯ ЗАКАЗОВ НЕТ")
    else:
        print("❌ СОЗДАНО СЛИШКОМ МНОГО ЛИСТОВ")

if __name__ == "__main__":
    debug_current_algorithm()