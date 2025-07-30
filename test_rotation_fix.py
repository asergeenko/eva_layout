#!/usr/bin/env python3
"""Test rotation fix for DXF elements."""

import os
import numpy as np
from layout_optimizer import parse_dxf_complete, save_dxf_layout_complete, rotate_polygon

def test_rotation_fix():
    """Test that rotated DXF elements are positioned correctly."""
    print("🔄 Тестирование исправления поворота DXF элементов")
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
    
    print(f"📄 Тестируем с файлом: {os.path.basename(sample_file)}")
    
    # Parse original file
    with open(sample_file, 'rb') as f:
        parsed_data = parse_dxf_complete(f, verbose=False)
    
    if not parsed_data or not parsed_data['combined_polygon']:
        print("❌ Не удалось распарсить файл")
        return False
    
    original_polygon = parsed_data['combined_polygon']
    original_centroid = original_polygon.centroid
    
    print(f"📐 Исходный полигон:")
    print(f"   • Центроид: ({original_centroid.x:.2f}, {original_centroid.y:.2f})")
    print(f"   • Площадь: {original_polygon.area:.2f} мм²")
    
    # Test different rotation scenarios
    test_angles = [0, 90, 180, 270]
    
    for angle in test_angles:
        print(f"\n🔄 Тестирование поворота на {angle}°:")
        
        # Rotate polygon using the same method as bin packing
        rotated_polygon = rotate_polygon(original_polygon, angle)
        rotated_centroid = rotated_polygon.centroid
        
        print(f"   • Повернутый центроид: ({rotated_centroid.x:.2f}, {rotated_centroid.y:.2f})")
        
        # Create test output with translation
        x_offset, y_offset = 100, 200  # Test translation
        test_output = f"test_rotation_{angle}.dxf"
        original_dxf_data_map = {os.path.basename(sample_file): parsed_data}
        placed_elements = [(rotated_polygon, x_offset, y_offset, angle, os.path.basename(sample_file), "серый")]
        sheet_size = (500, 500)  # Large sheet
        
        try:
            save_dxf_layout_complete(placed_elements, sheet_size, test_output, original_dxf_data_map)
            
            if os.path.exists(test_output):
                print(f"   ✅ Создан файл с поворотом {angle}°: {test_output}")
                
                # Verify by parsing the output
                with open(test_output, 'rb') as f:
                    output_parsed = parse_dxf_complete(f, verbose=False)
                
                if output_parsed and output_parsed['combined_polygon']:
                    output_centroid = output_parsed['combined_polygon'].centroid
                    expected_x = rotated_centroid.x + x_offset
                    expected_y = rotated_centroid.y + y_offset
                    
                    print(f"   • Ожидаемый центроид: ({expected_x:.2f}, {expected_y:.2f})")
                    print(f"   • Фактический центроид: ({output_centroid.x:.2f}, {output_centroid.y:.2f})")
                    
                    # Check if positions match (within tolerance)
                    x_diff = abs(output_centroid.x - expected_x)
                    y_diff = abs(output_centroid.y - expected_y)
                    tolerance = 5.0  # 5mm tolerance
                    
                    if x_diff <= tolerance and y_diff <= tolerance:
                        print(f"   ✅ Позиция корректна (отклонение: {x_diff:.2f}, {y_diff:.2f})")
                    else:
                        print(f"   ❌ Позиция некорректна (отклонение: {x_diff:.2f}, {y_diff:.2f})")
                        return False
                else:
                    print(f"   ❌ Не удалось распарсить выходной файл")
                    return False
                
                # Clean up
                os.remove(test_output)
            else:
                print(f"   ❌ Не удалось создать файл с поворотом {angle}°")
                return False
                
        except Exception as e:
            print(f"   ❌ Ошибка при тестировании поворота {angle}°: {e}")
            return False
    
    print(f"\n🎉 Все тесты поворота пройдены успешно!")
    return True

if __name__ == "__main__":
    success = test_rotation_fix()
    print(f"\n{'🎉 Тест пройден!' if success else '❌ Тест не пройден!'}")