#!/usr/bin/env python3

"""
Test scenario that closely mimics real Streamlit usage with larger polygons
to see if sheet filling is improved
"""

from shapely.geometry import Polygon
from layout_optimizer import bin_packing_with_inventory, Carpet


def test_real_streamlit_scenario():
    """Test realistic scenario with bigger polygons"""
    
    # Realistic sheet configuration (like in Streamlit)
    available_sheets = [
        {
            "name": "Лист 140x200 чёрный", 
            "width": 140, 
            "height": 200,
            "color": "чёрный", 
            "count": 20,  # Plenty of sheets available
            "used": 0,
        },
        {
            "name": "Лист 140x200 серый",
            "width": 140,
            "height": 200, 
            "color": "серый",
            "count": 20,  # Plenty of sheets available
            "used": 0,
        }
    ]
    
    # Create polygons that more closely mimic real DXF files
    polygons = []
    
    # Multi-file orders (like car floor mats) - should be constrained by MAX_SHEETS_PER_ORDER
    car_orders = [
        ("BMW_X5", "чёрный", 5),  # 5 files
        ("AUDI_A4", "серый", 4),   # 4 files  
        ("MERCEDES_C", "чёрный", 6), # 6 files
        ("TOYOTA_RAV4", "серый", 4), # 4 files
    ]
    
    for car_name, color, file_count in car_orders:
        order_id = f"EVA_BORT_{car_name}"
        for i in range(file_count):
            filename = f"{car_name}_part_{i+1}.dxf"
            
            # Realistic sizes - car mats are substantial
            width = 80 + i * 15  # 80-155mm range  
            height = 60 + i * 10  # 60-100mm range
            polygon = Polygon([(0, 0), (width, 0), (width, height), (0, height)])
            priority = 1
            polygons.append(Carpet(polygon, filename, color, order_id, priority))
    
    # Single-file orders (like individual items)
    for i in range(20):  # 20 individual orders
        order_id = f"SINGLE_ITEM_{i}"
        color = "чёрный" if i % 2 == 0 else "серый"
        filename = f"item_{i}.dxf"
        
        # Smaller individual items
        width = 40 + i * 3   # 40-97mm range
        height = 30 + i * 2  # 30-68mm range
        polygon = Polygon([(0, 0), (width, 0), (width, height), (0, height)])
        priority = 1
        polygons.append(Carpet(polygon, filename, color, order_id, priority))
    
    print(f"Создано {len(polygons)} полигонов:")
    print(f"- Multi-file orders: 4 заказа, всего {sum(fc for _, _, fc in car_orders)} файлов")
    print("- Single-file orders: 20 заказов")
    

    # Run optimization with MAX_SHEETS_PER_ORDER=5 (like in real Streamlit)
    MAX_SHEETS_PER_ORDER = 5
    
    print(f"\n=== ЗАПУСК С MAX_SHEETS_PER_ORDER={MAX_SHEETS_PER_ORDER} ===")
    
    placed_layouts, unplaced_polygons = bin_packing_with_inventory(
        polygons,
        available_sheets,
        verbose=False,  # Set to True to see detailed logs
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
        poorly_filled = []
        well_filled = []
        
        for layout in placed_layouts:
            usage = layout['usage_percent']
            sheet_num = layout['sheet_number']
            polygon_count = len(layout['placed_polygons'])
            
            print(f"  Лист {sheet_num}: {polygon_count} полигонов, {usage:.1f}% заполнение")
            
            if usage < 30:  # Consider <30% as poorly filled
                poorly_filled.append(sheet_num)
            elif usage > 60:  # Consider >60% as well filled
                well_filled.append(sheet_num)
        
        print("\n=== АНАЛИЗ ЗАПОЛНЕНИЯ ===")
        print(f"Плохо заполненные листы (<30%): {poorly_filled}")
        print(f"Хорошо заполненные листы (>60%): {well_filled}")
    
    if unplaced_polygons:
        print("\n=== НЕРАЗМЕЩЕННЫЕ ===")
        for idx, unplaced in enumerate(unplaced_polygons):
            if len(unplaced) >= 4:
                polygon, name, color, order_id = unplaced[:4]
                print(f"  [{idx+1}] {name} (цвет: {color}, заказ: {order_id})")
    
    # Success metrics
    placement_rate = total_placed / len(polygons)
    avg_usage = sum(layout['usage_percent'] for layout in placed_layouts) / len(placed_layouts) if placed_layouts else 0
    
    print("\n=== ИТОГОВЫЕ МЕТРИКИ ===")
    print(f"Процент размещения: {placement_rate*100:.1f}%")
    print(f"Среднее заполнение листов: {avg_usage:.1f}%") 
    print(f"Всего использовано листов: {len(placed_layouts)}")
    print(f"Плохо заполненных листов: {len(poorly_filled)}")
    
    # Assessment
    success_criteria = {
        "placement_rate": placement_rate >= 0.95,  # 95%+ placement
        "avg_usage": avg_usage >= 40,              # 40%+ average usage  
        "few_poorly_filled": len(poorly_filled) <= 2,  # Max 2 poorly filled sheets
    }
    
    print("\n=== КРИТЕРИИ УСПЕШНОСТИ ===")
    for criterion, passed in success_criteria.items():
        status = "✅ ПРОШЕЛ" if passed else "❌ НЕ ПРОШЕЛ"
        print(f"  {criterion}: {status}")
    
    overall_success = all(success_criteria.values())
    print(f"\n{'✅ ТЕСТ ПРОШЕЛ УСПЕШНО' if overall_success else '❌ ТЕСТ НЕ ПРОШЕЛ'}")
    
    return placed_layouts, unplaced_polygons, overall_success

if __name__ == "__main__":
    test_real_streamlit_scenario()