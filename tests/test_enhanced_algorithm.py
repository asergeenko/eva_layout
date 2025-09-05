#!/usr/bin/env python3
"""
Тест улучшенного алгоритма с синтетическими данными
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from layout_optimizer import bin_packing_with_inventory
from shapely.geometry import Polygon
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def create_test_data():
    """Создает тестовые данные для проверки алгоритма"""
    
    # Создаем полигоны разных размеров (более крупные чтобы заставить алгоритм создать несколько листов)
    polygons = []
    
    # Большие заказы (по 4-5 полигонов каждый) - делаем крупнее
    for order_id in range(1, 6):  # 5 больших заказов  
        for poly_id in range(4):  # 4 полигона в каждом заказе
            poly = Polygon([(0, 0), (80, 0), (80, 60), (0, 60)])  # Увеличенные размеры
            polygons.append((poly, f"big_order_{order_id}_{poly_id}.dxf", "чёрный", f"BIG_ORDER_{order_id}"))
    
    # Маленькие заказы (по 1 полигону каждый)
    for order_id in range(1, 16):  # 15 маленьких заказов
        poly = Polygon([(0, 0), (40, 0), (40, 30), (0, 30)])  # Чуть крупнее
        polygons.append((poly, f"small_order_{order_id}.dxf", "чёрный", f"SMALL_ORDER_{order_id}"))
    
    return polygons

def main():
    print("=== ТЕСТ УЛУЧШЕННОГО АЛГОРИТМА ===")
    
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
        for i in range(1, 21)  # 20 листов
    ]
    
    # Создаем тестовые данные
    polygons = create_test_data()
    print(f"Создано {len(polygons)} полигонов")
    
    # Показываем структуру заказов
    orders_count = {}
    for poly in polygons:
        order_id = poly[3]
        orders_count[order_id] = orders_count.get(order_id, 0) + 1
    
    big_orders = {k: v for k, v in orders_count.items() if v > 1}
    small_orders = {k: v for k, v in orders_count.items() if v == 1}
    
    print(f"Больших заказов: {len(big_orders)} (по {list(big_orders.values())[0] if big_orders else 0} полигонов)")
    print(f"Маленьких заказов: {len(small_orders)} (по 1 полигону)")
    
    # Запуск оптимизации с ограничением MAX_SHEETS_PER_ORDER=5
    MAX_SHEETS_PER_ORDER = 5
    print(f"\n=== ЗАПУСК ОПТИМИЗАЦИИ (MAX_SHEETS_PER_ORDER={MAX_SHEETS_PER_ORDER}) ===")
    
    placed_layouts, unplaced = bin_packing_with_inventory(
        polygons,
        available_sheets,
        verbose=True,  # Включаем детальные логи
        max_sheets_per_order=MAX_SHEETS_PER_ORDER,
    )
    
    # Анализ результатов
    print("\n=== РЕЗУЛЬТАТЫ ===")
    print(f"Размещенных листов: {len(placed_layouts)}")
    print(f"Неразмещенных полигонов: {len(unplaced)}")
    
    # Детальный анализ листов
    print("\nДетали по листам:")
    single_polygon_sheets = 0
    mixed_order_sheets = 0
    
    for i, layout in enumerate(placed_layouts, 1):
        poly_count = len(layout['placed_polygons'])
        usage = layout.get('usage_percent', 0)
        orders_on_sheet = layout.get('orders_on_sheet', set())
        
        # Анализ типов заказов на листе
        big_orders_on_sheet = [o for o in orders_on_sheet if o.startswith('BIG_ORDER')]
        small_orders_on_sheet = [o for o in orders_on_sheet if o.startswith('SMALL_ORDER')]
        
        sheet_type = ""
        if big_orders_on_sheet and small_orders_on_sheet:
            sheet_type = " [СМЕШАННЫЙ]"
            mixed_order_sheets += 1
        elif big_orders_on_sheet:
            sheet_type = " [БОЛЬШИЕ]"
        elif small_orders_on_sheet:
            sheet_type = " [МАЛЕНЬКИЕ]"
        
        print(f"  Лист {i}: {poly_count} полигонов, {usage:.1f}% заполнение{sheet_type}")
        print(f"    Большие заказы: {len(big_orders_on_sheet)}, Маленькие заказы: {len(small_orders_on_sheet)}")
        
        if poly_count <= 2:
            single_polygon_sheets += 1
    
    # Оценка эффективности алгоритма
    print("\n=== АНАЛИЗ ЭФФЕКТИВНОСТИ ===")
    print(f"Листов с малым заполнением (≤2 полигона): {single_polygon_sheets}")
    print(f"Смешанных листов (большие + маленькие заказы): {mixed_order_sheets}")
    
    # Проверим, что маленькие заказы попадают на листы с большими заказами
    efficiency_ok = mixed_order_sheets >= 3  # Ожидаем хотя бы 3 смешанных листа
    
    if efficiency_ok:
        print("✅ АЛГОРИТМ РАБОТАЕТ ЭФФЕКТИВНО")
        print("   Маленькие заказы успешно размещаются на листы с большими заказами")
    else:
        print("❌ АЛГОРИТМ НЕЭФФЕКТИВЕН")
        print(f"   Недостаточно смешанных листов: {mixed_order_sheets} (ожидалось ≥3)")

if __name__ == "__main__":
    main()