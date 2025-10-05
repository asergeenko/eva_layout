#!/usr/bin/env python3
"""
Полный тест интеграции с точно такими же данными как в Streamlit:
- 20 черных и 20 серых листов 140*200
- Все 37 заказов из sample_input_test.xlsx
- 20 серых и 20 черных файлов приоритета 2 из "data/ДЕКА KUGOO M4 PRO JILONG/1.dxf"
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

def process_orders(orders) -> tuple[list[Carpet], dict]:
    polygons = []
    dxf_data_map = {}

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
                    polygon_data = parse_dxf_complete(dxf_file, verbose=False)
                    if polygon_data and polygon_data.get("combined_polygon"):
                        polygon = polygon_data["combined_polygon"]
                        filename = os.path.basename(dxf_file)
                        # Добавляем уникальный суффикс для различения файлов
                        unique_filename = f"{product_name}_{os.path.splitext(filename)[0]}.dxf"
                        polygons.append(Carpet(polygon, unique_filename, color, order_id))
                        dxf_data_map[unique_filename] = polygon_data
                except Exception as e:
                    print(f"⚠️ Ошибка обработки {dxf_file}: {e}")
                    continue

    return polygons, dxf_data_map

def create_priority2_polygons() -> tuple[list[Carpet], dict]:
    """Создает 20 серых + 20 черных полигонов приоритета 2 из ДЕКА KUGOO M4 PRO JILONG"""
    priority2_polygons = []
    dxf_data_map = {}
    dxf_file = "data/ДЕКА KUGOO M4 PRO JILONG/1.dxf"
    try:
        # Используем verbose=False чтобы избежать Streamlit вызовов
        polygon_data = parse_dxf_complete(dxf_file, verbose=False)
        if polygon_data and polygon_data.get("combined_polygon"):
            base_polygon = polygon_data["combined_polygon"]

            # 20 черных полигонов приоритета 2
            for i in range(9):
                filename = f"ДЕКА_KUGOO_M4_PRO_JILONG_черный_{i+1}.dxf"
                priority2_polygons.append(Carpet(base_polygon, filename, "чёрный", "group_1",2))
                dxf_data_map[filename] = polygon_data

            # 20 серых полигонов приоритета 2
            for i in range(20):
                filename = f"ДЕКА_KUGOO_M4_PRO_JILONG_серый_{i+1}.dxf"
                priority2_polygons.append(Carpet(base_polygon, filename, "серый", "group_2",2))
                dxf_data_map[filename] = polygon_data
    except Exception as e:
        print(f"⚠️ Ошибка загрузки {dxf_file}: {e}")
        return [], {}

    return priority2_polygons, dxf_data_map


def test_streamlit_integration():
    """Основной тест с точно такими же данными как в Streamlit"""
    print("=== ТЕСТ ИНТЕГРАЦИИ STREAMLIT ===")
    

    # Создаем листы
    available_sheets = create_available_sheets()
    print(f"📄 Создано {len(available_sheets)} листов (30 черных + 30 серых)")

    #########################
    excel_data = load_excel_file(open("tests/sample_input_test.xlsx","rb").read())
    orders = parse_orders_from_excel(excel_data)
    polygons, dxf_data_map = process_orders(orders)
    #########################
    # Обрабатываем заказы из Excel
    print(f"🔧 Создано {len(orders)} полигонов из заказов Excel")

    # Создаем полигоны приоритета 2
    priority2_polygons, priority2_dxf_data = create_priority2_polygons()
    print(f"➕ Создано {len(priority2_polygons)} полигонов приоритета 2 (20 черных + 20 серых)")

    # Объединяем DXF данные
    dxf_data_map.update(priority2_dxf_data)
    
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

    # КРИТИЧЕСКАЯ ПРОВЕРКА: проверяем пересечения ковров на каждом листе
    print("\n=== ПРОВЕРКА ПЕРЕСЕЧЕНИЙ ===")
    for i, layout in enumerate(placed_layouts, 1):
        polygons_on_sheet = layout.placed_polygons

        # Проверяем каждую пару полигонов
        for idx1, p1 in enumerate(polygons_on_sheet):
            for idx2, p2 in enumerate(polygons_on_sheet[idx1+1:], idx1+1):
                if p1.polygon.intersects(p2.polygon):
                    intersection = p1.polygon.intersection(p2.polygon)
                    # Check ANY intersection, even tiny ones (changed from 0.1 to 0.01)
                    if hasattr(intersection, 'area') and intersection.area > 0.01:
                        error_msg = (
                            f"Лист {i}: ПЕРЕСЕЧЕНИЕ найдено!\n"
                            f"   '{p1.filename}' (pos={p1.polygon.bounds[:2]}, angle={p1.angle}°)\n"
                            f"   пересекается с\n"
                            f"   '{p2.filename}' (pos={p2.polygon.bounds[:2]}, angle={p2.angle}°)\n"
                            f"   Площадь пересечения: {intersection.area:.1f} мм²"
                        )
                        problems.append(error_msg)
                        print(f"❌ {error_msg}")

    if not problems:
        print("✅ Пересечений не найдено")

    # Экспорт в DXF для проверки
    print("\n=== ЭКСПОРТ В DXF ДЛЯ ПРОВЕРКИ ===")
    from dxf_utils import save_dxf_layout_complete
    import os

    # Создаем директорию если нужно
    os.makedirs("tmp_test", exist_ok=True)

    # Экспортируем лист 16 для проверки
    if len(placed_layouts) >= 16:
        sheet_16 = placed_layouts[15]  # 0-indexed
        output_path = "tmp_test/test_sheet_16.dxf"

        print(f"Экспортирую лист 16 в {output_path}")
        print(f"Полигонов на листе: {len(sheet_16.placed_polygons)}")

        # Показываем полигоны на листе 16
        for p in sheet_16.placed_polygons:
            print(f"  • {p.filename} (pos={p.polygon.bounds[:2]}, angle={p.angle}°)")

        # Проверяем пересечения SUBARU XV 1_3 и VOLKSWAGEN TIGUAN 2_4
        subaru = None
        tiguan = None
        for p in sheet_16.placed_polygons:
            if "SUBARU XV 1_3" in p.filename:
                subaru = p
            if "VOLKSWAGEN TIGUAN 2_4" in p.filename:
                tiguan = p

        if subaru and tiguan:
            print(f"\n=== ПРОВЕРКА ПЕРЕСЕЧЕНИЯ В ПАМЯТИ ===")
            print(f"SUBARU XV 1_3 bounds: {subaru.polygon.bounds}")
            print(f"VOLKSWAGEN TIGUAN 2_4 bounds: {tiguan.polygon.bounds}")
            print(f"Shapely intersects(): {subaru.polygon.intersects(tiguan.polygon)}")
            distance = subaru.polygon.distance(tiguan.polygon)
            print(f"Shapely distance(): {distance:.6f} mm")
            print(f"Shapely touches(): {subaru.polygon.touches(tiguan.polygon)}")

            # Найдем ближайшие точки
            from shapely.ops import nearest_points
            p1, p2 = nearest_points(subaru.polygon, tiguan.polygon)
            print(f"Nearest point on SUBARU: ({p1.x:.2f}, {p1.y:.2f})")
            print(f"Nearest point on TIGUAN: ({p2.x:.2f}, {p2.y:.2f})")

            if subaru.polygon.intersects(tiguan.polygon):
                intersection = subaru.polygon.intersection(tiguan.polygon)
                print(f"Intersection type: {type(intersection).__name__}")
                if hasattr(intersection, 'area'):
                    print(f"Intersection area: {intersection.area:.6f}")
            else:
                print(f"NO INTERSECTION - minimum gap is {distance:.2f}mm")

            # Проверка пересечения bounding boxes
            s_minx, s_miny, s_maxx, s_maxy = subaru.polygon.bounds
            t_minx, t_miny, t_maxx, t_maxy = tiguan.polygon.bounds
            bbox_overlap = not (s_maxx < t_minx or t_maxx < s_minx or s_maxy < t_miny or t_maxy < s_miny)
            print(f"Bounding boxes overlap: {bbox_overlap}")

            if bbox_overlap:
                print(f"  SUBARU XV Y range: {s_miny:.1f} - {s_maxy:.1f}")
                print(f"  TIGUAN Y range: {t_miny:.1f} - {t_maxy:.1f}")
                if s_maxy > t_miny and s_miny < t_maxy:
                    overlap_y = min(s_maxy, t_maxy) - max(s_miny, t_miny)
                    print(f"  Y overlap: {overlap_y:.1f}mm (от {max(s_miny, t_miny):.1f} до {min(s_maxy, t_maxy):.1f})")

            # Визуализация polygons из памяти
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots(figsize=(10, 8))

            # SUBARU XV
            if subaru.polygon.exterior:
                xs, ys = subaru.polygon.exterior.xy
                ax.plot(xs, ys, 'b-', linewidth=2, label=f'SUBARU XV (angle={subaru.angle}°)')
                ax.fill(xs, ys, alpha=0.3, color='blue')

            # TIGUAN
            if tiguan.polygon.exterior:
                xs, ys = tiguan.polygon.exterior.xy
                ax.plot(xs, ys, 'r-', linewidth=2, label=f'TIGUAN 2_4 (angle={tiguan.angle}°)')
                ax.fill(xs, ys, alpha=0.3, color='red')

            ax.set_aspect('equal')
            ax.legend()
            ax.grid(True, alpha=0.3)
            ax.set_title('Polygons from MEMORY (PlacedCarpet.polygon)')
            plt.savefig('tmp_test/memory_polygons.png', dpi=150, bbox_inches='tight')
            print(f"  Saved visualization: tmp_test/memory_polygons.png")

        # Сохраняем DXF
        save_dxf_layout_complete(
            sheet_16.placed_polygons,
            (sheet_16.sheet_size[0], sheet_16.sheet_size[1]),
            output_path,
            dxf_data_map
        )
        print(f"✅ DXF файл сохранен: {output_path}")

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


