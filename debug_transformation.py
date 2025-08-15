#!/usr/bin/env python3
"""
Debug transformation logic specifically
"""

from layout_optimizer import (parse_dxf_complete, bin_packing_with_inventory, 
                              save_dxf_layout_complete, check_collision, 
                              rotate_polygon, translate_polygon)
import os

def debug_transformation_logic():
    """Debug the transformation logic step by step"""
    print("=== ДЕТАЛЬНАЯ ОТЛАДКА ТРАНСФОРМАЦИИ ===")
    
    # Use simple test data
    dxf_samples_dir = "/home/sasha/proj/2025/eva_layout/dxf_samples"
    dxf_files = []
    
    for root, dirs, files in os.walk(dxf_samples_dir):
        for file in files:
            if file.endswith('.dxf'):
                dxf_files.append(os.path.join(root, file))
        if len(dxf_files) >= 2:  # Just 2 files for easier debugging
            break
    
    print(f"Используем {len(dxf_files[:2])} файлов для отладки:")
    
    # Parse files
    input_data = []
    original_dxf_data_map = {}
    
    for i, dxf_file in enumerate(dxf_files[:2]):
        print(f"  {i+1}. Парсинг {os.path.basename(dxf_file)}")
        
        dxf_data = parse_dxf_complete(dxf_file, verbose=False)
        
        if dxf_data['combined_polygon'] and dxf_data['combined_polygon'].area > 0:
            filename = os.path.basename(dxf_file)
            
            input_data.append((
                dxf_data['combined_polygon'], 
                filename, 
                "черный", 
                "order1"
            ))
            
            original_dxf_data_map[filename] = dxf_data
            
            print(f"    Исходная границы полигона: {dxf_data['combined_polygon'].bounds}")
    
    # Run bin packing
    available_sheets = [{
        'name': 'Лист 200x140',
        'width': 200,
        'height': 140,
        'color': 'черный',
        'count': 10,
        'used': 0
    }]
    
    placed_layouts, unplaced = bin_packing_with_inventory(
        input_data, 
        available_sheets, 
        verbose=False
    )
    
    if len(placed_layouts) == 0:
        print("❌ Не создано листов для отладки")
        return
    
    first_layout = placed_layouts[0]
    placed_polygons = first_layout['placed_polygons']
    
    print(f"\nРазмещено полигонов: {len(placed_polygons)}")
    
    # Analyze each placed polygon's transformation
    for i, placed_item in enumerate(placed_polygons):
        if len(placed_item) >= 7:
            transformed_polygon, x_offset, y_offset, angle, file_name, color, order_id = placed_item[:7]
        else:
            continue
            
        print(f"\nПОЛИГОН {i+1} ({file_name}):")
        print(f"  Угол поворота: {angle}°")
        print(f"  Смещения: x={x_offset:.2f}, y={y_offset:.2f}")
        print(f"  Финальные границы: {transformed_polygon.bounds}")
        
        # Get original data
        if file_name in original_dxf_data_map:
            original_data = original_dxf_data_map[file_name]
            original_polygon = original_data['combined_polygon']
            
            print(f"  Исходные границы: {original_polygon.bounds}")
            
            # Replicate bin_packing transformation step by step
            print(f"  Воспроизводим трансформацию bin_packing:")
            
            # Step 1: Rotate
            rotated = rotate_polygon(original_polygon, angle) if angle != 0 else original_polygon
            print(f"    После поворота: {rotated.bounds}")
            
            # Step 2: Translate
            # From bin_packing code: translated = translate_polygon(rotated, best_x - rotated_bounds[0], best_y - rotated_bounds[1])
            # We have x_offset = best_x - rotated_bounds[0], y_offset = best_y - rotated_bounds[1]
            translated = translate_polygon(rotated, x_offset, y_offset)
            print(f"    После перемещения: {translated.bounds}")
            print(f"    Ожидаемые границы: {transformed_polygon.bounds}")
            
            # Check if they match
            expected_bounds = transformed_polygon.bounds
            actual_bounds = translated.bounds
            
            matches = all(abs(expected_bounds[j] - actual_bounds[j]) < 0.01 for j in range(4))
            print(f"    Соответствие: {'✅' if matches else '❌'}")
            
            # Now test what our save_dxf_layout_complete would do
            print(f"  Тестируем логику save_dxf_layout_complete:")
            
            # Our new logic:
            # 1. Rotate the original polygon
            rotated_polygon = rotate_polygon(original_polygon, angle) if angle != 0 else original_polygon
            rotated_bounds = rotated_polygon.bounds
            final_bounds = transformed_polygon.bounds
            
            # 2. Calculate translation
            x_translation = final_bounds[0] - rotated_bounds[0]
            y_translation = final_bounds[1] - rotated_bounds[1]
            
            print(f"    Поворот полигона: {rotated_bounds}")
            print(f"    Целевое положение: {final_bounds}")
            print(f"    Вычисленный сдвиг: x={x_translation:.2f}, y={y_translation:.2f}")
            print(f"    Ожидаемый сдвиг: x={x_offset:.2f}, y={y_offset:.2f}")
            
            translation_matches = (abs(x_translation - x_offset) < 0.01 and 
                                 abs(y_translation - y_offset) < 0.01)
            print(f"    Сдвиг соответствует: {'✅' if translation_matches else '❌'}")
            
            if not translation_matches:
                print(f"    ⚠️ НАЙДЕНА ПРОБЛЕМА В ВЫЧИСЛЕНИИ СДВИГА!")
                print(f"      Разница x: {abs(x_translation - x_offset):.4f}")
                print(f"      Разница y: {abs(y_translation - y_offset):.4f}")

if __name__ == "__main__":
    debug_transformation_logic()