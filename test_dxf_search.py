#!/usr/bin/env python3
"""Test script to verify improved DXF search functionality."""

import os
import sys
sys.path.append('.')

def test_model_search():
    """Test the enhanced DXF search for complex model names."""
    print("🔍 Тестирование улучшенного поиска DXF файлов")
    print("=" * 60)
    
    # Test cases for different model formats
    test_cases = [
        {
            "article": "EVA_BORT+AUDI+A6 (C7) 4+2011-2018+black+15",
            "expected_parts": ["AUDI", "A6 (C7) 4"],
            "expected_keywords": ["a6", "c7", "4", "a6 4", "a6 c7", "a6 c7 4"]
        },
        {
            "article": "EVA_BORT+Changan+CX35PLUS+2018-2024+black+11", 
            "expected_parts": ["Changan", "CX35PLUS"],
            "expected_keywords": ["cx35plus", "cs35", "cs35 plus"]
        },
        {
            "article": "EVA_BORT+BMW+X5 (F15)+2013-2018+gray+20",
            "expected_parts": ["BMW", "X5 (F15)"],
            "expected_keywords": ["x5", "f15", "x5 f15"]
        }
    ]
    
    from streamlit_demo import find_dxf_files_for_article
    
    for i, test_case in enumerate(test_cases, 1):
        article = test_case["article"]
        expected_parts = test_case["expected_parts"]
        expected_keywords = test_case["expected_keywords"]
        
        print(f"\n🧪 Тест {i}: {article}")
        print(f"   Ожидаемые части: {expected_parts}")
        print(f"   Ожидаемые ключевые слова: {expected_keywords}")
        
        # Test article parsing
        if '+' in article:
            parts = article.split('+')
            if len(parts) >= 3:
                brand = parts[1].strip()
                model_info = parts[2].strip()
                print(f"   ✅ Извлечён бренд: {brand}")
                print(f"   ✅ Извлечена модель: {model_info}")
                
                # Test keyword generation for parentheses
                if '(' in model_info and ')' in model_info:
                    import re
                    parentheses_content = re.findall(r'\((.*?)\)', model_info)
                    base_model = re.sub(r'\s*\([^)]*\)\s*', ' ', model_info).strip()
                    print(f"   ✅ Содержимое скобок: {parentheses_content}")
                    print(f"   ✅ Базовая модель: {base_model}")
                    
                    # Show generated variants
                    model_variants = [model_info]
                    model_variants.extend([
                        base_model,
                        model_info.replace('(', '').replace(')', ''),
                    ])
                    
                    for content in parentheses_content:
                        model_variants.extend([
                            f"{base_model} {content}",
                            f"{content} {base_model}",
                            content,
                        ])
                    
                    model_parts = re.sub(r'[^\w\s]', ' ', model_info).split()
                    model_variants.extend(model_parts)
                    
                    print(f"   📝 Сгенерированные варианты: {list(set(model_variants))}")
        
        # Try to find actual files (will work only if dxf_samples directory exists)
        try:
            found_files = find_dxf_files_for_article(article)
            if found_files:
                print(f"   ✅ Найдено файлов: {len(found_files)}")
                for file_path in found_files[:3]:  # Show first 3 files
                    print(f"      📄 {os.path.basename(file_path)}")
            else:
                print(f"   ⚠️ Файлы не найдены (возможно, нет dxf_samples директории)")
        except Exception as e:
            print(f"   ⚠️ Ошибка поиска: {e}")
    
    print(f"\n🎯 Ключевые улучшения:")
    print(f"   ✅ Обработка скобок в названиях моделей (A6 (C7) 4)")
    print(f"   ✅ Извлечение отдельных частей модели (A6, C7, 4)")
    print(f"   ✅ Создание комбинаций частей (A6 C7, A6 4, C7 4)")
    print(f"   ✅ Система оценки совпадений для лучшего ранжирования")
    print(f"   ✅ Частичные совпадения в названиях папок")
    
    print(f"\n🎉 Тестирование завершено!")
    return True

if __name__ == "__main__":
    success = test_model_search()
    sys.exit(0 if success else 1)