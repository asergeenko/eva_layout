#!/usr/bin/env python3
"""Test rotation with realistic bin packing simulation."""

import os
import numpy as np
from layout_optimizer import parse_dxf_complete, save_dxf_layout_complete, rotate_polygon, place_polygon_at_origin, translate_polygon

def test_rotation_realistic():
    """Test with realistic bin packing simulation."""
    print("🔄 Тестирование с реалистичной симуляцией bin packing")
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
    
    # Simulate what bin packing algorithm actually does
    angle = 90
    grid_x = 500  # Grid position where we want to place the polygon
    grid_y = 800  
    
    print(f"\n🔄 Симуляция bin packing размещения на позиции ({grid_x}, {grid_y}) с поворотом {angle}°:")
    
    # Step 1: Rotate the original polygon (this is what bin packing does first)
    rotated_original = rotate_polygon(original_polygon, angle)
    rotated_bounds = rotated_original.bounds
    print(f"   1. После поворота исходного на {angle}°:")
    print(f"      • Центроид: ({rotated_original.centroid.x:.2f}, {rotated_original.centroid.y:.2f})")
    print(f"      • Границы: {rotated_bounds}")
    
    # Step 2: Translate to grid position (like bin packing does)
    # This is where the bin packing algorithm calculates the translation offset
    translation_x = grid_x - rotated_bounds[0]
    translation_y = grid_y - rotated_bounds[1]
    
    final_polygon = translate_polygon(rotated_original, translation_x, translation_y)
    
    print(f"   2. Перемещение на позицию сетки ({grid_x}, {grid_y}):")
    print(f"      • Смещение: ({translation_x:.2f}, {translation_y:.2f})")
    print(f"      • Финальный центроид: ({final_polygon.centroid.x:.2f}, {final_polygon.centroid.y:.2f})")
    print(f"      • Финальные границы: {final_polygon.bounds}")
    
    # Now create the placed_elements as bin packing would
    # Format: (transformed_polygon, x_offset, y_offset, rotation_angle, filename, color)
    # The x_offset and y_offset are what was used to move from bounds to grid position
    placed_elements = [(final_polygon, translation_x, translation_y, angle, os.path.basename(sample_file), "серый")]
    
    print(f"\n📦 Элемент для размещения:")
    print(f"   • Полигон: центроид ({final_polygon.centroid.x:.2f}, {final_polygon.centroid.y:.2f})")
    print(f"   • Смещения: ({translation_x:.2f}, {translation_y:.2f})")
    print(f"   • Угол: {angle}°")
    
    # Create test output
    test_output = "test_realistic_rotation.dxf"
    original_dxf_data_map = {os.path.basename(sample_file): parsed_data}
    sheet_size = (200, 200)  # 200x200 cm sheet
    
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
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_rotation_realistic()
    print(f"\n{'🎉 Тест пройден!' if success else '❌ Тест не пройден!'}")