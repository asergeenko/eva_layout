#!/usr/bin/env python3

"""
Test specifically for SUBARU FORESTER duplication issue
"""

import sys
import importlib

# Force reload of the module to ensure we get the latest version
if 'layout_optimizer' in sys.modules:
    importlib.reload(sys.modules["layout_optimizer"])

from layout_optimizer import bin_packing_with_inventory, Carpet
from shapely.geometry import Polygon

def test_subaru_duplication():
    """Test that SUBARU FORESTER doesn't get duplicated during placement"""
    
    # Large sheets to ensure polygons fit
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
    
    # Add SUBARU FORESTER with different suffixes to test duplication
    for i in range(4):
        filename = f"SUBARU FORESTER 2_{i+1}.dxf"
        width = 400
        height = 400
        polygon = Polygon([(0, 0), (width, 0), (width, height), (0, height)])
        priority = 1
        polygons.append(Carpet(polygon, filename, "чёрный", f"SUBARU_ORDER_{i+1}", priority))
    
    # Add some filler polygons
    for i in range(5):
        filename = f"filler_{i}.dxf"
        width = 300
        height = 300
        polygon = Polygon([(0, 0), (width, 0), (width, height), (0, height)])
        priority = 1
        polygons.append(Carpet(polygon, filename, "чёрный", f"FILLER_ORDER_{i}", priority))
    
    print("=== ТЕСТ ДУБЛИРОВАНИЯ SUBARU FORESTER ===")
    print(f"Полигонов: {len(polygons)}")
    print("SUBARU файлы: SUBARU FORESTER 2_1.dxf, SUBARU FORESTER 2_2.dxf, SUBARU FORESTER 2_3.dxf, SUBARU FORESTER 2_4.dxf")  
    print("ОЖИДАНИЕ: каждый SUBARU файл должен быть размещен ровно один раз")
    
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
        print("\nПроверка дублирования SUBARU FORESTER:")
        subaru_count = {}
        
        for layout in placed_layouts:
            for placed_tuple in layout['placed_polygons']:
                # Handle different tuple structures
                if len(placed_tuple) >= 5:
                    # Extended format: (polygon, x, y, angle, filename, color, order_id)
                    filename = placed_tuple[4]
                elif len(placed_tuple) >= 2:
                    # Standard format: (polygon, filename, ...)
                    filename = placed_tuple[1]
                else:
                    filename = "unknown"
                
                if "SUBARU FORESTER 2_" in filename:
                    subaru_count[filename] = subaru_count.get(filename, 0) + 1
        
        print("Найдено SUBARU файлов:")
        duplications = 0
        for filename, count in subaru_count.items():
            status = "✅" if count == 1 else "❌"
            print(f"  {status} {filename}: {count} раз(а)")
            if count > 1:
                duplications += count - 1
        
        if duplications == 0:
            print("\n✅ ДУБЛИРОВАНИЙ НЕ ОБНАРУЖЕНО")
            return True
        else:
            print(f"\n❌ ОБНАРУЖЕНО {duplications} ДУБЛИРОВАНИЙ")
            return False
    else:
        print("❌ НИ ОДНОГО ЛИСТА НЕ СОЗДАНО")
        return False

if __name__ == "__main__":
    result = test_subaru_duplication()
    print(f"\n{'✅ ТЕСТ ПРОШЕЛ' if result else '❌ ТЕСТ НЕ ПРОШЕЛ'}")