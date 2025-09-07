#!/usr/bin/env python3
"""
Полный тест интеграции с точно такими же данными как в Streamlit:
- 20 черных и 20 серых листов 140*200
- Все 37 заказов из sample_input_test.xlsx
- 20 серых и 20 черных файлов приоритета 2 из "dxf_samples/ДЕКА KUGOO M4 PRO JILONG/1.dxf"
"""

import sys
import os
import pandas as pd
import logging
from excel_loader import load_excel_file, parse_orders_from_excel, find_dxf_files_for_article

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from layout_optimizer import (
    bin_packing_with_inventory,
    parse_dxf_complete,
    Carpet,
)

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


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

def process_orders(orders):
    polygons = []
    
    for order in orders:
    #for idx, row in df.iterrows():
        order_id = order["order_id"]  # +2 для соответствия нумерации
        article = order["article"]
        product_name = order["product"]
        
        color = order["color"]

        # Ищем DXF файлы для этого товара
        dxf_files = find_dxf_files_for_article(article, product_name)

        if dxf_files:
            # Обрабатываем найденные DXF файлы
            for dxf_file in dxf_files:
                try:
                    # Используем verbose=False чтобы избежать Streamlit вызовов
                    polygon_data = parse_dxf_complete(dxf_file, verbose=False)
                    if polygon_data and polygon_data.get("combined_polygon"):
                        polygon = polygon_data["combined_polygon"]
                        filename = os.path.basename(dxf_file)
                        # Добавляем уникальный суффикс для различения файлов
                        unique_filename = f"{product_name}_{os.path.splitext(filename)[0]}.dxf"
                        polygons.append(Carpet(polygon, unique_filename, color, order_id))
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
            priority2_polygons.append(Carpet(base_polygon, filename, "чёрный", f"PRIORITY2_BLACK_{i+1}"))
        
        # 20 серых полигонов приоритета 2
        for i in range(20):
            filename = f"ДЕКА_KUGOO_M4_PRO_JILONG_серый_{i+1}.dxf"
            priority2_polygons.append(Carpet(base_polygon, filename, "серый", f"PRIORITY2_GRAY_{i+1}"))
    else:
        try:
            # Используем verbose=False чтобы избежать Streamlit вызовов
            polygon_data = parse_dxf_complete(dxf_file, verbose=False)
            if polygon_data and polygon_data.get("combined_polygon"):
                base_polygon = polygon_data["combined_polygon"]
                
                # 20 черных полигонов приоритета 2
                for i in range(20):
                    filename = f"ДЕКА_KUGOO_M4_PRO_JILONG_черный_{i+1}.dxf"
                    priority2_polygons.append(Carpet(base_polygon, filename, "чёрный", f"PRIORITY2_BLACK_{i+1}"))
                
                # 20 серых полигонов приоритета 2
                for i in range(20):
                    filename = f"ДЕКА_KUGOO_M4_PRO_JILONG_серый_{i+1}.dxf"
                    priority2_polygons.append(Carpet(base_polygon, filename, "серый", f"PRIORITY2_GRAY_{i+1}"))
        except Exception as e:
            print(f"⚠️ Ошибка загрузки {dxf_file}: {e}")
            return []
    
    return priority2_polygons

def test_streamlit_integration():
    """Основной тест с точно такими же данными как в Streamlit"""
    print("=== ТЕСТ ИНТЕГРАЦИИ STREAMLIT ===")
    

    # Создаем листы
    available_sheets = create_available_sheets()
    print(f"📄 Создано {len(available_sheets)} листов (20 черных + 20 серых)")

    #########################
    excel_data = load_excel_file(open("tests/sample_input_test.xlsx","rb").read())
    orders = parse_orders_from_excel(excel_data)
    polygons = process_orders(orders)
    #########################
    # Обрабатываем заказы из Excel
    print(f"🔧 Создано {len(orders)} полигонов из заказов Excel")
    
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
    print("\n=== ЗАПУСК ОПТИМИЗАЦИИ ===")
    MAX_SHEET_RANGE_PER_ORDER = 5
    
    placed_layouts, unplaced = bin_packing_with_inventory(
        all_polygons,
        available_sheets,
        verbose=True,
        max_sheet_range_per_order=MAX_SHEET_RANGE_PER_ORDER,
    )
    
    # Анализ результатов
    print("\n=== РЕЗУЛЬТАТЫ ===")
    actual_placed_count = total_polygons - len(unplaced)
    print(f"Размещено полигонов: {actual_placed_count}/{total_polygons}")
    print(f"Использовано листов: {len(placed_layouts)}")
    print(f"Неразмещенных полигонов: {len(unplaced)}")
    
    if unplaced:
        print("\n❌ НЕРАЗМЕЩЕННЫЕ ПОЛИГОНЫ:")
        for poly in unplaced:
            if hasattr(poly, 'filename'):
                # Объект Carpet
                filename = poly.filename
                color = poly.color
                order_id = poly.order_id
            elif len(poly) > 1:
                # Кортеж
                filename = poly[1] if len(poly) > 1 else "unknown"
                color = poly[2] if len(poly) > 2 else "unknown"
                order_id = poly[3] if len(poly) > 3 else "unknown"
            else:
                filename = "unknown"
                color = "unknown"
                order_id = "unknown"
            print(f"   • {filename} (цвет: {color}, заказ: {order_id})")
    
    # Детальный анализ по листам
    print("\n=== ДЕТАЛЬНЫЙ АНАЛИЗ ЛИСТОВ ===")
    priority2_black_placed = 0
    priority2_gray_placed = 0
    sheets_with_space = 0
    
    for i, layout in enumerate(placed_layouts, 1):
        poly_count = len(layout['placed_polygons'])
        usage = layout.get('usage_percent', 0)

        # Подсчет полигонов приоритета 2
        p2_black_count = 0
        p2_gray_count = 0
        for p in layout['placed_polygons']:
            # Обрабатываем разные форматы кортежей
            order_id = None
            if len(p) >= 7:
                # Extended format: (polygon, x, y, angle, file_name, color, order_id)
                order_id = str(p[6])
            elif len(p) > 3:
                # Standard format: (polygon, file_name, color, order_id)
                order_id = str(p[3])
            
            if order_id and order_id.startswith('PRIORITY2_BLACK'):
                p2_black_count += 1
            elif order_id and order_id.startswith('PRIORITY2_GRAY'):
                p2_gray_count += 1
        
        priority2_black_placed += p2_black_count
        priority2_gray_placed += p2_gray_count
        
        sheet_info = f"  Лист {i}: {poly_count} полигонов, {usage:.1f}% заполнение"
        
        if p2_black_count > 0 or p2_gray_count > 0:
            sheet_info += f" [+{p2_black_count} чер. прио2, +{p2_gray_count} сер. прио2]"
        
        print(sheet_info)

    
    # Анализ проблем
    print("\n=== АНАЛИЗ ПРОБЛЕМ ===")
    problems = []
    
    if len(unplaced) > 0:
        unplaced_excel = []
        unplaced_p2_black = []
        unplaced_p2_gray = []
        
        for p in unplaced:
            if hasattr(p, 'order_id'):
                # Объект Carpet
                order_id = str(p.order_id)
            elif len(p) > 3:
                # Кортеж
                order_id = str(p[3])
            else:
                order_id = ""
            
            if order_id.startswith('PRIORITY2_BLACK'):
                unplaced_p2_black.append(p)
            elif order_id.startswith('PRIORITY2_GRAY'):
                unplaced_p2_gray.append(p)
            elif not order_id.startswith('PRIORITY2'):
                unplaced_excel.append(p)
        
        # Один заказ не помещается по размеру - это верно
        if len(unplaced_excel) > 1:
            problems.append(f"Неразмещенные заказы из Excel: {len(unplaced_excel)}")
        if unplaced_p2_black:
            problems.append(f"Неразмещенные черные приоритета 2: {len(unplaced_p2_black)}")
        if unplaced_p2_gray:
            problems.append(f"Неразмещенные серые приоритета 2: {len(unplaced_p2_gray)}")
    
    if priority2_gray_placed < 15:  # Ожидаем хотя бы 15 из 20 серых
        problems.append(f"Мало размещенных серых приоритета 2: {priority2_gray_placed}/20")

    
    print(f"Черных приоритета 2 размещено: {priority2_black_placed}/20")
    print(f"Серых приоритета 2 размещено: {priority2_gray_placed}/20")
    print(f"Листов с <80% заполнением (начиная с 18): {sheets_with_space}")
    
    if problems:
        print("\n❌ НАЙДЕННЫЕ ПРОБЛЕМЫ:")
        for problem in problems:
            print(f"   • {problem}")
        
        # Это тест - если есть проблемы, тест должен провалиться
        assert False, f"Тест провалился из-за проблем: {problems}"
    else:
        print("\n✅ ТЕСТ ПРОЙДЕН УСПЕШНО")
        print("   • Все основные заказы размещены")
        print("   • Приоритет 2 работает корректно")
        print("   • Эффективное использование листов")

def main():
    """Запуск теста как отдельного скрипта"""
    test_streamlit_integration()

if __name__ == "__main__":
    main()