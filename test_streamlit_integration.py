#!/usr/bin/env python3
"""
Полный тест интеграции с точно такими же данными как в Streamlit:
- 20 черных и 20 серых листов 140*200
- Все 37 заказов из sample_input.xlsx
- 20 серых и 20 черных файлов приоритета 2 из "dxf_samples/ДЕКА KUGOO M4 PRO JILONG/1.dxf"
"""

import sys
import os
import pandas as pd
import pytest
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from layout_optimizer import (
    bin_packing_with_inventory,
    parse_dxf_complete,
)

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def load_sample_input_data():
    """Загружает данные из sample_input.xlsx точно как в Streamlit"""
    excel_path = "sample_input.xlsx"
    if not os.path.exists(excel_path):
        raise FileNotFoundError(f"Файл {excel_path} не найден")
    
    df = pd.read_excel(excel_path, sheet_name='ZAKAZ')
    
    # Первая строка содержит заголовки
    header_row = df.iloc[0]
    df.columns = [str(header_row.iloc[i]) if pd.notna(header_row.iloc[i]) else f'col_{i}' for i in range(len(header_row))]
    df = df[1:].reset_index(drop=True)
    
    return df

def create_available_sheets():
    """Создает листы точно как в Streamlit: 20 черных + 20 серых 140*200"""
    sheets = []
    
    # 20 черных листов
    for i in range(1, 21):
        sheets.append({
            "name": f"Черный лист {i}",
            "width": 140,
            "height": 200,
            "color": "чёрный", 
            "count": 1,
            "used": 0
        })
    
    # 20 серых листов
    for i in range(1, 21):
        sheets.append({
            "name": f"Серый лист {i}",
            "width": 140,
            "height": 200,
            "color": "серый", 
            "count": 1,
            "used": 0
        })
    
    return sheets

def process_orders_from_excel(df):
    """Обрабатывает заказы из Excel и создает полигоны"""
    polygons = []
    
    for idx, row in df.iterrows():
        order_id = f"ZAKAZ_row_{idx + 2}"  # +2 для соответствия нумерации
        article = row['Артикул']
        product_name = row['ТОВАР']
        
        # Определяем цвет по артикулу
        color = 'чёрный'
        if '+12' in str(article):
            color = 'чёрный'
        elif '+11' in str(article):
            color = 'серый'
        
        # Ищем DXF файлы для этого товара
        dxf_files = []
        dxf_samples_dir = "dxf_samples"
        
        if os.path.exists(dxf_samples_dir) and pd.notna(product_name):
            for root, dirs, files in os.walk(dxf_samples_dir):
                if str(product_name).upper() in root.upper():
                    for file in files:
                        if file.endswith('.dxf'):
                            dxf_files.append(os.path.join(root, file))
                            if len(dxf_files) >= 5:
                                break
                    if dxf_files:
                        break
        
        if dxf_files:
            # Обрабатываем найденные DXF файлы
            for dxf_file in dxf_files:
                try:
                    polygon_data = parse_dxf_complete(dxf_file)
                    if polygon_data and polygon_data[0]:
                        polygon = polygon_data[0]
                        filename = os.path.basename(dxf_file)
                        # Добавляем уникальный суффикс для различения файлов
                        unique_filename = f"{product_name}_{os.path.splitext(filename)[0]}.dxf"
                        polygons.append((polygon, unique_filename, color, order_id))
                except Exception as e:
                    print(f"⚠️ Ошибка обработки {dxf_file}: {e}")
                    continue
    
    return polygons

def create_priority2_polygons():
    """Создает 20 серых + 20 черных полигонов приоритета 2 из ДЕКА KUGOO M4 PRO JILONG"""
    priority2_polygons = []
    dxf_file = "dxf_samples/ДЕКА KUGOO M4 PRO JILONG/1.dxf"
    
    if not os.path.exists(dxf_file):
        print(f"⚠️ Файл {dxf_file} не найден, создаем синтетические полигоны")
        from shapely.geometry import Polygon
        # Создаем синтетический полигон размером примерно как коврик
        base_polygon = Polygon([(0, 0), (60, 0), (60, 40), (0, 40)])
        
        # 20 черных полигонов приоритета 2
        for i in range(20):
            filename = f"ДЕКА_KUGOO_M4_PRO_JILONG_черный_{i+1}.dxf"
            priority2_polygons.append((base_polygon, filename, "чёрный", f"PRIORITY2_BLACK_{i+1}"))
        
        # 20 серых полигонов приоритета 2
        for i in range(20):
            filename = f"ДЕКА_KUGOO_M4_PRO_JILONG_серый_{i+1}.dxf"
            priority2_polygons.append((base_polygon, filename, "серый", f"PRIORITY2_GRAY_{i+1}"))
    else:
        try:
            polygon_data = parse_dxf_complete(dxf_file)
            if polygon_data and polygon_data[0]:
                base_polygon = polygon_data[0]
                
                # 20 черных полигонов приоритета 2
                for i in range(20):
                    filename = f"ДЕКА_KUGOO_M4_PRO_JILONG_черный_{i+1}.dxf"
                    priority2_polygons.append((base_polygon, filename, "чёрный", f"PRIORITY2_BLACK_{i+1}"))
                
                # 20 серых полигонов приоритета 2
                for i in range(20):
                    filename = f"ДЕКА_KUGOO_M4_PRO_JILONG_серый_{i+1}.dxf"
                    priority2_polygons.append((base_polygon, filename, "серый", f"PRIORITY2_GRAY_{i+1}"))
        except Exception as e:
            print(f"⚠️ Ошибка загрузки {dxf_file}: {e}")
            return []
    
    return priority2_polygons

def test_streamlit_integration():
    """Основной тест с точно такими же данными как в Streamlit"""
    print("=== ТЕСТ ИНТЕГРАЦИИ STREAMLIT ===")
    
    # Загружаем данные Excel
    df = load_sample_input_data()
    print(f"📋 Загружено {len(df)} заказов из sample_input.xlsx")
    
    # Создаем листы
    available_sheets = create_available_sheets()
    print(f"📄 Создано {len(available_sheets)} листов (20 черных + 20 серых)")
    
    # Обрабатываем заказы из Excel
    polygons = process_orders_from_excel(df)
    print(f"🔧 Создано {len(polygons)} полигонов из заказов Excel")
    
    # Создаем полигоны приоритета 2
    priority2_polygons = create_priority2_polygons()
    print(f"➕ Создано {len(priority2_polygons)} полигонов приоритета 2 (20 черных + 20 серых)")
    
    # Объединяем все полигоны
    all_polygons = polygons + priority2_polygons
    total_polygons = len(all_polygons)
    print(f"📊 Всего полигонов для размещения: {total_polygons}")
    
    # Масштабируем полигоны
    if not all_polygons:
        print("❌ Нет полигонов для обработки")
        return

    # Запуск оптимизации
    print(f"\n=== ЗАПУСК ОПТИМИЗАЦИИ ===")
    MAX_SHEETS_PER_ORDER = 5
    
    placed_layouts, unplaced = bin_packing_with_inventory(
        all_polygons,
        available_sheets,
        verbose=True,
        max_sheets_per_order=MAX_SHEETS_PER_ORDER,
    )
    
    # Анализ результатов
    print(f"\n=== РЕЗУЛЬТАТЫ ===")
    actual_placed_count = total_polygons - len(unplaced)
    print(f"Размещено полигонов: {actual_placed_count}/{total_polygons}")
    print(f"Использовано листов: {len(placed_layouts)}")
    print(f"Неразмещенных полигонов: {len(unplaced)}")
    
    if unplaced:
        print(f"\n❌ НЕРАЗМЕЩЕННЫЕ ПОЛИГОНЫ:")
        for poly in unplaced:
            filename = poly[1] if len(poly) > 1 else "unknown"
            color = poly[2] if len(poly) > 2 else "unknown"
            order_id = poly[3] if len(poly) > 3 else "unknown"
            print(f"   • {filename} (цвет: {color}, заказ: {order_id})")
    
    # Детальный анализ по листам
    print(f"\n=== ДЕТАЛЬНЫЙ АНАЛИЗ ЛИСТОВ ===")
    priority2_black_placed = 0
    priority2_gray_placed = 0
    sheets_with_space = 0
    
    for i, layout in enumerate(placed_layouts, 1):
        poly_count = len(layout['placed_polygons'])
        usage = layout.get('usage_percent', 0)
        orders_on_sheet = layout.get('orders_on_sheet', set())
        
        # Подсчет полигонов приоритета 2
        p2_black_count = 0
        p2_gray_count = 0
        for p in layout['placed_polygons']:
            if len(p) > 3 and str(p[3]).startswith('PRIORITY2_BLACK'):
                p2_black_count += 1
            elif len(p) > 3 and str(p[3]).startswith('PRIORITY2_GRAY'):
                p2_gray_count += 1
        
        priority2_black_placed += p2_black_count
        priority2_gray_placed += p2_gray_count
        
        sheet_info = f"  Лист {i}: {poly_count} полигонов, {usage:.1f}% заполнение"
        
        if p2_black_count > 0 or p2_gray_count > 0:
            sheet_info += f" [+{p2_black_count} чер. прио2, +{p2_gray_count} сер. прио2]"
        
        print(sheet_info)
        
        # Отмечаем листы с большим количеством свободного места
        if usage < 80 and i >= 18:  # Начиная с листа 18, где пользователь заметил проблему
            sheets_with_space += 1
    
    # Анализ проблем
    print(f"\n=== АНАЛИЗ ПРОБЛЕМ ===")
    problems = []
    
    if len(unplaced) > 0:
        unplaced_excel = [p for p in unplaced if not str(p[3] if len(p) > 3 else "").startswith('PRIORITY2')]
        unplaced_p2_black = [p for p in unplaced if str(p[3] if len(p) > 3 else "").startswith('PRIORITY2_BLACK')]
        unplaced_p2_gray = [p for p in unplaced if str(p[3] if len(p) > 3 else "").startswith('PRIORITY2_GRAY')]
        
        if unplaced_excel:
            problems.append(f"Неразмещенные заказы из Excel: {len(unplaced_excel)}")
        if unplaced_p2_black:
            problems.append(f"Неразмещенные черные приоритета 2: {len(unplaced_p2_black)}")
        if unplaced_p2_gray:
            problems.append(f"Неразмещенные серые приоритета 2: {len(unplaced_p2_gray)}")
    
    if priority2_gray_placed < 15:  # Ожидаем хотя бы 15 из 20 серых
        problems.append(f"Мало размещенных серых приоритета 2: {priority2_gray_placed}/20")
    
    if sheets_with_space > 5:
        problems.append(f"Много листов с большим количеством свободного места: {sheets_with_space}")
    
    print(f"Черных приоритета 2 размещено: {priority2_black_placed}/20")
    print(f"Серых приоритета 2 размещено: {priority2_gray_placed}/20")
    print(f"Листов с <80% заполнением (начиная с 18): {sheets_with_space}")
    
    if problems:
        print(f"\n❌ НАЙДЕННЫЕ ПРОБЛЕМЫ:")
        for problem in problems:
            print(f"   • {problem}")
        
        # Это тест - если есть проблемы, тест должен провалиться
        assert False, f"Тест провалился из-за проблем: {problems}"
    else:
        print(f"\n✅ ТЕСТ ПРОЙДЕН УСПЕШНО")
        print(f"   • Все основные заказы размещены")
        print(f"   • Приоритет 2 работает корректно")
        print(f"   • Эффективное использование листов")

def main():
    """Запуск теста как отдельного скрипта"""
    test_streamlit_integration()

if __name__ == "__main__":
    main()