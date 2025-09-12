#!/usr/bin/env python3

from pathlib import Path
from layout_optimizer import parse_dxf_complete, Carpet, bin_packing_with_inventory

def test_exact_scenario():
    """Exact test as described: 140x200 sheet, 1 priority1 + 10 priority2 of same DXF."""
    
    # Create sheet exactly as described
    available_sheets = [{
        "name": "Черный лист",
        "width": 140,
        "height": 200,
        "color": "чёрный", 
        "count": 20,
        "used": 0
    }]

    # Load exact file as specified
    dxf_path = "dxf_samples/ДЕКА KUGOO M4 PRO JILONG/1.dxf"
    
    try:
        polygon_data = parse_dxf_complete(dxf_path, verbose=False)
        if not polygon_data or not polygon_data.get("combined_polygon"):
            print(f"❌ Не удалось загрузить файл {dxf_path}")
            return False
            
        base_polygon = polygon_data["combined_polygon"]
        
        # Get polygon dimensions for analysis
        bounds = base_polygon.bounds
        width_mm = bounds[2] - bounds[0]
        height_mm = bounds[3] - bounds[1]
        area_mm2 = base_polygon.area
        
        print(f"📐 Размеры полигона: {width_mm:.1f} x {height_mm:.1f} мм, площадь: {area_mm2:.0f} мм²")
        
        all_polygons = []
        
        # Add 1 copy with priority 1
        all_polygons.append(Carpet(base_polygon, "1.dxf_priority1", "чёрный", "group_1", 1))
        
        # Add 10 copies with priority 2  
        for i in range(1, 11):
            all_polygons.append(Carpet(base_polygon, f"1.dxf_priority2_копия_{i}", "чёрный", "group_1", 2))
            
    except Exception as e:
        print(f"⚠️ Ошибка загрузки {dxf_path}: {e}")
        return False

    print(f"📋 Загружено {len(all_polygons)} ковров:")
    print(f"   Приоритет 1: 1 копия")
    print(f"   Приоритет 2: 10 копий")
    
    # Calculate theoretical capacity
    sheet_area_mm2 = (140 * 10) * (200 * 10)  # Convert cm to mm
    theoretical_capacity = int(sheet_area_mm2 / area_mm2)
    print(f"📊 Теоретическая вместимость листа: {theoretical_capacity} ковров")
    
    # Run placement
    placed_layouts, unplaced = bin_packing_with_inventory(
        all_polygons,
        available_sheets,
        verbose=True,
    )

    # Analyze results
    actual_placed_count = len(all_polygons) - len(unplaced)
    
    print(f"\n📊 Результаты точного теста:")
    print(f"   Размещено полигонов: {actual_placed_count}/{len(all_polygons)}")
    print(f"   Использовано листов: {len(placed_layouts)}")
    print(f"   Неразмещенных полигонов: {len(unplaced)}")
    
    # Count by priority
    priority1_placed = 0
    priority2_placed = 0
    priority1_unplaced = 0
    priority2_unplaced = 0
    
    # Count placed
    for layout in placed_layouts:
        for placed_tuple in layout['placed_polygons']:
            for carpet in all_polygons:
                if (carpet.polygon, carpet.filename, carpet.color, carpet.order_id) == placed_tuple:
                    if carpet.priority == 1:
                        priority1_placed += 1
                    elif carpet.priority == 2:
                        priority2_placed += 1
                    break
    
    # Count unplaced  
    for unplaced_tuple in unplaced:
        for carpet in all_polygons:
            if (carpet.polygon, carpet.filename, carpet.color, carpet.order_id) == unplaced_tuple:
                if carpet.priority == 1:
                    priority1_unplaced += 1
                elif carpet.priority == 2:
                    priority2_unplaced += 1
                break
    
    print(f"\n📊 По приоритетам:")
    print(f"   Приоритет 1: {priority1_placed} размещено, {priority1_unplaced} неразмещенных")  
    print(f"   Приоритет 2: {priority2_placed} размещено, {priority2_unplaced} неразмещенных")
    
    if len(placed_layouts) > 0:
        print(f"\n📄 ДЕТАЛИ ПО ЛИСТАМ:")
        for i, layout in enumerate(placed_layouts, 1):
            carpet_count = len(layout['placed_polygons'])
            usage = layout.get('usage_percent', 0)
            print(f"   Лист {i}: {carpet_count} ковриков, {usage:.1f}% заполнение")
    
    # Expected result: all should fit if theoretical capacity allows
    expected_to_fit = min(len(all_polygons), theoretical_capacity)
    success = actual_placed_count >= expected_to_fit and priority2_placed > 0
    
    print(f"\n✅ Тест {'ПРОШЕЛ' if success else 'НЕ ПРОШЕЛ'}")
    
    if not success:
        print(f"❌ ПРОБЛЕМА:")
        if priority2_placed == 0:
            print("   Ни один ковер приоритета 2 не был размещен!")
        if actual_placed_count < expected_to_fit:
            print(f"   Размещено {actual_placed_count} из {expected_to_fit} ожидаемых ковров")
    
    return success

if __name__ == "__main__":
    test_exact_scenario()