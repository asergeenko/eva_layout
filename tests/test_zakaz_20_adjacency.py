#!/usr/bin/env python3
"""
Специальный тест для строгой проверки соблюдения MAX_SHEETS_PER_ORDER для заказа ZAKAZ_row_20
"""

import sys
import os
from shapely.geometry import Polygon

# Добавляем корневую директорию в путь для импорта модулей
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from layout_optimizer import bin_packing_with_inventory, Carpet


def test_zakaz_20_strict_adjacency():
    """Тест строгого соблюдения MAX_SHEETS_PER_ORDER для заказа ZAKAZ_row_20 в реалистичных условиях"""
    
    # Создаем листы как в реальном Streamlit
    available_sheets = [
        {
            "name": "Лист 140x200 чёрный",
            "width": 140,
            "height": 200,
            "color": "чёрный", 
            "count": 20,
            "used": 0,
        },
        {
            "name": "Лист 140x200 серый",
            "width": 140,
            "height": 200,
            "color": "серый",
            "count": 20,
            "used": 0,
        }
    ]
    
    # РЕАЛИСТИЧНАЯ СИТУАЦИЯ: Создаем много заказов с разными размерами
    # которые будут конкурировать за места на листах
    polygons = []
    
    # Заказ ZAKAZ_row_20 - 4 полигона разных размеров (в пределах MAX_SHEETS_PER_ORDER=7)
    zakaz_20_sizes = [(60, 40), (80, 30), (70, 50), (50, 60)]  # Разные размеры
    for i, (w, h) in enumerate(zakaz_20_sizes):
        poly = Polygon([(0, 0), (w, 0), (w, h), (0, h)])
        polygons.append(Carpet(poly, f"zakaz20_file_{i}.dxf", "чёрный", "ZAKAZ_row_20"))
    
    # МНОГО других заказов с БОЛЬШИМИ полигонами чтобы создать реальную конкуренцию
    # Это заставляет алгоритм делать сложные выборы размещения
    for order_num in range(1, 35):  # 34 других заказа
        if order_num == 20:
            continue  # Пропускаем, так как уже добавили ZAKAZ_row_20
        
        # Каждый заказ имеет 1-3 полигона разных размеров
        num_polygons = 1 + (order_num % 3)  # 1, 2 или 3 полигона
        for i in range(num_polygons):
            # Разные размеры полигонов - некоторые большие, некоторые маленькие
            if order_num % 4 == 0:
                # Большие полигоны, которые займут много места
                w, h = 90 + (i * 10), 80 + (i * 10)
            elif order_num % 4 == 1:
                # Средние полигоны
                w, h = 60 + (i * 5), 50 + (i * 5)
            else:
                # Маленькие полигоны
                w, h = 40 + (i * 3), 30 + (i * 3)
                
            poly = Polygon([(0, 0), (w, 0), (w, h), (0, h)])
            color = "чёрный" if order_num % 3 == 0 else "серый"
            polygons.append(Carpet(poly, f"order_{order_num}_file_{i}.dxf", color, f"ZAKAZ_row_{order_num}"))
    
    print(f"Создано {len(polygons)} полигонов")
    print("Заказ ZAKAZ_row_20 содержит 4 полигона")
    print("MAX_SHEETS_PER_ORDER = 7")
    
    # Запускаем оптимизацию с MAX_SHEETS_PER_ORDER = 7 (как у пользователя)
    MAX_SHEETS_PER_ORDER = 7
    
    placed_layouts, unplaced_polygons = bin_packing_with_inventory(
        polygons,
        available_sheets,
        verbose=True,
        max_sheets_per_order=MAX_SHEETS_PER_ORDER,
    )
    
    # Детальный анализ результатов для ZAKAZ_row_20
    zakaz_20_sheets = []
    zakaz_20_polygons_placed = 0
    zakaz_20_sheets_details = {}
    
    for layout in placed_layouts:
        if "orders_on_sheet" in layout and "ZAKAZ_row_20" in layout["orders_on_sheet"]:
            sheet_num = layout["sheet_number"]
            zakaz_20_sheets.append(sheet_num)
            zakaz_20_sheets_details[sheet_num] = []
            
            # Считаем полигоны ZAKAZ_row_20 на этом листе
            for poly_tuple in layout["placed_polygons"]:
                if len(poly_tuple) >= 7 and poly_tuple[6] == "ZAKAZ_row_20":
                    zakaz_20_polygons_placed += 1
                    zakaz_20_sheets_details[sheet_num].append(poly_tuple[4])  # filename
                elif len(poly_tuple) >= 4 and poly_tuple[3] == "ZAKAZ_row_20":
                    zakaz_20_polygons_placed += 1
                    zakaz_20_sheets_details[sheet_num].append(poly_tuple[1])  # filename
    
    # Считаем неразмещенные полигоны ZAKAZ_row_20
    zakaz_20_unplaced = 0
    unplaced_files = []
    for poly_tuple in unplaced_polygons:
        if len(poly_tuple) >= 4 and poly_tuple[3] == "ZAKAZ_row_20":
            zakaz_20_unplaced += 1
            unplaced_files.append(poly_tuple[1])
    
    print("\n=== ДЕТАЛЬНЫЙ АНАЛИЗ ЗАКАЗА ZAKAZ_row_20 ===")
    print(f"Полигонов размещено: {zakaz_20_polygons_placed}")
    print(f"Полигонов не размещено: {zakaz_20_unplaced}")
    print(f"Всего полигонов заказа: {zakaz_20_polygons_placed + zakaz_20_unplaced}")
    print(f"Листы с размещением: {sorted(zakaz_20_sheets)}")
    
    # Показываем детали размещения
    for sheet_num in sorted(zakaz_20_sheets):
        files = zakaz_20_sheets_details[sheet_num]
        print(f"  Лист {sheet_num}: {files}")
    
    if unplaced_files:
        print(f"Неразмещенные файлы: {unplaced_files}")
    
    # Показываем общую статистику
    print("\nОбщая статистика:")
    print(f"Всего листов создано: {len(placed_layouts)}")
    total_placed = sum(len(layout['placed_polygons']) for layout in placed_layouts)
    print(f"Всего полигонов размещено: {total_placed}")
    print(f"Всего полигонов не размещено: {len(unplaced_polygons)}")
    
    if zakaz_20_sheets:
        min_sheet = min(zakaz_20_sheets)
        max_sheet = max(zakaz_20_sheets)
        sheet_range = max_sheet - min_sheet + 1
        expected_max_sheet = min_sheet + MAX_SHEETS_PER_ORDER - 1
        
        print(f"Диапазон листов: {min_sheet} - {max_sheet} (размах: {sheet_range})")
        print(f"Ожидаемый максимум: {expected_max_sheet}")
        
        # СТРОГАЯ ПРОВЕРКА
        if sheet_range <= MAX_SHEETS_PER_ORDER and max_sheet <= expected_max_sheet:
            print("✅ ТЕСТ ПРОЙДЕН: Ограничение MAX_SHEETS_PER_ORDER соблюдено")
            
            # Дополнительная проверка: все ли полигоны заказа размещены?
            if zakaz_20_unplaced > 0:
                print(f"⚠️ ПРЕДУПРЕЖДЕНИЕ: {zakaz_20_unplaced} полигонов не размещены, хотя ограничение соблюдено")
                print("   Возможно, недостаточно места на листах или проблема с алгоритмом")
                return False  # Считаем тест неуспешным, если не все полигоны размещены
            
            return True
        else:
            print("❌ ТЕСТ НЕ ПРОЙДЕН: Нарушение ограничения MAX_SHEETS_PER_ORDER")
            print(f"   Диапазон {sheet_range} > {MAX_SHEETS_PER_ORDER} ИЛИ max_sheet {max_sheet} > {expected_max_sheet}")
            return False
    else:
        print("⚠️ Заказ ZAKAZ_row_20 вообще не был размещен")
        # В этом случае ограничение технически соблюдено, но это не оптимально
        return True


if __name__ == "__main__":
    success = test_zakaz_20_strict_adjacency()
    exit(0 if success else 1)