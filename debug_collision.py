from shapely import Polygon
from carpet import Carpet
from layout_optimizer import bin_packing_with_inventory

print("Testing collision detection with simple rectangles...")

# Создаем простые прямоугольные полигоны
rect1 = Polygon([(0, 0), (50, 0), (50, 50), (0, 50)])
rect2 = Polygon([(0, 0), (50, 0), (50, 50), (0, 50)])  # Идентичный прямоугольник

carpets = [
    Carpet(rect1, "rect1.dxf", "black", "group1", 1),
    Carpet(rect2, "rect2.dxf", "black", "group1", 1),
]

print(f"Carpet areas: {rect1.area}, {rect2.area}")

# Большой лист для размещения
available_sheets = [
    {
        "name": "Test Sheet",
        "width": 140,
        "height": 200,
        "color": "black",
        "count": 1,
        "used": 0,
    }
]

# Площадь листа: 140*10 * 200*10 = 2,800,000 мм²
# Площадь двух ковров: 2500 + 2500 = 5000 мм²
sheet_area = (140 * 10) * (200 * 10)
total_carpet_area = rect1.area + rect2.area
theoretical_utilization = (total_carpet_area / sheet_area) * 100

print(f"Sheet area: {sheet_area} mm²")
print(f"Total carpet area: {total_carpet_area} mm²")
print(f"Theoretical utilization: {theoretical_utilization:.1f}%")

placed_layouts, unplaced = bin_packing_with_inventory(
    carpets,
    available_sheets,
    verbose=True,
)

print("\nResults:")
print(f"Sheets used: {len(placed_layouts)}")
print(f"Unplaced: {len(unplaced)}")

if placed_layouts:
    layout = placed_layouts[0]
    print(f"Sheet utilization: {layout.usage_percent:.1f}%")
    print(f"Carpets on sheet: {len(layout.placed_polygons)}")

    # Проверим позиции ковров
    for i, carpet in enumerate(layout.placed_polygons):
        print(f"  Carpet {i+1}: pos=({carpet.x_offset:.1f}, {carpet.y_offset:.1f})")

    # Если утилизация > 1%, значит ковры накладываются друг на друга
    if layout.usage_percent > 1:
        print("❌ ПРОБЛЕМА: Утилизация > 1% указывает на наложение ковров!")
    else:
        print("✅ ОК: Нормальная утилизация, наложений нет")
