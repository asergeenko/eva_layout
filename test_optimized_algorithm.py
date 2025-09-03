#!/usr/bin/env python3

"""
Test script to debug the optimized algorithm
"""

import pandas as pd
import os
from shapely.geometry import Polygon
from unittest.mock import Mock

from layout_optimizer import (
    bin_packing_with_inventory,
    scale_polygons_to_fit,
)

def create_test_data():
    """Create test data similar to streamlit test"""
    
    # 1. Create available sheets
    available_sheets = []
    
    black_sheet = {
        "name": "Лист 140x200 чёрный", 
        "width": 140, 
        "height": 200,
        "color": "чёрный", 
        "count": 20, 
        "used": 0,
    }
    gray_sheet = {
        "name": "Лист 140x200 серый",
        "width": 140,
        "height": 200, 
        "color": "серый",
        "count": 20,
        "used": 0,
    }
    available_sheets.extend([black_sheet, gray_sheet])
    
    # 2. Create test polygons 
    dxf_files = []
    
    for i in range(37):  # 37 orders like in the real test
        order_id = f"ZAKAZ_row_{i+10}"  # Similar to real order IDs
        color = "чёрный" if i % 2 == 0 else "серый"  # Alternate colors
        filename = f"test_order_{i}.dxf"
        
        # Create polygon with varying sizes
        width = 50 + (i % 10) * 10   # 50 to 140 mm
        height = 50 + (i % 15) * 10  # 50 to 190 mm 
        
        polygon = Polygon([(0, 0), (width, 0), (width, height), (0, height)])
        
        priority = 1  # Default priority for all test orders
        dxf_files.append((polygon, filename, color, order_id, priority))
    
    # 3. Scale polygons
    scaled_polygons = scale_polygons_to_fit(dxf_files, (140, 200), verbose=True)
    
    return available_sheets, scaled_polygons

def main():
    print("=== ТЕСТ ОПТИМИЗИРОВАННОГО АЛГОРИТМА ===")
    
    available_sheets, scaled_polygons = create_test_data()
    
    print(f"Создано {len(available_sheets)} типов листов")
    print(f"Создано {len(scaled_polygons)} полигонов")
    
    # Analyze polygon structure
    print("\n=== АНАЛИЗ ПОЛИГОНОВ ===")
    for i, poly_tuple in enumerate(scaled_polygons[:5]):  # Show first 5
        print(f"Полигон {i}: длина tuple={len(poly_tuple)}")
        if len(poly_tuple) >= 4:
            print(f"  filename={poly_tuple[1]}, color={poly_tuple[2]}, order_id={poly_tuple[3]}")
        else:
            print(f"  tuple={poly_tuple}")
    
    # Run optimization
    MAX_SHEETS_PER_ORDER = 5
    
    print(f"\n=== ЗАПУСК ОПТИМИЗАЦИИ (MAX_SHEETS_PER_ORDER={MAX_SHEETS_PER_ORDER}) ===")
    
    placed_layouts, unplaced_polygons = bin_packing_with_inventory(
        scaled_polygons,
        available_sheets,
        verbose=False,  # Отключаем verbose чтобы не требовать Streamlit
        max_sheets_per_order=MAX_SHEETS_PER_ORDER,
    )
    
    print(f"\n=== РЕЗУЛЬТАТЫ ===")
    print(f"Размещенных листов: {len(placed_layouts)}")
    print(f"Неразмещенных полигонов: {len(unplaced_polygons)}")
    
    if placed_layouts:
        print("\nДетали по листам:")
        for layout in placed_layouts:
            print(f"  Лист {layout['sheet_number']}: {len(layout['placed_polygons'])} полигонов, {layout['usage_percent']:.1f}% заполнение")
    else:
        print("❌ НИ ОДНОГО ЛИСТА НЕ СОЗДАНО!")
        print("Проверьте логи выше для понимания причины")

if __name__ == "__main__":
    main()