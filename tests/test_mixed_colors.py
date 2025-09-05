#!/usr/bin/env python3

"""
Test mixed colors to ensure algorithm tries different sheet types
"""

import sys
import importlib

# Force reload of the module to ensure we get the latest version
if 'layout_optimizer' in sys.modules:
    importlib.reload(sys.modules["layout_optimizer"])

from layout_optimizer import bin_packing_with_inventory, Carpet
from shapely.geometry import Polygon

def test_mixed_colors():
    """Test that algorithm properly handles mixed colors and tries different sheet types"""
    
    # Both black and gray sheets available
    available_sheets = [
        {
            "name": "Лист чёрный", 
            "width": 2000,
            "height": 2000,
            "color": "чёрный", 
            "count": 5,
            "used": 0,
        },
        {
            "name": "Лист серый", 
            "width": 2000,
            "height": 2000,
            "color": "серый", 
            "count": 5,
            "used": 0,
        }
    ]
    
    polygons = []
    
    # Black polygons (should go on black sheets)
    for i in range(3):
        filename = f"black_{i}.dxf"
        width = 400
        height = 400
        polygon = Polygon([(0, 0), (width, 0), (width, height), (0, height)])
        priority = 1
        polygons.append(Carpet(polygon, filename, "чёрный", f"BLACK_ORDER_{i}", priority))
    
    # Gray polygons (should go on gray sheets)
    for i in range(3):
        filename = f"gray_{i}.dxf"
        width = 400
        height = 400
        polygon = Polygon([(0, 0), (width, 0), (width, height), (0, height)])
        priority = 1
        polygons.append(Carpet(polygon, filename, "серый", f"GRAY_ORDER_{i}", priority))
    
    print("=== ТЕСТ СМЕШАННЫХ ЦВЕТОВ ===")
    print(f"Полигонов: {len(polygons)}")
    print("Черные заказы: BLACK_ORDER_0, BLACK_ORDER_1, BLACK_ORDER_2")  
    print("Серые заказы: GRAY_ORDER_0, GRAY_ORDER_1, GRAY_ORDER_2")
    print("ОЖИДАНИЕ: полигоны должны быть размещены на листах соответствующих цветов")
    
    placed_layouts, unplaced_polygons = bin_packing_with_inventory(
        polygons,
        available_sheets,
        verbose=False,
        max_sheets_per_order=3,
    )
    
    print("\n=== РЕЗУЛЬТАТ ===")
    print(f"Листов создано: {len(placed_layouts)}")
    print(f"Неразмещенных полигонов: {len(unplaced_polygons)}")
    
    total_placed = sum(len(layout["placed_polygons"]) for layout in placed_layouts)
    print(f"Всего размещено: {total_placed}/{len(polygons)}")
    
    if placed_layouts:
        print("\nДетали по листам:")
        black_sheets = []
        gray_sheets = []
        
        for layout in placed_layouts:
            sheet_type = layout.get('sheet_type', 'Unknown')
            if sheet_type == 'Unknown' and 'sheet_color' in layout:
                sheet_type = f"Лист ({layout['sheet_color']})"
            
            polygons_count = len(layout['placed_polygons'])
            orders = layout['orders_on_sheet']
            
            print(f"  {sheet_type}: {polygons_count} полигонов, заказы: {', '.join(orders)}")
            
            if "чёрный" in sheet_type:
                black_sheets.append(layout)
            elif "серый" in sheet_type:
                gray_sheets.append(layout)
        
        print("\nАнализ по цветам:")
        print(f"Черных листов: {len(black_sheets)}")
        print(f"Серых листов: {len(gray_sheets)}")
        
        # Check if all polygons placed
        if unplaced_polygons:
            print(f"\n❌ ПРОБЛЕМА: {len(unplaced_polygons)} полигонов не размещены")
            for poly_tuple in unplaced_polygons:
                if len(poly_tuple) >= 3:
                    filename, color = poly_tuple[1], poly_tuple[2]
                    print(f"  - {filename} (цвет: {color})")
        else:
            print("\n✅ ВСЕ ПОЛИГОНЫ РАЗМЕЩЕНЫ")
            
        # Check if colors match sheet types
        success = True
        if len(black_sheets) == 0 and len(gray_sheets) == 0:
            print("❌ НЕ СОЗДАНО НИ ОДНОГО ЛИСТА")
            success = False
        elif len(black_sheets) > 0 and len(gray_sheets) > 0:
            print("✅ СОЗДАНЫ ЛИСТЫ ОБОИХ ЦВЕТОВ")
        else:
            print("⚠️ СОЗДАН ТОЛЬКО ОДИН ТИП ЛИСТОВ - возможная проблема")
            
        return success and len(unplaced_polygons) == 0
    else:
        print("❌ НИ ОДНОГО ЛИСТА НЕ СОЗДАНО")
        return False

if __name__ == "__main__":
    result = test_mixed_colors()
    print(f"\n{'✅ ТЕСТ ПРОШЕЛ' if result else '❌ ТЕСТ НЕ ПРОШЕЛ'}")