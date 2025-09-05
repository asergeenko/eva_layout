#!/usr/bin/env python3

"""
Test the algorithm directly to see if our improvements work
This bypasses Streamlit completely
"""

import sys
import importlib

# Force reload of the module to ensure we get the latest version
if 'layout_optimizer' in sys.modules:
    importlib.reload(sys.modules['layout_optimizer'])

from layout_optimizer import bin_packing_with_inventory
from shapely.geometry import Polygon

def test_direct_algorithm():
    """Test the improved filling algorithm directly"""
    
    # Simple test with bigger polygons that should create more realistic filling percentages
    available_sheets = [
        {
            "name": "Лист 140x200 чёрный", 
            "width": 140, 
            "height": 200,
            "color": "чёрный", 
            "count": 10,
            "used": 0,
        },
        {
            "name": "Лист 140x200 серый",
            "width": 140,
            "height": 200, 
            "color": "серый",
            "count": 10,
            "used": 0,
        }
    ]
    
    # Create polygons that should create partially filled sheets (to test our improved filling)
    polygons = []
    
    # First batch - should fill first sheet partially
    for i in range(3):
        order_id = "ORDER_A"
        color = "чёрный" 
        filename = f"part_A_{i}.dxf"
        # Medium size - should partially fill sheet
        width = 60  
        height = 80
        polygon = Polygon([(0, 0), (width, 0), (width, height), (0, height)])
        priority = 1
        polygons.append((polygon, filename, color, order_id, priority))
    
    # Second batch - different color, should also partially fill
    for i in range(4):
        order_id = "ORDER_B"
        color = "серый"
        filename = f"part_B_{i}.dxf"
        width = 50
        height = 70
        polygon = Polygon([(0, 0), (width, 0), (width, height), (0, height)])
        priority = 1
        polygons.append((polygon, filename, color, order_id, priority))
    
    # Third batch - should fill gaps if our algorithm works
    for i in range(6):
        order_id = f"ORDER_C_{i}"  # Single file orders
        color = "чёрный" if i % 2 == 0 else "серый"
        filename = f"single_{i}.dxf"
        width = 30 + i * 5
        height = 40 + i * 3
        polygon = Polygon([(0, 0), (width, 0), (width, height), (0, height)])
        priority = 1
        polygons.append((polygon, filename, color, order_id, priority))
    
    print(f"Создано {len(polygons)} полигонов для прямого тестирования")
    print("Запуск алгоритма с verbose=True для детального анализа...")
    
    # Test with MAX_SHEETS_PER_ORDER constraint
    MAX_SHEETS_PER_ORDER = 3
    
    placed_layouts, unplaced_polygons = bin_packing_with_inventory(
        polygons,
        available_sheets,
        verbose=True,  # Enable verbose to see our improvements in action
        max_sheets_per_order=MAX_SHEETS_PER_ORDER,
    )
    
    print("\n=== РЕЗУЛЬТАТЫ ПРЯМОГО ТЕСТИРОВАНИЯ ===")
    print(f"Размещенных листов: {len(placed_layouts)}")
    print(f"Неразмещенных полигонов: {len(unplaced_polygons)}")
    
    if placed_layouts:
        print("\nДетали по листам:")
        for layout in placed_layouts:
            print(f"  Лист {layout['sheet_number']}: {len(layout['placed_polygons'])} полигонов, {layout['usage_percent']:.1f}% заполнение")
            print(f"    Заказы: {', '.join(layout['orders_on_sheet'])}")
    
    if unplaced_polygons:
        print(f"\n❌ НЕРАЗМЕЩЕННЫЕ ({len(unplaced_polygons)}):")
        for unplaced in unplaced_polygons:
            if len(unplaced) >= 4:
                polygon, name, color, order_id = unplaced[:4]
                print(f"  • {name} (цвет: {color}, заказ: {order_id})")
    else:
        print("\n✅ ВСЕ ПОЛИГОНЫ РАЗМЕЩЕНЫ!")
    
    # Check if our improvements are working
    total_polygons = len(polygons)
    placed_polygons = sum(len(layout["placed_polygons"]) for layout in placed_layouts)
    
    print("\n=== ПРОВЕРКА УЛУЧШЕНИЙ ===")
    print(f"Размещение: {placed_polygons}/{total_polygons} ({placed_polygons/total_polygons*100:.1f}%)")
    
    # Look for evidence of improved filling
    if placed_layouts:
        avg_usage = sum(layout['usage_percent'] for layout in placed_layouts) / len(placed_layouts)
        print(f"Среднее заполнение листов: {avg_usage:.1f}%")
        
        # Check if we have mixed orders on sheets (sign of improved filling)
        mixed_order_sheets = [layout for layout in placed_layouts if len(layout['orders_on_sheet']) > 1]
        print(f"Листов с несколькими заказами: {len(mixed_order_sheets)} из {len(placed_layouts)}")
        
        if mixed_order_sheets:
            print("✅ УЛУЧШЕННОЕ ЗАПОЛНЕНИЕ РАБОТАЕТ - есть листы с несколькими заказами")
        else:
            print("❌ Улучшенное заполнение не активно - каждый лист содержит только один заказ")
    
    return placed_layouts, unplaced_polygons

if __name__ == "__main__":
    test_direct_algorithm()