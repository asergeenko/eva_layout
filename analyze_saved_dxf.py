#!/usr/bin/env python3
"""
Analyze the saved DXF file to understand why there are overlapping polygons
"""

from layout_optimizer import parse_dxf_complete, check_collision
import ezdxf

def analyze_saved_dxf():
    """Analyze the saved DXF file in detail"""
    print("=== АНАЛИЗ СОХРАНЕННОГО DXF ФАЙЛА ===")
    
    dxf_path = "/tmp/test_problem_file.dxf"
    
    # First, look at raw DXF structure
    try:
        doc = ezdxf.readfile(dxf_path)
        msp = doc.modelspace()
        
        print(f"Всего entities в DXF файле: {len(list(msp))}")
        
        # Count by layers
        layers = {}
        for entity in msp:
            layer = getattr(entity.dxf, 'layer', '0')
            layers[layer] = layers.get(layer, 0) + 1
        
        print(f"Entities по слоям:")
        for layer, count in layers.items():
            print(f"  {layer}: {count}")
            
        # Check for actual duplicates or overlaps at entity level
        print(f"\nПроверка отдельных entities на перекрытие...")
        
        all_entities = list(msp)
        entity_polygons = []
        
        for i, entity in enumerate(all_entities):
            try:
                # Try to convert entity to polygon
                from layout_optimizer import convert_entity_to_polygon_improved
                polygon = convert_entity_to_polygon_improved(entity)
                if polygon and polygon.is_valid and polygon.area > 0.1:
                    entity_polygons.append({
                        'index': i,
                        'polygon': polygon,
                        'layer': getattr(entity.dxf, 'layer', '0'),
                        'type': entity.dxftype(),
                        'bounds': polygon.bounds
                    })
            except:
                pass
        
        print(f"Получено {len(entity_polygons)} валидных полигонов из entities")
        
        # Check overlaps between entity polygons
        overlaps = 0
        overlap_details = []
        
        for i in range(len(entity_polygons)):
            for j in range(i+1, len(entity_polygons)):
                poly1 = entity_polygons[i]
                poly2 = entity_polygons[j]
                
                if check_collision(poly1['polygon'], poly2['polygon']):
                    overlaps += 1
                    overlap_details.append((i, j, poly1, poly2))
                    
                    if overlaps <= 5:  # Show first 5
                        print(f"  Перекрытие #{overlaps}:")
                        print(f"    Entity {poly1['index']} (слой {poly1['layer']}, тип {poly1['type']})")
                        print(f"    Entity {poly2['index']} (слой {poly2['layer']}, тип {poly2['type']})")
                        print(f"    Bounds1: {poly1['bounds']}")
                        print(f"    Bounds2: {poly2['bounds']}")
        
        print(f"\nНайдено {overlaps} перекрытий на уровне отдельных entities")
        
        # Now parse using our standard method
        print(f"\n=== АНАЛИЗ ЧЕРЕЗ parse_dxf_complete ===")
        
        parsed_data = parse_dxf_complete(dxf_path, verbose=False)
        
        print(f"parse_dxf_complete результат:")
        print(f"  Всего entities: {len(parsed_data['original_entities'])}")
        print(f"  Полигонов для оптимизации: {len(parsed_data['polygons'])}")
        print(f"  Слои: {parsed_data['layers']}")
        
        # Check collisions between parsed polygons (this is what the trace script checks)
        if len(parsed_data['polygons']) > 1:
            collisions = 0
            for i in range(len(parsed_data['polygons'])):
                for j in range(i+1, len(parsed_data['polygons'])):
                    if check_collision(parsed_data['polygons'][i], parsed_data['polygons'][j]):
                        collisions += 1
                        if collisions <= 3:
                            print(f"  Коллизия #{collisions} между полигонами {i+1} и {j+1}")
                            print(f"    Bounds1: {parsed_data['polygons'][i].bounds}")
                            print(f"    Bounds2: {parsed_data['polygons'][j].bounds}")
            
            print(f"Найдено {collisions} коллизий между полигонами parse_dxf_complete")
            
            # The discrepancy might be because parse_dxf_complete skips the sheet border
            # Let's check if we're including the sheet border in collision detection
            if len(parsed_data['polygons']) > 3:
                print(f"\nПервые 3 полигона (возможно, границы листа):")
                for i in range(min(3, len(parsed_data['polygons']))):
                    bounds = parsed_data['polygons'][i].bounds
                    area = parsed_data['polygons'][i].area
                    print(f"  Полигон {i+1}: bounds={bounds}, area={area:.1f}")
        
    except Exception as e:
        print(f"Ошибка анализа DXF: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    analyze_saved_dxf()