#!/usr/bin/env python3
"""
Тест улучшения размещения у краев.
Генерирует раскладку для визуальной проверки.
"""

import sys
import os

import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import Polygon as MplPolygon

from dxf_utils import parse_dxf_complete
from excel_loader import (
    load_excel_file,
    parse_orders_from_excel,
    find_dxf_files_for_article,
)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from layout_optimizer import (
    bin_packing_with_inventory,
    Carpet,
)


def visualize_layout(layout, sheet_width, sheet_height, filename):
    """Визуализация одного листа"""
    fig, ax = plt.subplots(figsize=(12, 16))

    # Границы листа
    sheet_rect = patches.Rectangle(
        (0, 0),
        sheet_width,
        sheet_height,
        linewidth=2,
        edgecolor="black",
        facecolor="lightcyan",
        alpha=0.3,
    )
    ax.add_patch(sheet_rect)

    # Размещенные ковры
    for carpet in layout.placed_polygons:
        poly_coords = list(carpet.polygon.exterior.coords)
        color = {"чёрный": "gray", "серый": "lightgray", "бежевый": "wheat"}.get(
            carpet.color, "blue"
        )

        polygon = MplPolygon(
            poly_coords,
            closed=True,
            edgecolor="black",
            facecolor=color,
            alpha=0.6,
            linewidth=1,
        )
        ax.add_patch(polygon)

        # Текст с информацией
        bounds = carpet.polygon.bounds
        cx = (bounds[0] + bounds[2]) / 2
        cy = (bounds[1] + bounds[3]) / 2
        ax.text(
            cx,
            cy,
            carpet.filename.split("_")[0],
            ha="center",
            va="center",
            fontsize=6,
            weight="bold",
        )

    ax.set_xlim(-10, sheet_width + 10)
    ax.set_ylim(-10, sheet_height + 10)
    ax.set_aspect("equal")
    ax.set_title(
        f"Раскладка на листе {sheet_width} x {sheet_height} мм\n"
        f"{len(layout.placed_polygons)} ковров, {layout.usage_percent:.1f}% заполнение",
        fontsize=10,
    )
    ax.set_xlabel("Ширина (мм)", fontsize=8)
    ax.set_ylabel("Высота (мм)", fontsize=8)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(filename, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"✅ Сохранено: {filename}")


# Создаем листы - только черные 140x200
available_sheets = [
    {
        "name": "Черный лист",
        "width": 140,
        "height": 200,
        "color": "чёрный",
        "count": 20,
        "used": 0,
    }
]

print("📄 Создано листов: 20 черных 140x200")

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
                    unique_filename = (
                        f"{product_name}_{os.path.splitext(filename)[0]}.dxf"
                    )
                    polygons.append(
                        Carpet(polygon, unique_filename, color, order_id, 1)
                    )
            except Exception as e:
                print(f"⚠️ Ошибка обработки {dxf_file}: {e}")
                continue

print(f"📊 Всего черных ковров: {len(polygons)}")

# Запуск оптимизации
placed_layouts, unplaced = bin_packing_with_inventory(
    polygons,
    available_sheets,
    verbose=False,
)

print(f"📄 Размещено на {len(placed_layouts)} листах")

# Сохраняем первые 3 листа для визуальной проверки
os.makedirs("tmp_test/improved", exist_ok=True)
for i, layout in enumerate(placed_layouts[:3], 1):
    visualize_layout(layout, 140, 200, f"tmp_test/improved/{i}.png")

print("\n✅ Готово! Проверьте tmp_test/improved/*.png")
print("Сравните с tmp_test/bad_middle/*.png")
