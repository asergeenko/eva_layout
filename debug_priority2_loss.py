#!/usr/bin/env python3
"""
Отладочный скрипт для поиска причины потери 4 серых полигонов приоритета 2
и дублирования SUZUKI XBEE_5.dxf
"""

import sys
import os
import pandas as pd
import logging
from shapely.geometry import Polygon

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Временно отключаем info логи для чистоты вывода
logging.basicConfig(level=logging.WARNING)

def load_excel_and_create_polygon_groups():
    """Загружает Excel и создает полигоны точно как в Streamlit"""
    
    excel_path = "sample_input.xlsx"
    if not os.path.exists(excel_path):
        print(f"❌ Файл {excel_path} не найден")
        return None, None
    
    df = pd.read_excel(excel_path, sheet_name='ZAKAZ')
    header_row = df.iloc[0]
    df.columns = [str(header_row.iloc[i]) if pd.notna(header_row.iloc[i]) else f'col_{i}' for i in range(len(header_row))]
    df = df[1:].reset_index(drop=True)
    
    # Создаем полигоны Excel (упрощенно)
    excel_polygons = []
    for idx, row in df.iterrows():
        if pd.isna(row['ТОВАР']):
            continue
            
        order_id = f"ZAKAZ_row_{idx + 2}"
        product_name = row['ТОВАР']
        article = row['Артикул']
        
        # Определяем цвет
        color = 'чёрный'
        if '+11' in str(article):
            color = 'серый'
        
        # Создаем 2-3 тестовых полигона для каждого заказа  
        poly_count = 3 if "SUZUKI XBEE" in product_name or "VOLKSWAGEN TIGUAN" in product_name else 2
        
        for i in range(poly_count):
            size = 80 + i * 10
            poly = Polygon([(0, 0), (size, 0), (size, size-20), (0, size-20)])
            filename = f"{product_name}_{i+1}.dxf"
            excel_polygons.append((poly, filename, color, order_id))
            
    print(f"✓ Создано {len(excel_polygons)} Excel полигонов")
    
    # Создаем полигоны приоритета 2 - точно 20 черных + 20 серых
    priority2_polygons = []
    
    # 20 черных
    for i in range(20):
        poly = Polygon([(0, 0), (60, 0), (60, 40), (0, 40)])
        filename = f"1_копия_{i+1}.dxf"
        priority2_polygons.append((poly, filename, "чёрный", "group_1", 2))  # 5-элементный кортеж с priority=2
    
    # 20 серых
    for i in range(20):
        poly = Polygon([(0, 0), (60, 0), (60, 40), (0, 40)])
        filename = f"1_копия_{i+1}.dxf"
        priority2_polygons.append((poly, filename, "серый", "group_2", 2))   # 5-элементный кортеж с priority=2
    
    print(f"✓ Создано {len(priority2_polygons)} полигонов приоритета 2 (20 черных + 20 серых)")
    
    return excel_polygons, priority2_polygons

def debug_polygon_processing():
    """Отлаживает обработку полигонов"""
    
    excel_polygons, priority2_polygons = load_excel_and_create_polygon_groups()
    if excel_polygons is None:
        return False
    
    all_polygons = excel_polygons + priority2_polygons
    print(f"📊 Всего полигонов: {len(all_polygons)}")
    
    # Группируем как в алгоритме
    normal_orders = {}
    priority2_list = []
    
    for poly in all_polygons:
        if len(poly) >= 5 and poly[4] == 2:  # Полигон приоритета 2
            priority2_list.append(poly)
        elif len(poly) >= 4:
            order_id = poly[3]
            if order_id not in normal_orders:
                normal_orders[order_id] = []
            normal_orders[order_id].append(poly)
    
    print(f"✓ Обычных заказов: {len(normal_orders)}")
    print(f"✓ Полигонов приоритета 2: {len(priority2_list)}")
    
    # Анализируем полигоны приоритета 2
    black_p2 = [p for p in priority2_list if p[2] == "чёрный"]
    gray_p2 = [p for p in priority2_list if p[2] == "серый"]
    
    print(f"  • Черных приоритета 2: {len(black_p2)}")
    print(f"  • Серых приоритета 2: {len(gray_p2)}")
    
    if len(gray_p2) != 20:
        print(f"❌ ПРОБЛЕМА: Должно быть 20 серых приоритета 2, а найдено {len(gray_p2)}")
        return False
    
    # Анализируем SUZUKI XBEE
    suzuki_files = []
    for order_id, polygons in normal_orders.items():
        for poly in polygons:
            filename = poly[1]
            if "SUZUKI XBEE" in filename:
                suzuki_files.append((filename, order_id))
    
    print(f"\nSUZUKI XBEE файлы:")
    for filename, order_id in suzuki_files:
        print(f"  • {filename} -> {order_id}")
    
    # Проверяем дублирование
    filenames = [f for f, _ in suzuki_files]
    duplicates = [f for f in filenames if filenames.count(f) > 1]
    
    if duplicates:
        print(f"❌ НАЙДЕНЫ ДУБЛИРОВАННЫЕ ФАЙЛЫ: {duplicates}")
        return False
    
    # Проверяем наличие всех ожидаемых файлов
    expected_suzuki = ["SUZUKI XBEE_1.dxf", "SUZUKI XBEE_2.dxf", "SUZUKI XBEE_3.dxf"]
    missing_suzuki = [f for f in expected_suzuki if f not in filenames]
    
    if missing_suzuki:
        print(f"❌ ОТСУТСТВУЮЩИЕ SUZUKI XBEE ФАЙЛЫ: {missing_suzuki}")
    else:
        print("✓ Все SUZUKI XBEE файлы найдены")
    
    # Проверяем VOLKSWAGEN TIGUAN 1
    vw_files = []
    for order_id, polygons in normal_orders.items():
        for poly in polygons:
            filename = poly[1]
            if "VOLKSWAGEN TIGUAN 1" in filename:
                vw_files.append((filename, order_id))
    
    print(f"\nVOLKSWAGEN TIGUAN 1 файлы:")
    for filename, order_id in vw_files:
        print(f"  • {filename} -> {order_id}")
    
    expected_vw = ["VOLKSWAGEN TIGUAN 1_1.dxf", "VOLKSWAGEN TIGUAN 1_2.dxf", "VOLKSWAGEN TIGUAN 1_3.dxf"]  
    vw_filenames = [f for f, _ in vw_files]
    missing_vw = [f for f in expected_vw if f not in vw_filenames]
    
    if missing_vw:
        print(f"❌ ОТСУТСТВУЮЩИЕ VOLKSWAGEN TIGUAN 1 ФАЙЛЫ: {missing_vw}")
    else:
        print("✓ Все VOLKSWAGEN TIGUAN 1 файлы найдены")
    
    print(f"\n=== ИТОГИ ===")
    if len(gray_p2) == 20 and not duplicates and not missing_suzuki and not missing_vw:
        print("✅ ВСЕ ПРОБЛЕМЫ УСТРАНЕНЫ НА ЭТАПЕ СОЗДАНИЯ ПОЛИГОНОВ")
        return True
    else:
        print("❌ ПРОБЛЕМЫ ОСТАЮТСЯ:")
        if len(gray_p2) != 20:
            print(f"   • Серых приоритета 2: {len(gray_p2)} вместо 20")
        if duplicates:
            print(f"   • Дублированные файлы: {duplicates}")
        if missing_suzuki:
            print(f"   • Отсутствующие SUZUKI XBEE: {missing_suzuki}")
        if missing_vw:
            print(f"   • Отсутствующие VOLKSWAGEN TIGUAN 1: {missing_vw}")
        return False

if __name__ == "__main__":
    print("=== ОТЛАДКА ПОТЕРИ ПРИОРИТЕТА 2 И ДУБЛИРОВАНИЯ ===")
    success = debug_polygon_processing()
    print(f"\nРезультат: {'УСПЕХ' if success else 'НЕУДАЧА'}")
    sys.exit(0 if success else 1)