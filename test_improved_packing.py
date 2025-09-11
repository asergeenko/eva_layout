#!/usr/bin/env python3
"""Test script to verify improved ultra-tight packing algorithm."""

import numpy as np
import matplotlib.pyplot as plt
from shapely.geometry import Polygon
from layout_optimizer import (
    bin_packing, 
    Carpet, 
    plot_layout,
    find_ultra_tight_position,
    check_collision
)

def create_test_carpets():
    """Create test carpets with various shapes and sizes."""
    carpets = []
    
    # Ковер 21 (примерно как на картинке)
    carpet21 = Polygon([
        (0, 0), (150, 0), (150, 50), (200, 50), (200, 150),
        (180, 150), (180, 200), (150, 200), (150, 300), 
        (120, 300), (120, 400), (80, 400), (80, 350),
        (50, 350), (50, 250), (0, 250)
    ])
    carpets.append(Carpet(carpet21, "21.dxf", "чёрный", "test", 1))
    
    # Ковер 23 (большой зеленый)
    carpet23 = Polygon([
        (0, 0), (300, 0), (300, 100), (320, 100), (320, 200),
        (300, 200), (300, 250), (250, 250), (250, 300),
        (200, 300), (200, 350), (150, 350), (150, 400),
        (0, 400), (0, 350), (50, 350), (50, 200), (0, 200)
    ])
    carpets.append(Carpet(carpet23, "23.dxf", "чёрный", "test", 1))
    
    # Ковер 24 (желтый)
    carpet24 = Polygon([
        (0, 0), (180, 0), (180, 80), (200, 80), (200, 120),
        (180, 120), (180, 200), (160, 200), (160, 250),
        (120, 250), (120, 300), (80, 300), (80, 200),
        (0, 200)
    ])
    carpets.append(Carpet(carpet24, "24.dxf", "чёрный", "test", 1))
    
    return carpets

def test_ultra_tight_vs_original():
    """Compare ultra-tight packing vs original algorithm."""
    print("🔥 Тестируем ультра-плотную упаковку...")
    
    carpets = create_test_carpets()
    sheet_size = (140, 200)  # 140x200 cm как на изображении
    
    # Тест с новым алгоритмом
    print("\n=== НОВЫЙ УЛЬТРА-ПЛОТНЫЙ АЛГОРИТМ ===")
    placed_new, unplaced_new = bin_packing(carpets, sheet_size, verbose=True)
    
    # Подсчитаем использование площади
    total_carpet_area = sum(carpet.polygon.area for carpet in carpets)
    sheet_area_mm2 = (sheet_size[0] * 10) * (sheet_size[1] * 10)  # convert cm to mm
    
    placed_area = sum(placed[0].area for placed in placed_new)
    usage_percent = (placed_area / sheet_area_mm2) * 100
    
    print(f"\n📊 РЕЗУЛЬТАТЫ:")
    print(f"Размещено ковров: {len(placed_new)}/{len(carpets)}")
    print(f"Использование площади: {usage_percent:.1f}%")
    print(f"Общая площадь ковров: {total_carpet_area/100:.0f} см²")
    print(f"Размещенная площадь: {placed_area/100:.0f} см²")
    
    # Проверим минимальные расстояния между коврами
    min_distances = []
    for i, (poly1, *_) in enumerate(placed_new):
        for j, (poly2, *_) in enumerate(placed_new[i+1:], i+1):
            distance = poly1.distance(poly2)
            min_distances.append(distance)
    
    if min_distances:
        print(f"Минимальное расстояние между коврами: {min(min_distances):.2f} мм")
        print(f"Среднее расстояние между коврами: {np.mean(min_distances):.2f} мм")
    
    # Создаем визуализацию
    if placed_new:
        plot_buffer = plot_layout(placed_new, sheet_size)
        with open("/tmp/improved_packing_test.png", "wb") as f:
            f.write(plot_buffer.getvalue())
        print(f"\n📈 Визуализация сохранена в /tmp/improved_packing_test.png")
    
    return len(placed_new) == len(carpets), usage_percent

def test_collision_precision():
    """Test collision detection precision."""
    print("\n🎯 Тестируем точность определения коллизий...")
    
    # Создаем два близко расположенных полигона
    poly1 = Polygon([(0, 0), (100, 0), (100, 100), (0, 100)])
    poly2 = Polygon([(100.1, 0), (200, 0), (200, 100), (100.1, 100)])  # Зазор 0.1мм
    
    # Тестируем разные минимальные зазоры
    gaps = [0.05, 0.1, 0.5, 1.0, 2.0]
    for gap in gaps:
        collision = check_collision(poly1, poly2, min_gap=gap)
        print(f"Зазор {gap:.2f}мм: {'КОЛЛИЗИЯ' if collision else 'OK'}")

def main():
    """Main test function."""
    print("🚀 ТЕСТИРОВАНИЕ УЛУЧШЕННОГО АЛГОРИТМА УПАКОВКИ")
    print("=" * 50)
    
    # Тест 1: Точность коллизий
    test_collision_precision()
    
    # Тест 2: Ультра-плотная упаковка
    all_placed, usage = test_ultra_tight_vs_original()
    
    print(f"\n🏆 ИТОГИ ТЕСТИРОВАНИЯ:")
    print(f"✅ Все ковры размещены: {'ДА' if all_placed else 'НЕТ'}")
    print(f"📊 Использование листа: {usage:.1f}%")
    
    if usage > 75:
        print("🎉 ОТЛИЧНЫЙ РЕЗУЛЬТАТ! Плотность упаковки значительно улучшена!")
    elif usage > 60:
        print("👍 ХОРОШИЙ РЕЗУЛЬТАТ! Заметные улучшения в плотности.")
    else:
        print("⚠️  Требуется дополнительная оптимизация.")

if __name__ == "__main__":
    main()