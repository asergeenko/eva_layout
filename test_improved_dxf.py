#!/usr/bin/env python3
"""Simple test for improved DXF handling."""

import os
from layout_optimizer import parse_dxf_complete, save_dxf_layout_complete

def test_improved_dxf():
    """Test the improved DXF handling."""
    print("🧪 Тестирование улучшенной DXF обработки")
    print("=" * 50)
    
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
    
    # Test improved parsing
    with open(sample_file, 'rb') as f:
        parsed_data = parse_dxf_complete(f, verbose=True)
    
    if parsed_data and parsed_data['combined_polygon']:
        print(f"✅ Парсинг успешен!")
        print(f"   • Элементов: {len(parsed_data['original_entities'])}")
        print(f"   • Полигонов: {len(parsed_data['polygons'])}")
        print(f"   • Площадь: {parsed_data['combined_polygon'].area:.2f} мм²")
        
        # Test improved output
        test_output = "test_output_improved.dxf"
        original_dxf_data_map = {os.path.basename(sample_file): parsed_data}
        placed_elements = [(parsed_data['combined_polygon'], 50, 50, 0, os.path.basename(sample_file), "серый")]
        sheet_size = (200, 200)  # 200x200 cm
        
        try:
            save_dxf_layout_complete(placed_elements, sheet_size, test_output, original_dxf_data_map)
            
            if os.path.exists(test_output):
                print(f"✅ Создан улучшенный выходной файл: {test_output}")
                
                # Analyze improved output
                with open(test_output, 'rb') as f:
                    improved_result = parse_dxf_complete(f, verbose=False)
                
                print(f"📊 Сравнение:")
                print(f"   Исходный → Улучшенный выход:")
                print(f"   • Элементов: {len(parsed_data['original_entities'])} → {len(improved_result['original_entities']) if improved_result else 0}")
                
                # Clean up
                os.remove(test_output)
                return True
            else:
                print("❌ Не удалось создать улучшенный выходной файл")
                return False
                
        except Exception as e:
            print(f"❌ Ошибка сохранения: {e}")
            return False
    else:
        print("❌ Парсинг не удался")
        return False

if __name__ == "__main__":
    success = test_improved_dxf()
    print(f"\n{'🎉 Тест пройден!' if success else '❌ Тест не пройден!'}")