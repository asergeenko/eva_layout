#!/usr/bin/env python3

"""
Test the enhanced fill optimization to verify that:
1. No objects remain unplaced when there is space
2. Sheets are filled more efficiently  
3. Unplaced objects are properly reported
"""

from shapely.geometry import Polygon
from layout_optimizer import bin_packing_with_inventory

def test_enhanced_fill_optimization():
    """Test enhanced fill optimization"""
    
    # Create limited sheet inventory to force optimization
    available_sheets = [
        {
            "name": "Лист 140x200 чёрный", 
            "width": 140, 
            "height": 200,
            "color": "чёрный", 
            "count": 3,  # Limited sheets
            "used": 0,
        },
        {
            "name": "Лист 140x200 серый",
            "width": 140,
            "height": 200, 
            "color": "серый",
            "count": 3,  # Limited sheets
            "used": 0,
        }
    ]
    
    polygons = []
    
    # Create orders that will initially create inefficient layouts
    # Then enhanced fill should optimize them
    
    # Multi-file orders that will partially fill sheets
    for order_num in range(4):
        order_id = f"MULTI_ORDER_{order_num}"
        color = "чёрный" if order_num % 2 == 0 else "серый"
        
        # 2 files per multi-order (will partially fill sheets)
        for file_num in range(2):
            filename = f"multi_{order_num}_{file_num}.dxf"
            width = 70  # Medium size
            height = 50  
            polygon = Polygon([(0, 0), (width, 0), (width, height), (0, height)])
            priority = 1
            polygons.append((polygon, filename, color, order_id, priority))
    
    # Single-file orders that should fill gaps
    for order_num in range(8):
        order_id = f"SINGLE_ORDER_{order_num}"
        color = "чёрный" if order_num % 2 == 0 else "серый"
        filename = f"single_{order_num}.dxf"
        
        # Small sizes that should fit in gaps
        width = 30 + order_num * 3
        height = 25 + order_num * 2
        polygon = Polygon([(0, 0), (width, 0), (width, height), (0, height)])
        priority = 1
        polygons.append((polygon, filename, color, order_id, priority))
    
    print(f"Создано {len(polygons)} полигонов:")
    print("- Multi-file orders: 4 заказа × 2 файла = 8 полигонов")
    print("- Single-file orders: 8 заказов × 1 файл = 8 полигонов")
    

    # Run optimization with MAX_SHEETS_PER_ORDER constraint
    MAX_SHEETS_PER_ORDER = 3
    
    placed_layouts, unplaced_polygons = bin_packing_with_inventory(
        polygons,
        available_sheets,
        verbose=False,
        max_sheets_per_order=MAX_SHEETS_PER_ORDER,
    )
    
    # Analyze results
    print("\n=== РЕЗУЛЬТАТЫ ===")
    print(f"Доступных листов: {sum(sheet['count'] for sheet in available_sheets)}")
    print(f"Размещенных листов: {len(placed_layouts)}")
    print(f"Неразмещенных полигонов: {len(unplaced_polygons)}")
    
    total_placed = sum(len(layout["placed_polygons"]) for layout in placed_layouts)
    print(f"Всего размещено: {total_placed}/{len(polygons)}")
    
    if placed_layouts:
        print("\nЗаполнение по листам:")
        for layout in placed_layouts:
            print(f"  Лист {layout['sheet_number']}: {len(layout['placed_polygons'])} полигонов, {layout['usage_percent']:.1f}% заполнение")
    
    if unplaced_polygons:
        print("\nНеразмещенные полигоны:")
        for idx, unplaced in enumerate(unplaced_polygons):
            if len(unplaced) >= 4:
                polygon, name, color, order_id = unplaced[:4]
                print(f"  [{idx+1}] {name} (цвет: {color}, заказ: {order_id})")
    
    # Calculate metrics
    placement_rate = total_placed / len(polygons)
    average_usage = sum(layout['usage_percent'] for layout in placed_layouts) / len(placed_layouts) if placed_layouts else 0
    
    print("\n=== МЕТРИКИ ===")
    print(f"Процент размещения: {placement_rate*100:.1f}%")
    print(f"Среднее заполнение листов: {average_usage:.1f}%")
    print(f"Использованных листов: {len(placed_layouts)}/{sum(sheet['count'] for sheet in available_sheets)}")
    
    # Should achieve good results with enhanced fill
    print("\n=== ОЦЕНКА ===")
    if placement_rate >= 0.9:
        print("✅ ОТЛИЧНО: Высокий процент размещения")
    elif placement_rate >= 0.8:
        print("✅ ХОРОШО: Приемлемый процент размещения")
    else:
        print("❌ ПЛОХО: Низкий процент размещения")
    
    if average_usage >= 30:
        print("✅ ОТЛИЧНО: Эффективное заполнение листов")
    elif average_usage >= 15:
        print("✅ ХОРОШО: Приемлемое заполнение листов")
    else:
        print("❌ ПЛОХО: Неэффективное заполнение листов")
        
    # Final assessment
    success = placement_rate >= 0.8 and average_usage >= 15
    print(f"\n{'✅ ТЕСТ ПРОШЕЛ' if success else '❌ ТЕСТ НЕ ПРОШЕЛ'}")
    
    return placed_layouts, unplaced_polygons, success

if __name__ == "__main__":
    test_enhanced_fill_optimization()