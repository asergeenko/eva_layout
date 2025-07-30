#!/usr/bin/env python3
"""Analyze sample_input.xlsx file structure."""

import pandas as pd

def analyze_excel():
    print("📊 Анализ файла sample_input.xlsx")
    print("=" * 50)
    
    try:
        # Read all sheets
        df_dict = pd.read_excel('sample_input.xlsx', sheet_name=None)
        
        print(f"📋 Найдено листов: {len(df_dict)}")
        print(f"🏷️ Названия листов: {list(df_dict.keys())}")
        print()
        
        for sheet_name, df in df_dict.items():
            print(f"📄 Лист '{sheet_name}':")
            print(f"   Размер: {df.shape[0]} строк, {df.shape[1]} колонок")
            print(f"   Колонки: {list(df.columns)}")
            print()
            
            # Show first few rows
            print("   Первые строки:")
            print(df.head(10).to_string(index=False))
            print()
            
            # Look for AUDI entries specifically
            if 'Товар' in df.columns:
                audi_rows = df[df['Товар'].str.contains('AUDI', case=False, na=False)]
                if not audi_rows.empty:
                    print(f"   🚗 Найдено записей AUDI: {len(audi_rows)}")
                    for idx, row in audi_rows.iterrows():
                        print(f"      • Артикул: {row.get('Артикул', 'N/A')}")
                        print(f"        Товар: {row.get('Товар', 'N/A')}")
                        if 'Цвет' in df.columns or df.shape[1] > 8:
                            color_col = df.columns[8] if df.shape[1] > 8 else 'Цвет'
                            print(f"        Цвет: {row.iloc[8] if df.shape[1] > 8 else 'N/A'}")
                        print()
            print("-" * 50)
            
    except Exception as e:
        print(f"❌ Ошибка чтения Excel файла: {e}")

if __name__ == "__main__":
    analyze_excel()