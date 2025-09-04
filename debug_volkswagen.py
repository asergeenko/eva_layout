#!/usr/bin/env python3
"""
Debug script to understand why VOLKSWAGEN TIGUAN 1_3.dxf and 1_4.dxf are missing
"""

import sys
import os
import pandas as pd
from shapely.geometry import Polygon

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def debug_volkswagen_generation():
    """Debug how VOLKSWAGEN TIGUAN polygons are created"""
    
    # Load Excel data
    excel_path = "sample_input.xlsx"
    if not os.path.exists(excel_path):
        print(f"❌ Файл {excel_path} не найден")
        return
    
    df = pd.read_excel(excel_path, sheet_name='ZAKAZ')
    header_row = df.iloc[0]
    df.columns = [str(header_row.iloc[i]) if pd.notna(header_row.iloc[i]) else f'col_{i}' for i in range(len(header_row))]
    df = df[1:].reset_index(drop=True)
    
    print("=== ПОИСК VOLKSWAGEN TIGUAN 1 В EXCEL ===")
    volkswagen_rows = []
    
    for idx, row in df.iterrows():
        if pd.isna(row['ТОВАР']):
            continue
            
        product_name = row['ТОВАР']
        if "VOLKSWAGEN TIGUAN 1" in product_name:
            volkswagen_rows.append((idx, row))
            print(f"Найдена строка {idx+2}: {product_name}")
    
    if not volkswagen_rows:
        print("❌ VOLKSWAGEN TIGUAN 1 не найден в Excel")
        return
    
    # Анализируем создание полигонов
    print(f"\n=== АНАЛИЗ СОЗДАНИЯ ПОЛИГОНОВ ===")
    
    for idx, row in volkswagen_rows:
        order_id = f"ZAKAZ_row_{idx + 2}"
        article = row['Артикул']
        product_name = row['ТОВАР']
        
        print(f"\nСтрока {idx+2}: {product_name}")
        print(f"  • order_id: {order_id}")
        print(f"  • Артикул: {article}")
        
        # Определяем цвет
        color = 'чёрный'
        if '+12' in str(article):
            color = 'чёрный'
        elif '+11' in str(article):
            color = 'серый'
        print(f"  • Цвет: {color}")
        
        # Ищем DXF файлы
        dxf_files = []
        dxf_samples_dir = "dxf_samples"
        
        if os.path.exists(dxf_samples_dir):
            for root, dirs, files in os.walk(dxf_samples_dir):
                if product_name.upper() in root.upper():
                    print(f"  • Найдена директория: {root}")
                    for file in files:
                        if file.endswith('.dxf'):
                            dxf_files.append(os.path.join(root, file))
                            if len(dxf_files) >= 5:
                                break
                    if dxf_files:
                        break
        
        print(f"  • Найдено DXF файлов: {len(dxf_files)}")
        for dxf_file in dxf_files:
            print(f"    - {dxf_file}")
        
        # Симулируем создание полигонов
        created_polygons = []
        
        if dxf_files:
            # Fallback к синтетическим полигонам (как в тесте)
            for i, dxf_file in enumerate(dxf_files):
                size = 80 + i * 10  # Вариативные размеры
                poly = Polygon([(0, 0), (size, 0), (size, size-20), (0, size-20)])
                filename = f"{product_name}_{i+1}.dxf"
                created_polygons.append((poly, filename, color, order_id))
                print(f"    ✓ Создан полигон: {filename}")
        else:
            # Создаем синтетические полигоны если DXF не найдены
            poly_count = min(5, max(1, len(str(article).split('+'))))
            print(f"  • Создается {poly_count} синтетических полигонов")
            for i in range(poly_count):
                size = 80 + i * 15
                poly = Polygon([(0, 0), (size, 0), (size, size-30), (0, size-30)])
                filename = f"{product_name}_{i+1}.dxf"
                created_polygons.append((poly, filename, color, order_id))
                print(f"    ✓ Создан полигон: {filename}")
        
        print(f"  • ИТОГО создано полигонов: {len(created_polygons)}")
        
        # Проверяем наличие конкретных файлов
        created_filenames = [p[1] for p in created_polygons]
        target_files = ["VOLKSWAGEN TIGUAN 1_3.dxf", "VOLKSWAGEN TIGUAN 1_4.dxf"]
        
        for target in target_files:
            if target in created_filenames:
                print(f"    ✅ {target} - СОЗДАН")
            else:
                print(f"    ❌ {target} - НЕ СОЗДАН")

if __name__ == "__main__":
    debug_volkswagen_generation()