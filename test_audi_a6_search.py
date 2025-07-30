#!/usr/bin/env python3
"""Test AUDI A6 (C7) 4 DXF search functionality."""

import os
import re

def test_audi_a6_search():
    """Test the search for AUDI A6 (C7) 4 DXF files."""
    print("🚗 Тестирование поиска DXF файлов для AUDI A6 (C7) 4")
    print("=" * 60)
    
    # Test data from Excel analysis
    article = "EVA_BORT+Audi+A6+2011-2018+black+12"
    product_name = "AUDI A6 (C7) 4"
    
    print(f"📋 Артикул: {article}")
    print(f"🏷️ Товар: {product_name}")
    print()
    
    # Simulate the improved search logic
    def search_by_product_name(product_name):
        """Search by product name logic."""
        found_files = []
        
        # Extract brand and model from product name
        product_upper = product_name.upper()
        
        # Handle common brand name mappings
        brand_mapping = {
            'AUDI': 'AUDI',
            'BMW': 'BMW',
            'MERCEDES': 'MERCEDES',
            'VOLKSWAGEN': 'VOLKSWAGEN',
            'FORD': 'FORD',
            'TOYOTA': 'TOYOTA',
            'NISSAN': 'NISSAN',
            'HYUNDAI': 'HYUNDAI',
            'KIA': 'KIA',
            'CHERY': 'CHERY',
            'CHANGAN': 'CHANGAN'
        }
        
        # Find brand in product name
        detected_brand = None
        for brand_key, brand_folder in brand_mapping.items():
            if brand_key in product_upper:
                detected_brand = brand_folder
                break
        
        print(f"🔍 Определён бренд: {detected_brand}")
        
        if detected_brand:
            brand_path = f"dxf_samples/{detected_brand}"
            if os.path.exists(brand_path):
                print(f"✅ Папка бренда найдена: {brand_path}")
                
                # Create search keywords from product name
                product_keywords = []
                
                # Clean product name and extract model parts
                model_part = product_upper.replace(detected_brand, '').strip()
                print(f"📝 Модельная часть: '{model_part}'")
                
                # Add full product name as keyword
                product_keywords.append(product_name.lower())
                
                # Handle parentheses and extract parts
                if '(' in model_part and ')' in model_part:
                    parentheses_content = re.findall(r'\((.*?)\)', model_part)
                    base_model = re.sub(r'\s*\([^)]*\)\s*', ' ', model_part).strip()
                    
                    print(f"🔖 Содержимое скобок: {parentheses_content}")
                    print(f"🔖 Базовая модель: '{base_model}'")
                    
                    product_keywords.extend([
                        base_model.lower(),
                        model_part.replace('(', '').replace(')', '').lower(),
                    ])
                    
                    for content in parentheses_content:
                        product_keywords.extend([
                            content.lower(),
                            f"{base_model} {content}".lower(),
                        ])
                
                # Extract individual parts
                model_parts = re.sub(r'[^\w\s]', ' ', model_part).split()
                product_keywords.extend([part.lower() for part in model_parts if len(part) > 1])
                
                # Remove duplicates
                product_keywords = list(set([k.strip() for k in product_keywords if k.strip()]))
                
                print(f"🔑 Сгенерированные ключевые слова:")
                for kw in sorted(product_keywords):
                    print(f"   • '{kw}'")
                print()
                
                # Search through brand folders
                print(f"📁 Поиск в папках бренда:")
                folders_found = []
                
                for model_folder in os.listdir(brand_path):
                    model_folder_path = os.path.join(brand_path, model_folder)
                    if os.path.isdir(model_folder_path):
                        folder_name_lower = model_folder.lower()
                        
                        # Calculate match score with Cyrillic/Latin normalization
                        match_score = 0
                        matched_keywords = []
                        
                        # Normalize folder name for better matching (handle Cyrillic/Latin)
                        normalized_folder = folder_name_lower
                        # Replace common Cyrillic letters with Latin equivalents
                        cyrillic_to_latin = {
                            'а': 'a', 'А': 'A',
                            'с': 'c', 'С': 'C',
                            'е': 'e', 'Е': 'E',
                            'о': 'o', 'О': 'O',
                            'р': 'p', 'Р': 'P',
                            'х': 'x', 'Х': 'X'
                        }
                        for cyrillic, latin in cyrillic_to_latin.items():
                            normalized_folder = normalized_folder.replace(cyrillic, latin)
                        
                        print(f"      Нормализованное имя: '{normalized_folder}'")
                        
                        for keyword in product_keywords:
                            if keyword and len(keyword) > 2:
                                # Direct match in normalized folder name
                                if keyword in normalized_folder:
                                    score_add = len(keyword) * 2
                                    match_score += score_add
                                    matched_keywords.append(f"'{keyword}' в нормализованном (+{score_add})")
                                # Direct match in original folder name
                                elif keyword in folder_name_lower:
                                    score_add = len(keyword) * 2
                                    match_score += score_add
                                    matched_keywords.append(f"'{keyword}' (+{score_add})")
                                else:
                                    # Check partial matches in normalized folder
                                    keyword_parts = keyword.split()
                                    matched_parts = sum(1 for part in keyword_parts 
                                                      if part in normalized_folder or part in folder_name_lower)
                                    if matched_parts > 0:
                                        score_add = matched_parts * 3
                                        match_score += score_add
                                        matched_keywords.append(f"'{keyword}' частично (+{score_add})")
                        
                        print(f"   📂 {model_folder}")
                        print(f"      Оценка: {match_score}")
                        if matched_keywords:
                            print(f"      Совпадения: {', '.join(matched_keywords)}")
                        
                        # If we have a good match, look for DXF files
                        if match_score >= 6:  # Threshold for product name matching
                            print(f"      ✅ Достаточная оценка для поиска DXF файлов!")
                            
                            dxf_folder = os.path.join(model_folder_path, "DXF")
                            if os.path.exists(dxf_folder):
                                dxf_files_found = [f for f in os.listdir(dxf_folder) if f.lower().endswith('.dxf')]
                                print(f"      📄 Найдено DXF файлов: {len(dxf_files_found)}")
                                for dxf_file in dxf_files_found:
                                    full_path = os.path.join(dxf_folder, dxf_file)
                                    found_files.append(full_path)
                                    print(f"         • {dxf_file}")
                                if found_files:
                                    folders_found.append(model_folder)
                                    break
                            else:
                                # Check for DXF files directly in model folder
                                dxf_files_found = [f for f in os.listdir(model_folder_path) if f.lower().endswith('.dxf')]
                                if dxf_files_found:
                                    print(f"      📄 Найдено DXF файлов (прямо в папке): {len(dxf_files_found)}")
                                    for dxf_file in dxf_files_found:
                                        full_path = os.path.join(model_folder_path, dxf_file)
                                        found_files.append(full_path)
                                        print(f"         • {dxf_file}")
                                    folders_found.append(model_folder)
                                    break
                        print()
                
                if folders_found:
                    print(f"🎉 Найдены подходящие папки: {', '.join(folders_found)}")
                else:
                    print("❌ Подходящие папки не найдены")
                    
            else:
                print(f"❌ Папка бренда не найдена: {brand_path}")
        
        return found_files
    
    # Run the test
    found_files = search_by_product_name(product_name)
    
    print(f"\n📊 Результат поиска:")
    if found_files:
        print(f"✅ Найдено {len(found_files)} DXF файлов:")
        for file_path in found_files:
            print(f"   📄 {file_path}")
    else:
        print("❌ DXF файлы не найдены")
    
    print(f"\n🎯 Заключение:")
    if found_files:
        print("✅ Улучшенный алгоритм поиска по названию товара работает!")
        print("✅ AUDI A6 (C7) 4 теперь будет найдена в приложении!")
    else:
        print("❌ Требуется дополнительная настройка алгоритма поиска")
    
    return len(found_files) > 0

if __name__ == "__main__":
    success = test_audi_a6_search()
    print(f"\n{'🎉 Тест пройден!' if success else '❌ Тест не пройден!'}")