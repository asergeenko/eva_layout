#!/usr/bin/env python3
"""Test script for order loading functionality."""

import pandas as pd
import os
from datetime import datetime

def test_order_loading():
    """Test the order loading from Excel functionality."""
    print("📋 Тестирование загрузки заказов из Excel")
    print("=" * 50)
    
    # Test month detection
    current_date = datetime.now()
    month_mapping = {
        "JANUARY": "ЯНВАРЬ", "FEBRUARY": "ФЕВРАЛЬ", "MARCH": "МАРТ", 
        "APRIL": "АПРЕЛЬ", "MAY": "МАЙ", "JUNE": "ИЮНЬ",
        "JULY": "ИЮЛЬ", "AUGUST": "АВГУСТ", "SEPTEMBER": "СЕНТЯБРЬ",
        "OCTOBER": "ОКТЯБРЬ", "NOVEMBER": "НОЯБРЬ", "DECEMBER": "ДЕКАБРЬ"
    }
    
    current_month_ru = month_mapping.get(current_date.strftime("%B").upper(), "ИЮЛЬ") + " " + str(current_date.year)
    
    if current_date.month == 1:
        prev_month_ru = "ДЕКАБРЬ " + str(current_date.year - 1)
    else:
        prev_date = current_date.replace(month=current_date.month - 1)
        prev_month_ru = month_mapping.get(prev_date.strftime("%B").upper(), "ИЮНЬ") + " " + str(prev_date.year)
    
    print(f"🗓️ Текущий месяц: {current_month_ru}")
    print(f"🗓️ Предыдущий месяц: {prev_month_ru}")
    
    # Test Excel file reading
    excel_file = "sample_input.xlsx"
    if os.path.exists(excel_file):
        try:
            excel_data = pd.read_excel(excel_file, sheet_name=None, header=None)
            print(f"\n📊 Excel файл загружен успешно")
            print(f"   Количество листов: {len(excel_data)}")
            
            target_sheets = [current_month_ru, prev_month_ru]
            for sheet_name in target_sheets:
                if sheet_name in excel_data:
                    df = excel_data[sheet_name]
                    print(f"\n✅ Лист '{sheet_name}' найден")
                    print(f"   Размер: {df.shape[0]} строк, {df.shape[1]} столбцов")
                    
                    if df.shape[0] > 2:
                        data_rows = df.iloc[2:].copy()
                        # Check for empty "Сделано" column (index 2)
                        if df.shape[1] > 3:
                            pending_orders = data_rows[data_rows.iloc[:, 2].isna() | (data_rows.iloc[:, 2] == '')]
                            print(f"   Невыполненных заказов: {len(pending_orders)}")
                            
                            # Show first few examples
                            if len(pending_orders) > 0:
                                print("   Примеры:")
                                for i, (idx, row) in enumerate(pending_orders.head(3).iterrows()):
                                    if pd.notna(row.iloc[3]):
                                        article = str(row.iloc[3])
                                        product = str(row.iloc[4]) if pd.notna(row.iloc[4]) else ''
                                        print(f"     • {article} - {product[:50]}...")
                else:
                    print(f"❌ Лист '{sheet_name}' не найден")
        except Exception as e:
            print(f"❌ Ошибка чтения Excel файла: {e}")
    else:
        print(f"❌ Файл {excel_file} не найден")
    
    # Test DXF file search
    print(f"\n🔍 Тестирование поиска DXF файлов")
    
    def find_dxf_files_for_article(article):
        """Find DXF files for a given article by searching in the dxf_samples directory structure."""
        found_files = []
        
        # Strategy 1: Direct path mapping
        direct_path = f"dxf_samples/{article}"
        if os.path.exists(direct_path):
            dxf_files = [f for f in os.listdir(direct_path) if f.lower().endswith('.dxf')]
            for dxf_file in dxf_files:
                found_files.append(os.path.join(direct_path, dxf_file))
        
        # Strategy 2: Parse article and search in brand folders
        if not found_files and '+' in article:
            parts = article.split('+')
            if len(parts) >= 3:
                # Extract brand and model (e.g., EVA_BORT+Chery+Tiggo 4 -> Chery, Tiggo 4)
                brand = parts[1].strip()
                model_info = parts[2].strip() if len(parts) > 2 else ""
                
                # Create search variants for the brand
                brand_variants = [
                    brand.upper(),
                    brand.capitalize(),
                    brand.lower()
                ]
                
                # Find matching brand folder
                for brand_variant in brand_variants:
                    brand_path = f"dxf_samples/{brand_variant}"
                    if os.path.exists(brand_path):
                        # Look for model folders that might match
                        for model_folder in os.listdir(brand_path):
                            model_folder_path = os.path.join(brand_path, model_folder)
                            if os.path.isdir(model_folder_path):
                                # Create search keywords from model info
                                search_keywords = []
                                
                                # Clean model info and create variants
                                if model_info:
                                    # Handle specific transformations
                                    model_variants = [model_info]
                                    
                                    # Handle "CX35PLUS" -> "CS35", "CS35 PLUS" 
                                    if 'CX35PLUS' in model_info:
                                        model_variants.append(model_info.replace('CX35PLUS', 'CS35'))
                                        model_variants.append(model_info.replace('CX35PLUS', 'CS35 PLUS'))
                                    
                                    # Handle "PLUS" variations
                                    if 'PLUS' in model_info:
                                        model_variants.append(model_info.replace('PLUS', ' PLUS'))
                                        model_variants.append(model_info.replace('PLUS', ''))
                                    
                                    # Handle "PRO" variations
                                    if 'PRO' in model_info:
                                        model_variants.append(model_info.replace('PRO', ' PRO'))
                                        model_variants.append(model_info.replace('PRO', ''))
                                    
                                    # Create search keywords from all variants
                                    for variant in model_variants:
                                        search_keywords.extend([
                                            variant.lower().strip(),
                                            variant.replace(' ', '').lower(),
                                            variant[:10].lower().strip()  # First 10 chars
                                        ])
                                    
                                    # Remove duplicates and empty strings
                                    search_keywords = list(set([k for k in search_keywords if k.strip()]))
                                
                                # Debug output
                                if search_keywords:
                                    print(f"     🔍 Поиск в папке: {model_folder}")
                                    print(f"     🔑 Ключевые слова: {search_keywords[:3]}...")  # First 3 keywords
                                
                                # Check if this model folder matches our search keywords
                                folder_name_lower = model_folder.lower()
                                match_found = False
                                
                                for keyword in search_keywords:
                                    if keyword and len(keyword) > 2:  # Only check meaningful keywords
                                        # For exact model matches, require strong similarity
                                        keyword_parts = keyword.split()
                                        if len(keyword_parts) >= 2:
                                            # Multi-word keyword like "cs35 plus" or "tiggo 4"
                                            if all(part in folder_name_lower for part in keyword_parts):
                                                match_found = True
                                                break
                                        elif len(keyword) >= 4:
                                            # Single word keyword like "cs35" or "tiggo4"
                                            if keyword in folder_name_lower:
                                                match_found = True
                                                break
                                
                                if match_found:
                                    print(f"     🎯 Найдено совпадение: {model_folder}")
                                    # Look for DXF folder first
                                    dxf_folder = os.path.join(model_folder_path, "DXF")
                                    if os.path.exists(dxf_folder):
                                        dxf_files = [f for f in os.listdir(dxf_folder) if f.lower().endswith('.dxf')]
                                        for dxf_file in dxf_files:
                                            found_files.append(os.path.join(dxf_folder, dxf_file))
                                        if found_files:
                                            break
                                    else:
                                        # Look for DXF files directly in model folder
                                        dxf_files = [f for f in os.listdir(model_folder_path) if f.lower().endswith('.dxf')]
                                        for dxf_file in dxf_files:
                                            found_files.append(os.path.join(model_folder_path, dxf_file))
                                        if found_files:
                                            break
                        
                        if found_files:
                            break
        
        return found_files
    
    # Test with actual articles from Excel
    test_articles = [
        "EVA_BORT+Changan+CX35PLUS+2018-2024+black+11",
        "EVA_BORT+Chery+Tiggo 4+2017-2021+black+12",
        "EVA_BORT+Chery+Tiggo 4 PRO+2017-2021+black+12"
    ]
    
    for article in test_articles:
        print(f"\n📄 Тестируем артикул: {article}")
        found_files = find_dxf_files_for_article(article)
        if found_files:
            print(f"   ✅ Найдено {len(found_files)} DXF файлов:")
            for file_path in found_files[:3]:  # Show first 3
                print(f"     • {file_path}")
        else:
            print(f"   ❌ DXF файлы не найдены")
    
    print("\n🎉 Тестирование завершено!")
    return True

if __name__ == "__main__":
    test_order_loading()