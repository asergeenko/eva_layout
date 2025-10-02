#!/usr/bin/env python3
"""
Анализ позиций ковров - проверяет сколько ковров прижаты к краям.
"""
import sys
import os
from pathlib import Path

from dxf_utils import parse_dxf_complete
from excel_loader import load_excel_file, parse_orders_from_excel, find_dxf_files_for_article

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from layout_optimizer import (
    bin_packing_with_inventory,
    Carpet,
)

# Создаем листы - только черные 140x200
available_sheets = [{
    "name": "Черный лист",
    "width": 140,
    "height": 200,
    "color": "чёрный",
    "count": 20,
    "used": 0
}]

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

    if color != "чёрный":
        continue

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
            except:
                continue

print(f"📊 Всего черных ковров: {len(polygons)}")

# Запуск оптимизации
placed_layouts, unplaced = bin_packing_with_inventory(
    polygons,
    available_sheets,
    verbose=False,
)

print(f"📄 Размещено на {len(placed_layouts)} листах\n")

# Анализ позиций ковров
EDGE_THRESHOLD = 10  # мм от края считается "прижатым"
sheet_width = 140
sheet_height = 200

total_carpets = 0
left_edge_count = 0
right_edge_count = 0
top_edge_count = 0
bottom_edge_count = 0
center_count = 0

for i, layout in enumerate(placed_layouts[:5], 1):  # Первые 5 листов
    print(f"Лист {i} ({len(layout.placed_polygons)} ковров, {layout.usage_percent:.1f}% заполнение):")

    for carpet in layout.placed_polygons:
        bounds = carpet.polygon.bounds
        min_x = bounds[0]
        max_x = bounds[2]
        min_y = bounds[1]
        max_y = bounds[3]

        total_carpets += 1

        # Проверяем позицию
        at_left = min_x < EDGE_THRESHOLD
        at_right = max_x > sheet_width - EDGE_THRESHOLD
        at_bottom = min_y < EDGE_THRESHOLD
        at_top = max_y > sheet_height - EDGE_THRESHOLD

        if at_left:
            left_edge_count += 1
        if at_right:
            right_edge_count += 1
        if at_bottom:
            bottom_edge_count += 1
        if at_top:
            top_edge_count += 1

        # Ковер в центре (не прижат ни к одному краю)
        if not (at_left or at_right or at_bottom or at_top):
            center_count += 1
            print(f"  ⚠️  {carpet.filename.split('_')[0]}: x={min_x:.0f}-{max_x:.0f}, y={min_y:.0f}-{max_y:.0f} (В ЦЕНТРЕ!)")
        elif at_left:
            print(f"  ✓ {carpet.filename.split('_')[0]}: x={min_x:.0f}-{max_x:.0f}, y={min_y:.0f}-{max_y:.0f} (прижат к левому краю)")
    print()

print("=" * 60)
print(f"ИТОГО (первые 5 листов, {total_carpets} ковров):")
print(f"  Прижаты к левому краю:  {left_edge_count} ({left_edge_count/total_carpets*100:.1f}%)")
print(f"  Прижаты к правому краю: {right_edge_count} ({right_edge_count/total_carpets*100:.1f}%)")
print(f"  Прижаты к нижнему краю: {bottom_edge_count} ({bottom_edge_count/total_carpets*100:.1f}%)")
print(f"  Прижаты к верхнему краю: {top_edge_count} ({top_edge_count/total_carpets*100:.1f}%)")
print(f"  В ЦЕНТРЕ (не прижаты):  {center_count} ({center_count/total_carpets*100:.1f}%)")
print()

if center_count == 0:
    print("✅ ОТЛИЧНО! Все ковры прижаты хотя бы к одному краю")
elif center_count < total_carpets * 0.1:
    print("✅ ХОРОШО! Менее 10% ковров в центре")
else:
    print(f"⚠️  ВНИМАНИЕ! {center_count/total_carpets*100:.1f}% ковров не прижаты к краям")
