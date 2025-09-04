#!/usr/bin/env python3
"""
Финальный тест всех исправлений алгоритма
"""

import sys
import os
import logging
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from layout_optimizer import bin_packing_with_inventory
from shapely.geometry import Polygon

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def main():
    print("=== ФИНАЛЬНЫЙ ТЕСТ АЛГОРИТМА ===")
    
    # Создаем тестовые данные, имитирующие проблему пользователя
    polygons = []
    
    # 5 больших заказов (по 4 полигона)
    for order_id in range(1, 6):
        for poly_id in range(4):
            poly = Polygon([(0, 0), (60, 0), (60, 40), (0, 40)])
            polygons.append((poly, f"big_order_{order_id}_{poly_id}.dxf", "чёрный", f"ZAKAZ_row_{order_id}"))
    
    # 15 маленьких заказов (по 1 полигону) - они должны заполнить свободное место
    for order_id in range(21, 36):  # ZAKAZ_row_21 до ZAKAZ_row_35
        poly = Polygon([(0, 0), (30, 0), (30, 20), (0, 20)])
        polygons.append((poly, f"small_order_{order_id}.dxf", "чёрный", f"ZAKAZ_row_{order_id}"))
    
    # Добавляем несколько серых полигонов приоритета 2
    priority2_polygons = []
    for i in range(5):  # 5 серых полигонов приоритета 2
        poly = Polygon([(0, 0), (25, 0), (25, 15), (0, 15)])
        priority2_polygons.append((poly, f"priority2_{i}.dxf", "серый", f"PRIORITY2_{i}"))
    
    # Создаем листы
    available_sheets = [
        {
            "name": f"Черный лист {i}",
            "width": 140,
            "height": 200,
            "color": "чёрный", 
            "count": 1,
            "used": 0
        }
        for i in range(1, 11)  # 10 черных листов
    ] + [
        {
            "name": f"Серый лист {i}",
            "width": 140,
            "height": 200,
            "color": "серый", 
            "count": 1,
            "used": 0
        }
        for i in range(1, 6)  # 5 серых листов
    ]
    
    total_polygons = len(polygons) + len(priority2_polygons)
    print(f"Создано {len(polygons)} основных полигонов + {len(priority2_polygons)} приоритета 2 = {total_polygons} всего")
    print(f"Доступно {len(available_sheets)} листов")
    
    # Запуск оптимизации
    print(f"\n=== ЗАПУСК ОПТИМИЗАЦИИ ===")
    MAX_SHEETS_PER_ORDER = 5
    
    placed_layouts, unplaced = bin_packing_with_inventory(
        polygons + priority2_polygons,  # Объединяем основные и приоритета 2
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
    
    # Детальный анализ
    single_polygon_sheets = 0
    mixed_orders = 0
    priority2_placed = 0
    
    print(f"\nДетали по листам:")
    for i, layout in enumerate(placed_layouts, 1):
        poly_count = len(layout['placed_polygons'])
        usage = layout.get('usage_percent', 0)
        orders_on_sheet = layout.get('orders_on_sheet', set())
        
        # Подсчет полигонов приоритета 2
        p2_count = sum(1 for p in layout['placed_polygons'] if 'PRIORITY2' in str(p))
        if p2_count > 0:
            priority2_placed += p2_count
        
        # Анализ типов заказов
        big_orders = [o for o in orders_on_sheet if o.startswith('ZAKAZ_row_') and int(o.split('_')[-1]) <= 5]
        small_orders = [o for o in orders_on_sheet if o.startswith('ZAKAZ_row_') and int(o.split('_')[-1]) >= 21]
        
        sheet_info = f"  Лист {i}: {poly_count} полигонов, {usage:.1f}% заполнение"
        if big_orders and small_orders:
            sheet_info += " [СМЕШАННЫЙ]"
            mixed_orders += 1
        elif big_orders:
            sheet_info += " [БОЛЬШИЕ ЗАКАЗЫ]"
        elif small_orders:
            sheet_info += " [МАЛЕНЬКИЕ ЗАКАЗЫ]"
        
        if p2_count > 0:
            sheet_info += f" [+{p2_count} приоритета 2]"
        
        print(sheet_info)
        
        if poly_count <= 2:
            single_polygon_sheets += 1
    
    # Оценка эффективности
    print(f"\n=== АНАЛИЗ ЭФФЕКТИВНОСТИ ===")
    print(f"Листов с малым заполнением (≤2 полигона): {single_polygon_sheets}")
    print(f"Смешанных листов (большие + маленькие заказы): {mixed_orders}")
    print(f"Полигонов приоритета 2 размещено: {priority2_placed}/5")
    
    # Проверка на основные проблемы
    problems = []
    if single_polygon_sheets > 2:
        problems.append(f"Слишком много листов с малым заполнением: {single_polygon_sheets}")
    
    if mixed_orders < 3:
        problems.append(f"Недостаточно смешанных листов: {mixed_orders} (ожидалось ≥3)")
    
    if priority2_placed < 3:
        problems.append(f"Мало размещенных полигонов приоритета 2: {priority2_placed}")
    
    if len(unplaced) > 0:
        problems.append(f"Остались неразмещенные полигоны: {len(unplaced)}")
    
    if actual_placed_count != (total_polygons - len(unplaced)):
        problems.append(f"Неверный подсчет размещенных полигонов")
    
    if problems:
        print(f"\n❌ НАЙДЕНЫ ПРОБЛЕМЫ:")
        for problem in problems:
            print(f"   • {problem}")
    else:
        print(f"\n✅ АЛГОРИТМ РАБОТАЕТ КОРРЕКТНО")
        print(f"   • Все основные проблемы исправлены")
        print(f"   • Эффективное размещение достигнуто")

if __name__ == "__main__":
    main()