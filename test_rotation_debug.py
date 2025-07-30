#!/usr/bin/env python3
"""Debug rotation positioning for DXF elements."""

import os
import numpy as np
from layout_optimizer import parse_dxf_complete, save_dxf_layout_complete, rotate_polygon, place_polygon_at_origin, translate_polygon

def test_rotation_debug():
    """Debug the exact transformations that should happen."""
    print("🔄 Отладка поворота DXF элементов")
    print("=" * 60)
    
    # Find a sample DXF file
    sample_file = None
    dxf_samples_path = "dxf_samples"
    
    if os.path.exists(dxf_samples_path):
        for root, dirs, files in os.walk(dxf_samples_path):
            for file in files:
                if file.lower().endswith('.dxf'):
                    sample_file = os.path.join(root, file)
                    break
            if sample_file:
                break
    
    if not sample_file:
        print("❌ Не найден образец DXF файла")
        return False
    
    print(f"📄 Файл: {os.path.basename(sample_file)}")
    
    # Parse original file
    with open(sample_file, 'rb') as f:
        parsed_data = parse_dxf_complete(f, verbose=False)
    
    if not parsed_data or not parsed_data['combined_polygon']:
        return False
    
    original_polygon = parsed_data['combined_polygon']
    
    print(f"\n📐 Исходный полигон:")
    print(f"   • Центроид: ({original_polygon.centroid.x:.2f}, {original_polygon.centroid.y:.2f})")
    print(f"   • Границы: {original_polygon.bounds}")
    
    # Simulate bin packing transformation sequence
    angle = 90  # Test with 90 degree rotation
    
    print(f"\n🔄 Имитация трансформации bin packing (поворот {angle}°):")
    
    # Step 1: Place at origin (like bin packing does)
    origin_placed = place_polygon_at_origin(original_polygon)
    print(f"   1. После place_at_origin:")
    print(f"      • Центроид: ({origin_placed.centroid.x:.2f}, {origin_placed.centroid.y:.2f})")
    print(f"      • Границы: {origin_placed.bounds}")
    
    # Step 2: Rotate (like bin packing does)
    rotated = rotate_polygon(origin_placed, angle)
    print(f"   2. После поворота на {angle}°:")
    print(f"      • Центроид: ({rotated.centroid.x:.2f}, {rotated.centroid.y:.2f})")
    print(f"      • Границы: {rotated.bounds}")
    
    # Step 3: Translate to final position
    x_offset, y_offset = 100, 200
    final_polygon = translate_polygon(rotated, x_offset, y_offset)
    print(f"   3. После перемещения на ({x_offset}, {y_offset}):")
    print(f"      • Центроид: ({final_polygon.centroid.x:.2f}, {final_polygon.centroid.y:.2f})")
    print(f"      • Границы: {final_polygon.bounds}")
    
    # Create test output
    test_output = f"test_debug_rotation_{angle}.dxf"
    original_dxf_data_map = {os.path.basename(sample_file): parsed_data}
    
    # The placed_elements should contain the final transformed polygon and the transformation parameters
    # that were used to create it
    placed_elements = [(final_polygon, x_offset, y_offset, angle, os.path.basename(sample_file), "серый")]
    sheet_size = (500, 500)  # Large sheet
    
    try:
        save_dxf_layout_complete(placed_elements, sheet_size, test_output, original_dxf_data_map)
        
        if os.path.exists(test_output):
            print(f"\n✅ Создан DXF файл: {test_output}")
            
            # Analyze output
            with open(test_output, 'rb') as f:
                output_parsed = parse_dxf_complete(f, verbose=False)
            
            if output_parsed and output_parsed['combined_polygon']:
                output_centroid = output_parsed['combined_polygon'].centroid
                
                print(f"\n📊 Результаты:")
                print(f"   • Ожидаемый центроид: ({final_polygon.centroid.x:.2f}, {final_polygon.centroid.y:.2f})")
                print(f"   • Фактический центроид: ({output_centroid.x:.2f}, {output_centroid.y:.2f})")
                
                # Check difference
                x_diff = abs(output_centroid.x - final_polygon.centroid.x)
                y_diff = abs(output_centroid.y - final_polygon.centroid.y)
                
                print(f"   • Отклонение: ({x_diff:.2f}, {y_diff:.2f})")
                
                # Also check sheet boundary position
                sheet_center_x = sheet_size[0] * 10 / 2  # Sheet center in mm
                sheet_center_y = sheet_size[1] * 10 / 2
                print(f"   • Центр листа: ({sheet_center_x:.2f}, {sheet_center_y:.2f})")
                
                if x_diff <= 10 and y_diff <= 10:  # 10mm tolerance
                    print(f"   ✅ Позиция корректна!")
                    return True
                else:
                    print(f"   ❌ Позиция некорректна")
                    return False
            else:
                print("❌ Не удалось распарсить выходной файл")
                return False
        else:
            print("❌ Не удалось создать файл")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

if __name__ == "__main__":
    success = test_rotation_debug()
    print(f"\n{'🎉 Тест пройден!' if success else '❌ Тест не пройден!'}")