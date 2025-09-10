#!/usr/bin/env python3
"""
Отладочный скрипт для понимания проблем с размещением ковриков
"""

from shapely.geometry import Polygon
from layout_optimizer import Carpet, bin_packing
from improved_packing import improved_bin_packing
import logging

# Настройка логирования
logging.basicConfig(level=logging.DEBUG, format="%(levelname)s - %(message)s")


def create_simple_test():
    """Создает простой тест с маленькими ковриками."""
    carpets = []

    # Очень маленькие коврики, которые точно должны поместиться
    small_sizes = [
        (100, 80),  # 10x8 см
        (120, 60),  # 12x6 см
        (80, 100),  # 8x10 см
        (90, 70),  # 9x7 см
        (110, 50),  # 11x5 см
    ]

    for i, (width, height) in enumerate(small_sizes):
        polygon = Polygon([(0, 0), (width, 0), (width, height), (0, height)])
        carpets.append(Carpet(polygon, f"small_{i+1}.dxf", "черный", f"order_{i+1}", 1))

    return carpets


def debug_single_carpet():
    """Тестируем размещение одного коврика."""
    print("=== ТЕСТ ОДНОГО КОВРИКА ===")

    # Один маленький коврик 10x8 см (100x80 мм)
    polygon = Polygon([(0, 0), (100, 0), (100, 80), (0, 80)])
    carpet = Carpet(polygon, "test.dxf", "черный", "test_order", 1)

    sheet_size = (140, 200)  # 140x200 см
    print(f"Коврик: 10x8 см, Лист: {sheet_size[0]}x{sheet_size[1]} см")

    # Стандартный алгоритм
    placed_std, unplaced_std = bin_packing([carpet], sheet_size, verbose=False)
    print(f"Стандартный: размещено {len(placed_std)}, не размещено {len(unplaced_std)}")

    # Улучшенный алгоритм
    placed_imp, unplaced_imp = improved_bin_packing([carpet], sheet_size, verbose=False)
    print(f"Улучшенный: размещено {len(placed_imp)}, не размещено {len(unplaced_imp)}")

    if len(placed_std) > 0:
        print(
            f"Стандартный разместил в позицию: ({placed_std[0][1]:.1f}, {placed_std[0][2]:.1f})"
        )
    if len(placed_imp) > 0:
        print(
            f"Улучшенный разместил в позицию: ({placed_imp[0][1]:.1f}, {placed_imp[0][2]:.1f})"
        )


def debug_multiple_carpets():
    """Тестируем размещение нескольких маленьких ковриков."""
    print("\n=== ТЕСТ НЕСКОЛЬКИХ МАЛЕНЬКИХ КОВРИКОВ ===")

    carpets = create_simple_test()
    sheet_size = (140, 200)

    print(f"Ковриков: {len(carpets)}, Лист: {sheet_size[0]}x{sheet_size[1]} см")

    # Покажем размеры всех ковриков
    total_area = 0
    for i, carpet in enumerate(carpets):
        bounds = carpet.polygon.bounds
        w, h = bounds[2] - bounds[0], bounds[3] - bounds[1]
        area = carpet.polygon.area
        total_area += area
        print(f"  Коврик {i+1}: {w/10:.1f}x{h/10:.1f} см, площадь {area/100:.1f} см²")

    sheet_area = sheet_size[0] * sheet_size[1] * 100  # в мм²
    print(f"  Общая площадь ковриков: {total_area/100:.1f} см²")
    print(f"  Площадь листа: {sheet_area/100:.1f} см²")
    print(f"  Теоретическая загрузка: {(total_area/sheet_area)*100:.1f}%")

    # Стандартный алгоритм
    placed_std, unplaced_std = bin_packing(carpets, sheet_size, verbose=False)
    print(
        f"\nСтандартный: размещено {len(placed_std)}, не размещено {len(unplaced_std)}"
    )

    if placed_std:
        usage = sum(p[0].area for p in placed_std) / sheet_area * 100
        print(f"  Использование листа: {usage:.1f}%")

    # Улучшенный алгоритм
    placed_imp, unplaced_imp = improved_bin_packing(carpets, sheet_size, verbose=False)
    print(f"Улучшенный: размещено {len(placed_imp)}, не размещено {len(unplaced_imp)}")

    if placed_imp:
        usage = sum(p[0].area for p in placed_imp) / sheet_area * 100
        print(f"  Использование листа: {usage:.1f}%")


if __name__ == "__main__":
    debug_single_carpet()
    debug_multiple_carpets()
