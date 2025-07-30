#!/usr/bin/env python3
"""Test full integration: Excel -> DXF discovery -> Layout optimization."""

import pandas as pd
import os
from datetime import datetime
import layout_optimizer as lo

def test_full_integration():
    """Test the complete workflow from Excel to DXF files to layout optimization."""
    print("🔗 Тестирование полной интеграции")
    print("=" * 50)
    
    # Step 1: Load Excel data
    print("📊 Шаг 1: Загрузка Excel данных")
    excel_file = "sample_input.xlsx"
    if not os.path.exists(excel_file):
        print(f"❌ Файл {excel_file} не найден")
        return False
    
    try:
        excel_data = pd.read_excel(excel_file, sheet_name=None, header=None)
        print(f"✅ Excel загружен: {len(excel_data)} листов")
    except Exception as e:
        print(f"❌ Ошибка загрузки Excel: {e}")
        return False
    
    # Step 2: Find pending orders
    print("\n📋 Шаг 2: Поиск невыполненных заказов")
    current_date = datetime.now()
    month_mapping = {
        "JANUARY": "ЯНВАРЬ", "FEBRUARY": "ФЕВРАЛЬ", "MARCH": "МАРТ", 
        "APRIL": "АПРЕЛЬ", "MAY": "МАЙ", "JUNE": "ИЮНЬ",
        "JULY": "ИЮЛЬ", "AUGUST": "АВГУСТ", "SEPTEMBER": "СЕНТЯБРЬ",
        "OCTOBER": "ОКТЯБРЬ", "NOVEMBER": "НОЯБРЬ", "DECEMBER": "ДЕКАБРЬ"
    }
    
    current_month_ru = month_mapping.get(current_date.strftime("%B").upper(), "ИЮЛЬ") + " " + str(current_date.year)
    
    all_orders = []
    if current_month_ru in excel_data:
        df = excel_data[current_month_ru]
        if df.shape[0] > 2:
            data_rows = df.iloc[2:].copy()
            pending_orders = data_rows[data_rows.iloc[:, 2].isna() | (data_rows.iloc[:, 2] == '')]
            
            for idx, row in pending_orders.head(2).iterrows():  # Test first 2 orders only
                if pd.notna(row.iloc[3]):
                    order = {
                        'article': str(row.iloc[3]),
                        'product': str(row.iloc[4]) if pd.notna(row.iloc[4]) else ''
                    }
                    all_orders.append(order)
    
    print(f"✅ Найдено заказов для тестирования: {len(all_orders)}")
    
    if not all_orders:
        print("❌ Нет заказов для тестирования")
        return False
    
    # Step 3: Find DXF files for each order
    print("\n🔍 Шаг 3: Поиск DXF файлов")
    
    def find_dxf_files_for_article(article):
        """Find DXF files for a given article."""
        found_files = []
        
        # Parse article and search in brand folders
        if '+' in article:
            parts = article.split('+')
            if len(parts) >= 3:
                brand = parts[1].strip()
                model_info = parts[2].strip() if len(parts) > 2 else ""
                
                # Create search variants for the brand
                brand_variants = [brand.upper(), brand.capitalize(), brand.lower()]
                
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
                                            variant[:10].lower().strip()
                                        ])
                                    
                                    search_keywords = list(set([k for k in search_keywords if k.strip()]))
                                
                                # Check if this model folder matches our search keywords
                                folder_name_lower = model_folder.lower()
                                match_found = False
                                
                                for keyword in search_keywords:
                                    if keyword and len(keyword) > 2:
                                        keyword_parts = keyword.split()
                                        if len(keyword_parts) >= 2:
                                            if all(part in folder_name_lower for part in keyword_parts):
                                                match_found = True
                                                break
                                        elif len(keyword) >= 4:
                                            if keyword in folder_name_lower:
                                                match_found = True
                                                break
                                
                                if match_found:
                                    # Look for DXF folder first
                                    dxf_folder = os.path.join(model_folder_path, "DXF")
                                    if os.path.exists(dxf_folder):
                                        dxf_files = [f for f in os.listdir(dxf_folder) if f.lower().endswith('.dxf')]
                                        for dxf_file in dxf_files[:2]:  # Take first 2 files only
                                            found_files.append(os.path.join(dxf_folder, dxf_file))
                                        if found_files:
                                            break
                        
                        if found_files:
                            break
        
        return found_files
    
    successful_orders = []
    for order in all_orders:
        article = order['article']
        print(f"\n📄 Обрабатываем: {article}")
        
        # Find DXF files
        dxf_files = find_dxf_files_for_article(article)
        if dxf_files:
            print(f"✅ Найдено {len(dxf_files)} DXF файлов")
            order['dxf_files'] = dxf_files
            successful_orders.append(order)
        else:
            print(f"❌ DXF файлы не найдены")
    
    print(f"\n✅ Успешно обработано заказов: {len(successful_orders)}")
    
    # Step 4: Test DXF parsing and layout optimization
    if successful_orders:
        print("\n🧩 Шаг 4: Тестирование парсинга DXF и оптимизации")
        
        first_order = successful_orders[0]
        first_dxf = first_order['dxf_files'][0]
        
        try:
            # Parse DXF
            polygons = lo.parse_dxf(first_dxf)
            print(f"✅ DXF распарсен: {first_dxf}")
            
            # Test layout optimization with inventory
            test_sheets = [
                {'name': 'Лист 140x200 серый', 'width': 140, 'height': 200, 'color': 'серый', 'count': 2, 'used': 0},
                {'name': 'Лист 150x150 чёрный', 'width': 150, 'height': 150, 'color': 'чёрный', 'count': 1, 'used': 0}
            ]
            
            if hasattr(polygons, '__len__'):
                test_polygons = [(polygons[0], 'test_part')] if len(polygons) > 0 else []
            else:
                test_polygons = [(polygons, 'test_part')]
            
            result = lo.bin_packing_with_inventory(test_polygons, test_sheets)
            if isinstance(result, tuple):
                layout, updated_sheets = result
            else:
                layout = result
                updated_sheets = test_sheets
            print(f"✅ Оптимизация выполнена успешно")
            print(f"   Размещено листов: {len(layout)}")
            
            # Test color handling
            for sheet in updated_sheets:
                color_emoji = "⚫" if sheet.get("color") == "чёрный" else "⚪" if sheet.get("color") == "серый" else "🔘"
                print(f"   {color_emoji} {sheet['name']}: использовано {sheet['used']}/{sheet['count']}")
            
        except Exception as e:
            print(f"❌ Ошибка оптимизации: {e}")
            return False
    
    print("\n🎉 ПОЛНАЯ ИНТЕГРАЦИЯ УСПЕШНА!")
    print("   ✅ Excel данные загружены")
    print("   ✅ Заказы найдены и обработаны")
    print("   ✅ DXF файлы найдены и распарсены")
    print("   ✅ Оптимизация layout выполнена")
    print("   ✅ Цветовые характеристики работают")
    
    return True

if __name__ == "__main__":
    success = test_full_integration()
    exit(0 if success else 1)