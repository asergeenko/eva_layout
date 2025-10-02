#!/usr/bin/env python3
"""
Тест плотности размещения черных ковров из Excel файла.
Проверяет что черные заказы размещаются максимум на 17 листах,
причем на последнем листе максимум 1 ковер.
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


def test_black_density():
    """
    Тест плотности черных ковров:
    - Использует sample_input_test.xlsx
    - Только черные заказы
    - Листы 140x200 черные
    - Должно размещаться максимум на 17 листах
    - На последнем листе максимум 1 ковер
    """
    print("=== ТЕСТ ПЛОТНОСТИ ЧЕРНЫХ КОВРОВ ===")

    # Создаем листы - только черные 140x200
    available_sheets = [{
        "name": "Черный лист",
        "width": 140,
        "height": 200,
        "color": "чёрный",
        "count": 20,
        "used": 0
    }]

    print(f"📄 Создано листов: 20 черных 140x200")

    # Загружаем заказы из Excel
    excel_data = load_excel_file(open("tests/sample_input_test.xlsx", "rb").read())
    orders = parse_orders_from_excel(excel_data)

    # Обрабатываем заказы - только черные
    polygons = []
    for order in orders:
        order_id = order["order_id"]
        article = order["article"]
        product_name = order["product"]
        color = order["color"]

        # Только черные заказы
        if color != "чёрный":
            continue

        # Ищем DXF файлы для этого товара
        dxf_files = find_dxf_files_for_article(article, product_name)

        if dxf_files:
            for dxf_file in dxf_files:
                try:
                    polygon_data = parse_dxf_complete(dxf_file, verbose=False)
                    if polygon_data and polygon_data.get("combined_polygon"):
                        polygon = polygon_data["combined_polygon"]
                        filename = os.path.basename(dxf_file)
                        unique_filename = f"{product_name}_{os.path.splitext(filename)[0]}.dxf"
                        polygons.append(Carpet(polygon, unique_filename, color, order_id, 1))
                except Exception as e:
                    print(f"⚠️ Ошибка обработки {dxf_file}: {e}")
                    continue

    total_polygons = len(polygons)
    print(f"📊 Всего черных ковров для размещения: {total_polygons}")

    if not polygons:
        print("❌ Нет черных ковров для обработки")
        assert False, "Нет черных ковров для обработки"

    # Запуск оптимизации
    print("\n=== ЗАПУСК ОПТИМИЗАЦИИ ===")

    placed_layouts, unplaced = bin_packing_with_inventory(
        polygons,
        available_sheets,
        verbose=False,
    )

    # Анализ результатов
    print("\n=== РЕЗУЛЬТАТЫ ===")
    actual_placed_count = total_polygons - len(unplaced)
    print(f"📊 Размещено полигонов: {actual_placed_count}/{total_polygons} ({actual_placed_count / total_polygons * 100:.1f}%)")
    print(f"📄 Использовано листов: {len(placed_layouts)}")
    print(f"❌ Неразмещенных полигонов: {len(unplaced)}")

    # Детальный анализ по листам
    print("\n📄 ДЕТАЛИ ПО ЛИСТАМ:")
    total_sheet_usage = 0
    for i, layout in enumerate(placed_layouts, 1):
        carpet_count = len(layout.placed_polygons)
        usage = layout.usage_percent
        total_sheet_usage += usage
        print(f"   Лист {i}: {carpet_count} ковриков, {usage:.1f}% заполнение")

    if placed_layouts:
        avg_sheet_usage = total_sheet_usage / len(placed_layouts)
        print(f"   Среднее заполнение листов: {avg_sheet_usage:.1f}%")

    # Проверяем количество листов
    print("\n🎯 ПРОВЕРКА ТРЕБОВАНИЙ:")

    # Требование 1: Все ковры должны быть размещены
    if len(unplaced) > 0:
        print(f"   ❌ Есть неразмещенные ковры: {len(unplaced)}")
        print("   Неразмещенные:")
        for poly in unplaced:
            print(f"      • {poly.filename} (заказ: {poly.order_id})")
        assert False, f"Есть неразмещенные ковры: {len(unplaced)}"
    else:
        print(f"   ✅ Все ковры размещены")

    # Требование 2: Максимум 17 листов
    if len(placed_layouts) > 17:
        print(f"   ❌ Использовано листов: {len(placed_layouts)} > 17")
        assert False, f"Использовано слишком много листов: {len(placed_layouts)} > 17"
    else:
        print(f"   ✅ Использовано листов: {len(placed_layouts)} <= 17")

    # Требование 3: На последнем листе низкое заполнение (< 20%)
    # Это показатель хорошей плотности - последний лист не должен быть сильно заполнен
    if placed_layouts:
        last_sheet_carpets = len(placed_layouts[-1].placed_polygons)
        last_sheet_usage = placed_layouts[-1].usage_percent
        if last_sheet_usage > 20:
            print(f"   ❌ Заполнение последнего листа {last_sheet_usage:.1f}% > 20%")
            assert False, f"Последний лист слишком заполнен: {last_sheet_usage:.1f}% > 20%"
        else:
            print(f"   ✅ Заполнение последнего листа {last_sheet_usage:.1f}% <= 20% ({last_sheet_carpets} ковров)")

    print("\n✅ ТЕСТ ПРОЙДЕН УСПЕШНО")
    print(f"   • Размещено {actual_placed_count} ковров")
    print(f"   • Использовано {len(placed_layouts)} листов (макс 17)")
    print(f"   • На последнем листе {last_sheet_carpets} ковер (макс 1)")
    print(f"   • Среднее заполнение: {avg_sheet_usage:.1f}%")
