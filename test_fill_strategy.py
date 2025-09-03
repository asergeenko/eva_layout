#!/usr/bin/env python3
"""
Специальный тест для проверки стратегии дозаполнения листов.
"""

import sys
import os

# Добавляем корневую директорию в путь для импорта модулей
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from layout_optimizer import bin_packing_with_inventory
from shapely.geometry import Polygon
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def create_test_polygons():
    """Создаем тестовые полигоны с разными размерами для симуляции проблемы."""
    polygons = []
    
    # Заказы с 4-5 полигонами (большие)
    for order_num in range(2, 6):  # ZAKAZ_row_2 to ZAKAZ_row_5
        for poly_num in range(5):
            # Большие полигоны
            poly = Polygon([(0, 0), (300, 0), (300, 200), (0, 200)])
            polygons.append((poly, f"big_order_{order_num}_{poly_num}.dxf", "чёрный", f"ZAKAZ_row_{order_num}"))
    
    # Заказы с 1 полигоном (маленькие - должны дозаполнять листы)
    for order_num in range(21, 28):  # ZAKAZ_row_21 to ZAKAZ_row_27
        # Маленькие полигоны
        poly = Polygon([(0, 0), (100, 0), (100, 80), (0, 80)])
        color = "чёрный" if order_num % 2 == 0 else "серый"
        polygons.append((poly, f"small_order_{order_num}.dxf", color, f"ZAKAZ_row_{order_num}"))
    
    return polygons

def main():
    print("=== ТЕСТ СТРАТЕГИИ ДОЗАПОЛНЕНИЯ ===")
    
    # Создаем листы
    available_sheets = [
        {
            "name": "Черный лист 140x200",
            "width": 140,
            "height": 200,
            "color": "чёрный",
            "count": 10,
            "used": 0
        },
        {
            "name": "Серый лист 140x200", 
            "width": 140,
            "height": 200,
            "color": "серый",
            "count": 10,
            "used": 0
        }
    ]
    
    # Создаем полигоны
    polygons = create_test_polygons()
    
    print(f"Создано {len(polygons)} полигонов")
    print(f"Большие заказы: 4 заказа по 5 полигонов (20 полигонов)")
    print(f"Маленькие заказы: 7 заказов по 1 полигону (7 полигонов)")
    
    # Запуск оптимизации
    print("\n=== ЗАПУСК ОПТИМИЗАЦИИ (MAX_SHEETS_PER_ORDER=5) ===")
    MAX_SHEETS_PER_ORDER = 5
    
    placed_layouts, unplaced = bin_packing_with_inventory(
        polygons,
        available_sheets,
        verbose=False,
        max_sheets_per_order=MAX_SHEETS_PER_ORDER,
    )
    
    # Анализ результатов
    print(f"\n=== РЕЗУЛЬТАТЫ ===")
    print(f"Размещенных листов: {len(placed_layouts)}")
    print(f"Неразмещенных полигонов: {len(unplaced)}")
    
    print(f"\nДетали по листам:")
    for i, layout in enumerate(placed_layouts, 1):
        poly_count = len(layout['placed_polygons'])
        usage = layout.get('usage_percent', 0)
        orders_on_sheet = layout.get('orders_on_sheet', set())
        print(f"  Лист {i}: {poly_count} полигонов, {usage:.1f}% заполнение, заказы: {', '.join(sorted(orders_on_sheet))}")
    
    # Проверка эффективности
    total_polygons = len(polygons) - len(unplaced)
    if len(placed_layouts) <= 6:  # Ожидаем не больше 6 листов для эффективной упаковки
        print(f"\n✅ ТЕСТ ПРОЙДЕН: Эффективное размещение {total_polygons} полигонов на {len(placed_layouts)} листах")
    else:
        print(f"\n❌ ТЕСТ НЕ ПРОЙДЕН: Неэффективное размещение {total_polygons} полигонов на {len(placed_layouts)} листах")
        print("Ожидалось не больше 6 листов")

if __name__ == "__main__":
    main()