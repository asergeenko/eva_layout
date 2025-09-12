#!/usr/bin/env python3

from pathlib import Path
from layout_optimizer import parse_dxf_complete, Carpet, bin_packing_with_inventory

def test_simple_priority():
    """Simple test with just 1 carpet of each priority."""
    
    # Create sheets
    available_sheets = [{
        "name": "Черный лист",
        "width": 140,
        "height": 200,
        "color": "чёрный", 
        "count": 20,
        "used": 0
    }]

    # Load just one DXF file and create one of each priority
    models = ["VOLKSWAGEN GOLF PLUS"]
    all_polygons = []
    
    for group_id, group in enumerate(models, 1):
        path = Path('dxf_samples') / group
        files = list(path.rglob("*.dxf", case_sensitive=False))
        
        if len(files) >= 2:
            # Take two different files to avoid identical polygons
            dxf_file1 = files[0] 
            dxf_file2 = files[1]
            
            try:
                # Load first polygon data
                polygon_data1 = parse_dxf_complete(dxf_file1.as_posix(), verbose=False)
                if polygon_data1 and polygon_data1.get("combined_polygon"):
                    polygon1 = polygon_data1["combined_polygon"]
                    all_polygons.append(Carpet(polygon1, f"{dxf_file1.name}_priority1", "чёрный", f"group_{group_id}", 1))
                    
                # Load second polygon data  
                polygon_data2 = parse_dxf_complete(dxf_file2.as_posix(), verbose=False)
                if polygon_data2 and polygon_data2.get("combined_polygon"):
                    polygon2 = polygon_data2["combined_polygon"]
                    all_polygons.append(Carpet(polygon2, f"{dxf_file2.name}_priority2", "чёрный", f"group_{group_id}", 2))
                        
            except Exception as e:
                print(f"⚠️ Ошибка загрузки файлов: {e}")
                return False

    print(f"Загружено {len(all_polygons)} ковров: {[f'{c.filename} (приоритет {c.priority})' for c in all_polygons]}")
    
    # Run placement with verbose logging
    placed_layouts, unplaced = bin_packing_with_inventory(
        all_polygons,
        available_sheets,
        verbose=True,
    )

    # Check results
    actual_placed_count = len(all_polygons) - len(unplaced)
    
    print(f"\n📊 Результаты простого теста:")
    print(f"   Размещено полигонов: {actual_placed_count}/{len(all_polygons)}")
    print(f"   Использовано листов: {len(placed_layouts)}")
    print(f"   Неразмещенных полигонов: {len(unplaced)}")
    
    # Analyze what was placed
    for i, layout in enumerate(placed_layouts, 1):
        print(f"\n📄 Лист {i}:")
        for j, placed_polygon in enumerate(layout['placed_polygons']):
            # Find corresponding carpet
            for carpet in all_polygons:
                if (carpet.polygon, carpet.filename, carpet.color, carpet.order_id) == placed_polygon:
                    print(f"   Полигон {j+1}: {carpet.filename} (приоритет {carpet.priority})")
                    break
    
    # Analyze what was NOT placed
    if unplaced:
        print(f"\n❌ Неразмещенные:")
        for unplaced_polygon in unplaced:
            # Find corresponding carpet
            for carpet in all_polygons:
                if (carpet.polygon, carpet.filename, carpet.color, carpet.order_id) == unplaced_polygon:
                    print(f"   {carpet.filename} (приоритет {carpet.priority})")
                    break
    
    # Success if both are placed
    success = len(unplaced) == 0
    print(f"\n✅ Тест {'ПРОШЕЛ' if success else 'НЕ ПРОШЕЛ'}")
    
    return success

if __name__ == "__main__":
    test_simple_priority()