#!/usr/bin/env python3
"""Test improved AUDI A6 (C7) 4 DXF search functionality."""

import os
import re

def test_audi_a6_search_v2():
    """Test the improved search for AUDI A6 (C7) 4 DXF files."""
    print("🚗 Тестирование улучшенного поиска DXF файлов для AUDI A6 (C7) 4")
    print("=" * 70)
    
    # Test data from Excel analysis
    article = "EVA_BORT+Audi+A6+2011-2018+black+12"
    product_name = "AUDI A6 (C7) 4"
    
    print(f"📋 Артикул: {article}")
    print(f"🏷️ Товар: {product_name}")
    print()
    
    # Simulate the improved search logic with best match selection
    def search_by_product_name_v2(product_name):
        """Improved search by product name logic with best match selection."""
        found_files = []
        
        # Extract brand and model from product name
        product_upper = product_name.upper()
        
        # Handle common brand name mappings
        brand_mapping = {'AUDI': 'AUDI'}
        
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
                
                # Search through brand folders and find the best match
                best_match_folder = None
                best_match_score = 0
                all_folders_scores = []
                
                print(f"📁 Поиск в папках бренда:")
                
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
                        
                        # Special bonus for exact generation match (e.g., "(c7)" in folder)
                        if '(' in model_part and ')' in model_part:
                            parentheses_content = re.findall(r'\((.*?)\)', model_part)
                            for content in parentheses_content:
                                # Check for exact parentheses match in folder
                                if f"({content.lower()})" in normalized_folder:
                                    match_score += 20  # High bonus for exact generation match
                                    matched_keywords.append(f"'({content.lower()})' точное поколение (+20)")
                                elif f"({content.lower()})" in folder_name_lower:
                                    match_score += 20
                                    matched_keywords.append(f"'({content.lower()})' точное поколение кириллица (+20)")
                        
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
                        
                        all_folders_scores.append((model_folder, match_score))
                        
                        print(f"   📂 {model_folder}")
                        print(f"      Нормализованное: '{normalized_folder}'")
                        print(f"      Оценка: {match_score}")
                        if matched_keywords:
                            print(f"      Совпадения: {', '.join(matched_keywords)}")
                        
                        # Track the best match
                        if match_score > best_match_score and match_score >= 6:
                            best_match_score = match_score
                            best_match_folder = (model_folder, model_folder_path)
                        
                        print()
                
                # Sort by score to show ranking
                print(f"🏆 Рейтинг папок по оценке:")
                sorted_scores = sorted(all_folders_scores, key=lambda x: x[1], reverse=True)
                for i, (folder, score) in enumerate(sorted_scores[:5], 1):
                    status = "👑 ВЫБРАНА" if best_match_folder and folder == best_match_folder[0] else ""
                    print(f"   {i}. {folder}: {score} баллов {status}")
                print()
                
                # Try to get DXF files from the best matching folder
                if best_match_folder:
                    model_folder, model_folder_path = best_match_folder
                    print(f"🎯 Выбрана лучшая папка: {model_folder} (оценка: {best_match_score})")
                    
                    dxf_folder = os.path.join(model_folder_path, "DXF")
                    if os.path.exists(dxf_folder):
                        dxf_files_found = [f for f in os.listdir(dxf_folder) if f.lower().endswith('.dxf')]
                        print(f"📄 Найдено DXF файлов: {len(dxf_files_found)}")
                        for dxf_file in dxf_files_found:
                            full_path = os.path.join(dxf_folder, dxf_file)
                            found_files.append(full_path)
                            print(f"   • {dxf_file}")
                    else:
                        # Check for DXF files directly in model folder
                        dxf_files_found = [f for f in os.listdir(model_folder_path) if f.lower().endswith('.dxf')]
                        if dxf_files_found:
                            print(f"📄 Найдено DXF файлов (прямо в папке): {len(dxf_files_found)}")
                            for dxf_file in dxf_files_found:
                                full_path = os.path.join(model_folder_path, dxf_file)
                                found_files.append(full_path)
                                print(f"   • {dxf_file}")
                else:
                    print("❌ Подходящие папки не найдены")
                    
            else:
                print(f"❌ Папка бренда не найдена: {brand_path}")
        
        return found_files
    
    # Run the test
    found_files = search_by_product_name_v2(product_name)
    
    print(f"\n📊 Результат поиска:")
    if found_files:
        print(f"✅ Найдено {len(found_files)} DXF файлов:")
        for file_path in found_files:
            print(f"   📄 {file_path}")
    else:
        print("❌ DXF файлы не найдены")
    
    print(f"\n🎯 Заключение:")
    if found_files and "audi а6 (с7) 4" in found_files[0].lower():
        print("🎉 Отлично! Найдена правильная папка 'Audi А6 (С7) 4'!")
        print("✅ Улучшенный алгоритм работает идеально!")
    elif found_files:
        print("⚠️ Найдены файлы, но возможно не из оптимальной папки")
        print("🔧 Требуется дополнительная настройка оценки")
    else:
        print("❌ Требуется дополнительная настройка алгоритма поиска")
    
    return len(found_files) > 0

if __name__ == "__main__":
    success = test_audi_a6_search_v2()
    print(f"\n{'🎉 Тест пройден!' if success else '❌ Тест не пройден!'}")