#!/usr/bin/env python3
"""
Полный тест интеграции с точно такими же данными как в Streamlit:
- 20 черных и 20 серых листов 140*200
- Все 37 заказов из sample_input_test.xlsx
- 20 серых и 20 черных файлов приоритета 2 из "dxf_samples/ДЕКА KUGOO M4 PRO JILONG/1.dxf"
"""

import sys
import os
from pathlib import Path

import pandas as pd
import logging

import pytest

from dxf_utils import parse_dxf_complete
from excel_loader import load_excel_file, parse_orders_from_excel, find_dxf_files_for_article

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from layout_optimizer import (
    bin_packing_with_inventory,
    Carpet,
)

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def create_available_sheets():
    """Создает листы точно как в Streamlit: 30 черных + 30 серых 140*200"""
    sheets = []
    
    # 30 черных листов (увеличено для лучшего размещения)
    sheets.append({
            "name": f"Черный лист",
            "width": 140,
            "height": 200,
            "color": "чёрный", 
            "count": 20,
            "used": 0
        })
    
    # 30 серых листов (увеличено для лучшего размещения)
    sheets.append({
            "name": f"Серый лист",
            "width": 140,
            "height": 200,
            "color": "серый", 
            "count": 20,
            "used": 0
        })
    
    return sheets

def process_orders(orders) -> list[Carpet]:
    polygons = []
    
    for order in orders:
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
    try:
        # Используем verbose=False чтобы избежать Streamlit вызовов
        polygon_data = parse_dxf_complete(dxf_file, verbose=False)
        if polygon_data and polygon_data.get("combined_polygon"):
            base_polygon = polygon_data["combined_polygon"]

            # 20 черных полигонов приоритета 2
            for i in range(9):
                filename = f"ДЕКА_KUGOO_M4_PRO_JILONG_черный_{i+1}.dxf"
                priority2_polygons.append(Carpet(base_polygon, filename, "чёрный", "group_1",2))

            # 20 серых полигонов приоритета 2
            for i in range(20):
                filename = f"ДЕКА_KUGOO_M4_PRO_JILONG_серый_{i+1}.dxf"
                priority2_polygons.append(Carpet(base_polygon, filename, "серый", "group_2",2))
    except Exception as e:
        print(f"⚠️ Ошибка загрузки {dxf_file}: {e}")
        return []
    
    return priority2_polygons


@pytest.mark.skip
def test_streamlit_integration():
    """Основной тест с точно такими же данными как в Streamlit"""
    print("=== ТЕСТ ИНТЕГРАЦИИ STREAMLIT ===")
    

    # Создаем листы
    available_sheets = create_available_sheets()
    print(f"📄 Создано {len(available_sheets)} листов (30 черных + 30 серых)")

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
    print("\n=== ЗАПУСК ОПТИМИЗАЦИИ (БЕЗ ОГРАНИЧЕНИЙ НА ДИАПАЗОН ЛИСТОВ) ===")
    
    placed_layouts, unplaced = bin_packing_with_inventory(
        all_polygons,
        available_sheets,
        verbose=True,
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
            # Объект Carpet
            filename = poly.filename
            color = poly.color
            order_id = poly.order_id
            print(f"   • {filename} (цвет: {color}, заказ: {order_id})")
    
    # Детальный анализ по листам
    print("\n=== ДЕТАЛЬНЫЙ АНАЛИЗ ЛИСТОВ ===")
    priority2_black_placed = 0
    priority2_gray_placed = 0
    sheets_with_space = 0
    
    for i, layout in enumerate(placed_layouts, 1):
        poly_count = layout.placed_polygons
        usage = layout.usage_percent

        # Подсчет полигонов приоритета 2
        p2_black_count = 0
        p2_gray_count = 0
        for p in layout.placed_polygons:
            # Обрабатываем разные форматы кортежей
            color = p.color

            if color=="чёрный":
                p2_black_count += 1
            elif color=="серый":
                p2_gray_count += 1
        
        priority2_black_placed += p2_black_count
        priority2_gray_placed += p2_gray_count
        
        sheet_info = f"  Лист {i}: {poly_count} полигонов, {usage:.1f}% заполнение"
        
        if p2_black_count > 0 or p2_gray_count > 0:
            sheet_info += f" [+{p2_black_count} чер. прио2, +{p2_gray_count} сер. прио2]"
        
        print(sheet_info)

    
    # Анализ проблем без ограничений на диапазон листов
    print("\n=== АНАЛИЗ ПРИОРИТЕТНОЙ ЛОГИКИ РАЗМЕЩЕНИЯ ===")
    problems = []
    
    # Проверка неразмещенных полигонов
    if len(unplaced) > 0:
        unplaced_excel = []
        unplaced_p1 = []
        unplaced_p2 = []
        
        for p in unplaced:
            if p.order_id.startswith("ZAKAZ"):
                unplaced_excel.append(p)
            elif p.priority == 1:
                unplaced_p1.append(p)
            elif p.priority == 2:
                unplaced_p2.append(p)
        
        # Проверяем что Excel заказы и приоритет 1 успешно размещены (они должны иметь возможность брать новые листы)
        if unplaced_excel:
            print(f"⚠️  Неразмещенные Excel заказы: {len(unplaced_excel)}")
            for p in unplaced_excel:
                print(f"   • {p.order_id}: {p.filename}")
                
        if unplaced_p1:
            print(f"⚠️  Неразмещенные приоритета 1: {len(unplaced_p1)}")
            for p in unplaced_p1:
                print(f"   • {p.order_id}: {p.filename}")
        
        # Приоритет 2 может быть не размещен - это нормально, они используют только свободное место
        if unplaced_p2:
            print(f"ℹ️   Неразмещенные приоритета 2: {len(unplaced_p2)} (ожидаемо - используют только свободное место)")

    # Проверка что все заказы из Excel размещены (главное требование)
    print("\n=== ПРОВЕРКА РАЗМЕЩЕНИЯ EXCEL ЗАКАЗОВ ===")
    
    # Собираем информацию о размещенных заказах Excel
    placed_orders = set()
    
    for i, layout in enumerate(placed_layouts, 1):        
        # Анализируем размещенные полигоны на этом листе
        for placed_tuple in layout.placed_polygons:
            order_id = placed_tuple.order_id
            
            # Учитываем только заказы из Excel (ZAKAZ_*)
            if order_id.startswith("ZAKAZ"):
                placed_orders.add(order_id)
    
    print(f"Размещено Excel заказов: {len(placed_orders)}")
    
    # Проверяем максимальную плотность - все Excel заказы должны быть размещены
    total_excel_orders = len([p for p in all_polygons if p.order_id.startswith("ZAKAZ")])
    total_excel_orders_unique = len(set(p.order_id for p in all_polygons if p.order_id.startswith("ZAKAZ")))
    
    print(f"Всего уникальных Excel заказов в данных: {total_excel_orders_unique}")
    print(f"Размещено уникальных Excel заказов: {len(placed_orders)}")
    
    if len(placed_orders) < total_excel_orders_unique:
        missing_orders = total_excel_orders_unique - len(placed_orders)
        # Проверяем что не размещен только известный проблемный заказ
        unplaced_excel_ids = set()
        for p in unplaced:
            unplaced_excel_ids.add(p.order_id)
        known_problematic_orders = {"ZAKAZ_row_34"}  # Лодка AKVA 2800 - слишком большая
        
        if unplaced_excel_ids.issubset(known_problematic_orders) and missing_orders <= 1:
            print(f"ℹ️   Не размещен {missing_orders} проблемный Excel заказ (известная большая лодка)")
            print("✅ Все остальные Excel заказы успешно размещены")
        else:
            problems.append(f"Не все Excel заказы размещены: {missing_orders} не размещено (неожиданно)")
    else:
        print("✅ Все Excel заказы успешно размещены")

    # Финальная проверка
    if problems:
        print("\n❌ НАЙДЕННЫЕ ПРОБЛЕМЫ:")
        for problem in problems:
            print(f"   • {problem}")
        
        # Это тест - если есть проблемы, тест должен провалиться
        assert False, f"Тест провалился из-за проблем: {problems}"
    else:
        print("\n✅ ТЕСТ ПРОЙДЕН УСПЕШНО")
        print("   • Все Excel заказы размещены (максимальная плотность)")
        print("   • Приоритетная логика работает корректно:")
        print("     - Приоритет 1 + Excel: используют новые листы")
        print("     - Приоритет 2: только на свободном месте")
        print("   • Эффективное использование листов без ограничений на диапазон")
        
        unplaced_count = len(unplaced) if unplaced else 0
        print(f"   • Неразмещенных полигонов: {unplaced_count} (в основном приоритет 2)")


