#!/usr/bin/env python3

"""
Test script to test the progress detector optimization
"""

import logging
from shapely.geometry import Polygon
from layout_optimizer import bin_packing_with_inventory, Carpet

# Настраиваем логирование для отслеживания детектора прогресса
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger('layout_optimizer')

def create_test_data():
    """Create test data with many orders to trigger the optimization"""
    
    # 1. Create available sheets
    available_sheets = []
    
    black_sheet = {
        "name": "Лист 140x200 чёрный", 
        "width": 140, 
        "height": 200,
        "color": "чёрный", 
        "count": 2,  # Only 2 sheets to force more iterations
        "used": 0,
    }
    gray_sheet = {
        "name": "Лист 140x200 серый",
        "width": 140,
        "height": 200, 
        "color": "серый",
        "count": 2,  # Only 2 sheets
        "used": 0,
    }
    available_sheets.extend([black_sheet, gray_sheet])
    
    # 2. Create test carpets with Carpet class
    carpets = []
    
    for i in range(10):  # 10 orders 
        order_id = f"ZAKAZ_row_{i+10}"
        color = "чёрный" if i % 2 == 0 else "серый"
        filename = f"test_order_{i}.dxf"
        
        # Create small polygons that will fit
        width = 30 + (i % 5) * 5   # 30 to 50 mm
        height = 30 + (i % 5) * 5  # 30 to 50 mm 
        
        polygon = Polygon([(0, 0), (width, 0), (width, height), (0, height)])
        
        carpet = Carpet(
            polygon=polygon,
            filename=filename,
            color=color,
            order_id=order_id,
            priority=1
        )
        carpets.append(carpet)
    
    # Add some impossible to fit carpets to trigger no-progress scenario
    for i in range(5):
        order_id = f"IMPOSSIBLE_{i}"
        color = "неизвестный_цвет"  # Color that doesn't exist in sheets
        filename = f"impossible_{i}.dxf"
        
        # Create normal-sized polygon but wrong color
        width = 30   
        height = 30  
        
        polygon = Polygon([(0, 0), (width, 0), (width, height), (0, height)])
        
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
    print("=== ТЕСТ ДЕТЕКТОРА ЗАВИСШИХ ИТЕРАЦИЙ ===")
    
    available_sheets, carpets = create_test_data()
    
    print(f"Создано {len(available_sheets)} типов листов")
    print(f"Создано {len(carpets)} ковров")
    
    for sheet in available_sheets:
        print(f"  - {sheet['name']}: {sheet['count']} листов")
    
    print("\nКовры:")
    for carpet in carpets:
        bounds = carpet.polygon.bounds
        w = bounds[2] - bounds[0]
        h = bounds[3] - bounds[1] 
        print(f"  - {carpet.filename}: {w}x{h}mm, цвет {carpet.color}, заказ {carpet.order_id}")
    
    # Run optimization
    MAX_SHEETS_PER_ORDER = 5
    
    print(f"\n=== ЗАПУСК ОПТИМИЗАЦИИ (MAX_SHEETS_PER_ORDER={MAX_SHEETS_PER_ORDER}) ===")
    
    try:
        placed_layouts, unplaced_carpets = bin_packing_with_inventory(
            carpets,
            available_sheets,
            verbose=False,  # Отключаем verbose чтобы не требовать Streamlit
            max_sheets_per_order=MAX_SHEETS_PER_ORDER,
        )
        
        print("\n=== РЕЗУЛЬТАТЫ ===")
        print(f"Размещенных листов: {len(placed_layouts)}")
        print(f"Неразмещенных ковров: {len(unplaced_carpets)}")
        
        if placed_layouts:
            print("\nДетали по листам:")
            for layout in placed_layouts:
                print(f"  Лист {layout['sheet_number']}: {len(layout['placed_polygons'])} полигонов, {layout.get('usage_percent', 0):.1f}% заполнение")
        
        if unplaced_carpets:
            print("\nНеразмещенные ковры:")
            for carpet in unplaced_carpets:
                if hasattr(carpet, 'filename'):
                    print(f"  - {carpet.filename}")
                else:
                    print(f"  - {carpet}")
    
    except Exception as e:
        print(f"❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()