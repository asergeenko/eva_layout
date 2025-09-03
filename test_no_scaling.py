#!/usr/bin/env python3

"""
Test without scaling to see if improved filling works
"""

import sys
import importlib

# Force reload of the module to ensure we get the latest version
if 'layout_optimizer' in sys.modules:
    importlib.reload(sys.modules['layout_optimizer'])

from layout_optimizer import bin_packing_with_inventory
from shapely.geometry import Polygon

def test_without_scaling():
    """Test the improved filling algorithm without scaling issues"""
    
    # Sheet size in mm (as used in algorithm)
    available_sheets = [
        {
            "name": "Лист 140x200 чёрный", 
            "width": 1400,  # Already in mm (14cm * 100)
            "height": 2000, # Already in mm (20cm * 100)
            "color": "чёрный", 
            "count": 10,
            "used": 0,
        },
        {
            "name": "Лист 140x200 серый",
            "width": 1400,
            "height": 2000,
            "color": "серый",
            "count": 10,
            "used": 0,
        }
    ]
    
    polygons = []
    
    # Create realistic sized polygons in mm (no scaling needed)
    # Multi-file orders (should create partial filling)
    for i in range(2):
        order_id = f"MULTI_ORDER_{i}"
        color = "чёрный" if i % 2 == 0 else "серый"
        for j in range(3):  # 3 files per order
            filename = f"multi_{i}_{j}.dxf"
            width = 400   # 40mm after proper scaling
            height = 300  # 30mm
            polygon = Polygon([(0, 0), (width, 0), (width, height), (0, height)])
            priority = 1
            polygons.append((polygon, filename, color, order_id, priority))
    
    # Single-file orders (should fill gaps)
    for i in range(8):
        order_id = f"SINGLE_{i}"
        color = "чёрный" if i % 2 == 0 else "серый"
        filename = f"single_{i}.dxf"
        width = 200 + i * 50   # Various sizes
        height = 150 + i * 30  
        polygon = Polygon([(0, 0), (width, 0), (width, height), (0, height)])
        priority = 1
        polygons.append((polygon, filename, color, order_id, priority))
    
    print(f"Создано {len(polygons)} полигонов (без масштабирования)")
    print("Запуск алгоритма...")
    
    placed_layouts, unplaced_polygons = bin_packing_with_inventory(
        polygons,
        available_sheets,
        verbose=True,
        max_sheets_per_order=3,
    )
    
    print(f"\n=== РЕЗУЛЬТАТЫ (без масштабирования) ===")
    print(f"Размещенных листов: {len(placed_layouts)}")
    print(f"Неразмещенных полигонов: {len(unplaced_polygons)}")
    
    total_placed = sum(len(layout["placed_polygons"]) for layout in placed_layouts)
    print(f"Всего размещено: {total_placed}/{len(polygons)}")
    
    if placed_layouts:
        print(f"\nДетали по листам:")
        mixed_sheets = 0
        for layout in placed_layouts:
            usage = layout['usage_percent']
            orders = layout['orders_on_sheet']
            print(f"  Лист {layout['sheet_number']}: {len(layout['placed_polygons'])} полигонов, {usage:.1f}% заполнение")
            print(f"    Заказы: {', '.join(orders)}")
            if len(orders) > 1:
                mixed_sheets += 1
        
        print(f"\nЛистов с несколькими заказами: {mixed_sheets}/{len(placed_layouts)}")
        if mixed_sheets > 0:
            print("✅ УЛУЧШЕННОЕ ЗАПОЛНЕНИЕ РАБОТАЕТ!")
        else:
            print("❌ Улучшенное заполнение не работает")
    
    avg_usage = sum(layout['usage_percent'] for layout in placed_layouts) / len(placed_layouts) if placed_layouts else 0
    print(f"Среднее заполнение: {avg_usage:.1f}%")
    
    return placed_layouts, unplaced_polygons

if __name__ == "__main__":
    test_without_scaling()