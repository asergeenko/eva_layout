#!/usr/bin/env python3

"""
Test script to specifically test single-file order processing logic
"""

from shapely.geometry import Polygon
from layout_optimizer import bin_packing_with_inventory

def test_single_file_order_processing():
    """Test that single-file orders are processed correctly"""
    
    # Create test data with mix of multi-file and single-file orders
    available_sheets = [
        {
            "name": "Лист 140x200 чёрный", 
            "width": 140, 
            "height": 200,
            "color": "чёрный", 
            "count": 5, 
            "used": 0,
        },
        {
            "name": "Лист 140x200 серый",
            "width": 140,
            "height": 200, 
            "color": "серый",
            "count": 5,
            "used": 0,
        }
    ]
    
    polygons = []
    
    # Create 3 multi-file orders (with priority constraint)
    for order_num in range(3):
        order_id = f"MULTI_ORDER_{order_num}"
        color = "чёрный" if order_num % 2 == 0 else "серый"
        
        # Each multi-file order has 3 files
        for file_num in range(3):
            filename = f"multi_order_{order_num}_file_{file_num}.dxf"
            width = 80 + file_num * 10
            height = 60 + file_num * 5
            polygon = Polygon([(0, 0), (width, 0), (width, height), (0, height)])
            priority = 1
            polygons.append((polygon, filename, color, order_id, priority))
    
    # Create 10 single-file orders  
    for order_num in range(10):
        order_id = f"SINGLE_ORDER_{order_num}"
        color = "чёрный" if order_num % 2 == 0 else "серый"
        filename = f"single_order_{order_num}.dxf"
        
        # Varying sizes for single orders
        width = 40 + order_num * 5
        height = 30 + order_num * 3
        polygon = Polygon([(0, 0), (width, 0), (width, height), (0, height)])
        priority = 1
        polygons.append((polygon, filename, color, order_id, priority))
    
    print(f"Создано {len(polygons)} полигонов:")
    print("- Multi-file orders: 3 заказа × 3 файла = 9 полигонов")
    print("- Single-file orders: 10 заказов × 1 файл = 10 полигонов")
    

    # Run optimization  
    MAX_SHEETS_PER_ORDER = 3  # Smaller limit to force single-file optimization
    
    placed_layouts, unplaced_polygons = bin_packing_with_inventory(
        polygons,
        available_sheets,
        verbose=False,
        max_sheets_per_order=MAX_SHEETS_PER_ORDER,
    )
    
    # Analyze results
    print("\n=== РЕЗУЛЬТАТЫ ===")
    print(f"Размещенных листов: {len(placed_layouts)}")
    print(f"Неразмещенных полигонов: {len(unplaced_polygons)}")
    
    total_placed = sum(len(layout["placed_polygons"]) for layout in placed_layouts)
    print(f"Всего размещено: {total_placed}/{len(polygons)}")
    
    if placed_layouts:
        print("\nДетали по листам:")
        for layout in placed_layouts:
            print(f"  Лист {layout['sheet_number']}: {len(layout['placed_polygons'])} полигонов, {layout['usage_percent']:.1f}% заполнение")
    
    # Verify that most orders are placed
    placement_rate = total_placed / len(polygons)
    print(f"\nПроцент размещения: {placement_rate*100:.1f}%")
    
    # Should place most orders
    assert placement_rate >= 0.8, f"Низкая эффективность размещения: {placement_rate*100:.1f}%"
    
    # Should create reasonable number of sheets (not too many)
    assert len(placed_layouts) <= 6, f"Слишком много листов создано: {len(placed_layouts)}"
    
    print("✅ Тест обработки одиночных заказов прошел успешно!")
    return placed_layouts, unplaced_polygons

if __name__ == "__main__":
    test_single_file_order_processing()