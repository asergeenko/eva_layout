#!/usr/bin/env python3
"""Find AUDI A6 entries in Excel file."""

import pandas as pd

def find_audi_a6():
    print("🔍 Поиск записей AUDI A6 в Excel файле")
    print("=" * 50)
    
    try:
        # Read all sheets
        df_dict = pd.read_excel('sample_input.xlsx', sheet_name=None)
        
        audi_a6_entries = []
        
        for sheet_name, df in df_dict.items():
            if len(df) > 2:  # Skip sheets with less than 3 rows
                # Skip first 2 rows (headers), start from row 2 (index 2)
                data_rows = df.iloc[2:].copy()
                
                # Check if we have the necessary columns
                if df.shape[1] > 4:
                    for idx, row in data_rows.iterrows():
                        article = str(row.iloc[3]) if pd.notna(row.iloc[3]) else ''
                        product = str(row.iloc[4]) if pd.notna(row.iloc[4]) else ''
                        
                        # Look for AUDI A6 entries
                        if 'audi' in article.lower() and 'a6' in article.lower():
                            color = str(row.iloc[8]).lower().strip() if pd.notna(row.iloc[8]) and df.shape[1] > 8 else ''
                            audi_a6_entries.append({
                                'sheet': sheet_name,
                                'article': article,
                                'product': product,
                                'color': color,
                                'row': idx
                            })
        
        print(f"📋 Найдено записей AUDI A6: {len(audi_a6_entries)}")
        
        for entry in audi_a6_entries[:10]:  # Show first 10
            print(f"\n🚗 Лист: {entry['sheet']}")
            print(f"   Артикул: {entry['article']}")
            print(f"   Товар: {entry['product']}")
            print(f"   Цвет: {entry['color']}")
            
            # Test parsing
            if '+' in entry['article']:
                parts = entry['article'].split('+')
                if len(parts) >= 3:
                    brand = parts[1].strip()
                    model_info = parts[2].strip()
                    print(f"   -> Бренд: {brand}")
                    print(f"   -> Модель: {model_info}")
                    
                    # Show what folder we would look for
                    print(f"   -> Ищем папку: dxf_samples/{brand.upper()}/...")
                    print(f"   -> Поиск по модели: {model_info}")
            
        print(f"\n📁 Существующие папки AUDI A6:")
        import os
        audi_path = "dxf_samples/AUDI"
        if os.path.exists(audi_path):
            for folder in os.listdir(audi_path):
                if 'a6' in folder.lower():
                    print(f"   • {folder}")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    find_audi_a6()