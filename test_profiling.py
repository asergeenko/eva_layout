#!/usr/bin/env python3

"""
Profiling test to identify performance bottlenecks
"""

import logging
from shapely.geometry import Polygon
from layout_optimizer import bin_packing_with_inventory, Carpet

# Включаем логирование на уровне WARNING для профилирования
logging.basicConfig(level=logging.WARNING, format='%(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger('layout_optimizer')

def create_complex_test_data():
    """Create test data that will trigger complex geometric operations"""
    
    # 1. Limited sheets to force dxf filling with many obstacles
    available_sheets = []
    
    black_sheet = {
        "name": "Лист 140x200 чёрный", 
        "width": 140, 
        "height": 200,
        "color": "чёрный", 
        "count": 2,  # Limited to force complex dxf filling
        "used": 0,
    }
    available_sheets.append(black_sheet)
    
    # 2. Create many carpets with complex shapes
    carpets = []
    
    for i in range(30):  # 30 carpets to create many obstacles
        order_id = f"ORDER_{i:02d}"
        color = "чёрный"
        filename = f"complex_{i}.dxf"
        
        if i < 15:
            # Small carpets first - will be placed and become obstacles
            size = 15 + (i % 5) * 3  # 15-27 mm
            polygon = Polygon([(0, 0), (size, 0), (size, size), (0, size)])
        else:
            # Larger, more complex shapes later - will face many obstacles
            size = 40 + (i % 8) * 5  # 40-75 mm
            # Create L-shaped polygon (more complex geometry)
            polygon = Polygon([
                (0, 0), (size, 0), (size, size//2), 
                (size//2, size//2), (size//2, size), (0, size)
            ])
        
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
    print("=== ПРОФИЛИРОВАНИЕ УЗКИХ МЕСТ ===")
    
    available_sheets, carpets = create_complex_test_data()
    
    print(f"Создано {len(available_sheets)} типов листов")
    print(f"Создано {len(carpets)} ковров")
    print("Включено логирование WARNING для отслеживания медленных операций...\n")
    
    # Run with profiling enabled
    try:
        placed_layouts, unplaced_carpets = bin_packing_with_inventory(
            carpets,
            available_sheets,
            verbose=False,
            max_sheets_per_order=5,
        )
        
        print(f"\n=== РЕЗУЛЬТАТЫ ===")
        print(f"Размещенных листов: {len(placed_layouts)}")
        print(f"Неразмещенных ковров: {len(unplaced_carpets)}")
        
        if placed_layouts:
            for layout in placed_layouts:
                print(f"  Лист {layout['sheet_number']}: {len(layout['placed_polygons'])} ковров")
        
        print("\n=== АНАЛИЗ ЛОГОВ ===")
        print("Проверьте логи выше на наличие предупреждений о медленных операциях:")
        print("- ⏱️ bin_packing_with_existing: медленное дозаполнение")
        print("- ⏱️ Медленный полигон: долгое размещение отдельного полигона")
        print("- ⏱️ Медленный поиск позиции: много препятствий")
        print("- ⏱️ Медленный расчет waste: сложные геометрические операции")
        
    except Exception as e:
        print(f"❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()