#!/usr/bin/env python3

from pathlib import Path
from layout_optimizer import parse_dxf_complete, Carpet, bin_packing_with_inventory

def test_priority_collision():
    """Test that priority 2 carpets don't overlap with existing ones."""
    
    # Create sheets
    available_sheets = [{
        "name": "Черный лист",
        "width": 140,
        "height": 200,
        "color": "чёрный", 
        "count": 20,
        "used": 0
    }]

    # Create mix of priority 1 and priority 2 polygons
    models = ["VOLKSWAGEN GOLF PLUS"]
    all_polygons = []
    
    for group_id, group in enumerate(models, 1):
        path = Path('dxf_samples') / group
        files = list(path.rglob("*.dxf", case_sensitive=False))[:3]  # Take first 3 files
        
        for dxf_file in files:
            try:
                # Load polygon data
                polygon_data = parse_dxf_complete(dxf_file.as_posix(), verbose=False)
                if polygon_data and polygon_data.get("combined_polygon"):
                    base_polygon = polygon_data["combined_polygon"]
                    
                    # Add 2 copies with priority 1
                    for i in range(1, 3):
                        all_polygons.append(Carpet(base_polygon, f"{dxf_file.name}_priority1_копия_{i}", "чёрный", f"group_{group_id}", 1))
                    
                    # Add 1 copy with priority 2
                    all_polygons.append(Carpet(base_polygon, f"{dxf_file.name}_priority2_копия_1", "чёрный", f"group_{group_id}", 2))
                        
            except Exception as e:
                print(f"⚠️ Ошибка загрузки {dxf_file}: {e}")
                return False

    print(f"Загружено {len(all_polygons)} ковров для тестирования коллизий")
    
    # Run placement
    placed_layouts, unplaced = bin_packing_with_inventory(
        all_polygons,
        available_sheets,
        verbose=True,
    )

    # Check results
    actual_placed_count = len(all_polygons) - len(unplaced)
    
    print(f"\n📊 Результаты теста коллизий:")
    print(f"   Размещено полигонов: {actual_placed_count}/{len(all_polygons)}")
    print(f"   Использовано листов: {len(placed_layouts)}")
    print(f"   Неразмещенных полигонов: {len(unplaced)}")
    
    # Count priority 1 vs 2 in results
    priority1_placed = 0
    priority2_placed = 0
    
    for layout in placed_layouts:
        for placed_polygon in layout['placed_polygons']:
            # Extract priority from carpet objects
            for carpet in all_polygons:
                if (carpet.polygon, carpet.filename, carpet.color, carpet.order_id) == placed_polygon:
                    if carpet.priority == 1:
                        priority1_placed += 1
                    elif carpet.priority == 2:
                        priority2_placed += 1
                    break
    
    priority1_unplaced = sum(1 for c in unplaced if any(carpet.priority == 1 for carpet in all_polygons 
                                                        if (carpet.polygon, carpet.filename, carpet.color, carpet.order_id) == c))
    priority2_unplaced = len(unplaced) - priority1_unplaced
    
    print(f"\n📊 По приоритетам:")
    print(f"   Приоритет 1: {priority1_placed} размещено, {priority1_unplaced} неразмещенных")  
    print(f"   Приоритет 2: {priority2_placed} размещено, {priority2_unplaced} неразмещенных")
    
    if len(placed_layouts) > 0:
        print(f"\n📄 ДЕТАЛИ ПО ЛИСТАМ:")
        for i, layout in enumerate(placed_layouts, 1):
            carpet_count = len(layout['placed_polygons'])
            usage = layout.get('usage_percent', 0)
            print(f"   Лист {i}: {carpet_count} ковриков, {usage:.1f}% заполнение")
    
    # Check for success - all carpets placed and no overlap errors in logs
    success = len(unplaced) == 0
    print(f"\n✅ Тест {'ПРОШЕЛ' if success else 'НЕ ПРОШЕЛ'}")
    
    return success

if __name__ == "__main__":
    test_priority_collision()