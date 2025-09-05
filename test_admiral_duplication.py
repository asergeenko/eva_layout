#!/usr/bin/env python3
"""
Specific test for ADMIRAL 335 duplication issue mentioned by user
"""

import sys
import os
import pandas as pd
import logging
from shapely.geometry import Polygon

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from layout_optimizer import bin_packing_with_inventory

# Set up logging to see detailed algorithm behavior
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def create_admiral_test_scenario():
    """Creates a scenario specifically for ADMIRAL 335 duplication testing"""
    
    # Create some ADMIRAL 335 polygons (ZAKAZ_row_29)
    admiral_polygons = []
    for i in range(3):
        size = 90 + i * 15
        poly = Polygon([(0, 0), (size, 0), (size, size-25), (0, size-25)])
        filename = f"Лодка ADMIRAL 335_{i+1}.dxf"
        admiral_polygons.append((poly, filename, "чёрный", "ZAKAZ_row_29"))
    
    # Add some other polygons to make it realistic
    other_polygons = []
    
    # SUZUKI XBEE
    for i in range(3):
        size = 80 + i * 10
        poly = Polygon([(0, 0), (size, 0), (size, size-20), (0, size-20)])
        filename = f"SUZUKI XBEE_{i+1}.dxf"
        other_polygons.append((poly, filename, "чёрный", "ZAKAZ_row_7"))
    
    # Some random other order
    for i in range(2):
        size = 70 + i * 8
        poly = Polygon([(0, 0), (size, 0), (size, size-15), (0, size-15)])
        filename = f"Random_Product_{i+1}.dxf"
        other_polygons.append((poly, filename, "чёрный", "ZAKAZ_row_5"))
    
    all_polygons = admiral_polygons + other_polygons
    
    print(f"Создано {len(all_polygons)} полигонов:")
    for poly in all_polygons:
        print(f"  • {poly[1]} -> {poly[3]}")
    
    return all_polygons

def create_test_sheets():
    """Creates test sheets optimized to trigger multiple placement attempts"""
    sheets = []
    
    # Create sheets that will force the algorithm to try filling existing sheets
    for i in range(1, 6):
        sheets.append({
            "name": f"Черный лист {i}",
            "width": 140,
            "height": 200,
            "color": "чёрный",
            "count": 1,
            "used": 0
        })
    
    return sheets

def analyze_placement_results(placed_layouts, unplaced):
    """Analyzes results specifically for ADMIRAL 335 duplication"""
    
    print(f"\n=== АНАЛИЗ РЕЗУЛЬТАТОВ ===")
    print(f"Использовано листов: {len(placed_layouts)}")
    print(f"Неразмещенных полигонов: {len(unplaced)}")
    
    # Count ADMIRAL 335 placements
    admiral_placements = {}
    total_admiral_count = 0
    
    for i, layout in enumerate(placed_layouts, 1):
        print(f"\nЛист {i}:")
        sheet_polygons = layout['placed_polygons']
        print(f"  • Полигонов на листе: {len(sheet_polygons)}")
        
        for poly in sheet_polygons:
            # Handle different tuple formats
            if len(poly) >= 7:  # From bin_packing result
                filename = str(poly[4])
                order_id = str(poly[6]) if len(poly) > 6 else "unknown"
            elif len(poly) >= 4:  # Original format
                filename = str(poly[1])
                order_id = str(poly[3])
            else:
                filename = "unknown"
                order_id = "unknown"
            
            print(f"    - {filename} ({order_id})")
            
            # Track ADMIRAL 335 specifically
            if "ADMIRAL 335" in filename:
                if filename not in admiral_placements:
                    admiral_placements[filename] = 0
                admiral_placements[filename] += 1
                total_admiral_count += 1
    
    # Check unplaced ADMIRAL 335
    unplaced_admiral = []
    for poly in unplaced:
        if len(poly) >= 2 and "ADMIRAL 335" in str(poly[1]):
            unplaced_admiral.append(str(poly[1]))
    
    print(f"\n=== АНАЛИЗ ADMIRAL 335 ===")
    print(f"Всего размещений ADMIRAL 335: {total_admiral_count}")
    print(f"По файлам:")
    for filename, count in admiral_placements.items():
        status = "✅ ОК" if count == 1 else f"❌ ДУБЛИРОВАНИЕ ({count} раз)"
        print(f"  • {filename}: {status}")
    
    if unplaced_admiral:
        print(f"Неразмещенные ADMIRAL 335: {unplaced_admiral}")
    
    # Check for duplication problem
    duplicated_files = [f for f, count in admiral_placements.items() if count > 1]
    if duplicated_files:
        print(f"\n❌ НАЙДЕНО ДУБЛИРОВАНИЕ: {duplicated_files}")
        return False
    else:
        print(f"\n✅ Дублирования не найдено")
        return True

def main():
    print("=== ТЕСТ ДУБЛИРОВАНИЯ ADMIRAL 335 ===")
    
    # Create test scenario
    test_polygons = create_admiral_test_scenario()
    test_sheets = create_test_sheets()
    

    # Run algorithm
    print(f"\n=== ЗАПУСК АЛГОРИТМА ===")
    placed_layouts, unplaced = bin_packing_with_inventory(
        test_polygons,
        test_sheets,
        verbose=True,
        max_sheets_per_order=5,
    )
    
    # Analyze results
    success = analyze_placement_results(placed_layouts, unplaced)
    
    return success

if __name__ == "__main__":
    success = main()
    print(f"\nРезультат теста: {'УСПЕХ' if success else 'НЕУДАЧА'}")
    sys.exit(0 if success else 1)