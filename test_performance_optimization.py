#!/usr/bin/env python3

"""
Performance test for O(n²) to O(1) optimization
"""

import time
import logging
from shapely.geometry import Polygon
from layout_optimizer import bin_packing_with_inventory, Carpet

# Отключаем логирование для чистого теста производительности
logging.basicConfig(level=logging.ERROR)

def create_heavy_test_data():
    """Create test data that will trigger heavy dxf filling operations"""
    
    # 1. Create limited sheets to force dxf filling
    available_sheets = []
    
    black_sheet = {
        "name": "Лист 140x200 чёрный", 
        "width": 140, 
        "height": 200,
        "color": "чёрный", 
        "count": 3,  # Limited sheets to force dxf filling
        "used": 0,
    }
    gray_sheet = {
        "name": "Лист 140x200 серый",
        "width": 140,
        "height": 200, 
        "color": "серый",
        "count": 3,  # Limited sheets
        "used": 0,
    }
    available_sheets.extend([black_sheet, gray_sheet])
    
    # 2. Create many small carpets that will trigger dxf filling logic
    carpets = []
    
    # Create orders with multiple small carpets each
    for order_num in range(20):  # 20 orders
        order_id = f"ORDER_{order_num:03d}"
        color = "чёрный" if order_num % 2 == 0 else "серый"
        
        # Each order has 3-5 small carpets
        carpets_per_order = 3 + (order_num % 3)
        for carpet_num in range(carpets_per_order):
            filename = f"order_{order_num}_carpet_{carpet_num}.dxf"
            
            # Create small polygons that will fit many per sheet
            size = 20 + (carpet_num % 10) * 2  # 20-38 mm
            polygon = Polygon([(0, 0), (size, 0), (size, size), (0, size)])
            
            carpet = Carpet(
                polygon=polygon,
                filename=filename,
                color=color,
                order_id=order_id,
                priority=1
            )
            carpets.append(carpet)
    
    return available_sheets, carpets

def main():
    print("=== ТЕСТ ПРОИЗВОДИТЕЛЬНОСТИ O(n²) → O(1) ОПТИМИЗАЦИИ ===")
    
    available_sheets, carpets = create_heavy_test_data()
    
    print(f"Создано {len(available_sheets)} типов листов")
    print(f"Создано {len(carpets)} ковров")
    
    # Count orders and carpets per order
    orders = {}
    for carpet in carpets:
        if carpet.order_id not in orders:
            orders[carpet.order_id] = 0
        orders[carpet.order_id] += 1
    
    print(f"Заказов: {len(orders)}")
    print(f"Ковров на заказ: {sum(orders.values()) / len(orders):.1f} в среднем")
    
    # Run optimization with timing
    MAX_SHEETS_PER_ORDER = 5
    
    print(f"\n=== ЗАПУСК ОПТИМИЗАЦИИ (MAX_SHEETS_PER_ORDER={MAX_SHEETS_PER_ORDER}) ===")
    
    start_time = time.time()
    try:
        placed_layouts, unplaced_carpets = bin_packing_with_inventory(
            carpets,
            available_sheets,
            verbose=False,  # Отключаем verbose 
            max_sheets_per_order=MAX_SHEETS_PER_ORDER,
        )
        
        end_time = time.time()
        elapsed = end_time - start_time
        
        print("\n=== РЕЗУЛЬТАТЫ ПРОИЗВОДИТЕЛЬНОСТИ ===")
        print(f"⏱️  Время выполнения: {elapsed:.2f} секунд")
        print(f"📊 Размещенных листов: {len(placed_layouts)}")
        print(f"📦 Неразмещенных ковров: {len(unplaced_carpets)}")
        
        if placed_layouts:
            total_carpets_placed = sum(len(layout['placed_polygons']) for layout in placed_layouts)
            avg_usage = sum(layout.get('usage_percent', 0) for layout in placed_layouts) / len(placed_layouts)
            print(f"🎯 Всего ковров размещено: {total_carpets_placed}")
            print(f"📈 Среднее заполнение листов: {avg_usage:.1f}%")
            
            print("\nДетали по листам:")
            for layout in placed_layouts:
                print(f"  Лист {layout['sheet_number']}: {len(layout['placed_polygons'])} ковров, {layout.get('usage_percent', 0):.1f}%")
        
        # Performance assessment
        carpets_per_second = len(carpets) / elapsed if elapsed > 0 else float('inf')
        print(f"\n🚀 Производительность: {carpets_per_second:.1f} ковров/сек")
        
        if elapsed < 5.0:
            print("✅ ОТЛИЧНАЯ производительность!")
        elif elapsed < 15.0:
            print("✅ Хорошая производительность")
        elif elapsed < 30.0:
            print("⚠️  Приемлемая производительность")
        else:
            print("❌ Медленная производительность - требуется дополнительная оптимизация")
    
    except Exception as e:
        print(f"❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()