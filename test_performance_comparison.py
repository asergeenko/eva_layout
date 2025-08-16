#!/usr/bin/env python3
"""
Тест производительности оптимизированного алгоритма размещения.
"""

import time
import numpy as np
from shapely.geometry import Polygon
from layout_optimizer import bin_packing, check_collision

def create_test_polygons(count=20):
    """Создает тестовые полигоны для проверки производительности."""
    polygons = []
    for i in range(count):
        # Создаем прямоугольные полигоны разных размеров
        width = np.random.uniform(10, 50)
        height = np.random.uniform(10, 40)
        x = np.random.uniform(0, 10)
        y = np.random.uniform(0, 10)
        
        polygon = Polygon([
            (x, y), (x + width, y), 
            (x + width, y + height), (x, y + height)
        ])
        
        polygons.append((polygon, f"test_{i}.dxf", "серый", f"order_{i % 5}"))
    
    return polygons

def test_collision_performance():
    """Тестирует производительность проверки коллизий."""
    print("=== Тест производительности проверки коллизий ===")
    
    # Создаем два полигона
    poly1 = Polygon([(0, 0), (30, 0), (30, 20), (0, 20)])
    poly2 = Polygon([(25, 5), (55, 5), (55, 25), (25, 25)])
    
    # Количество проверок
    iterations = 10000
    
    start_time = time.time()
    collision_count = 0
    for _ in range(iterations):
        if check_collision(poly1, poly2):
            collision_count += 1
    end_time = time.time()
    
    total_time = end_time - start_time
    avg_time = (total_time / iterations) * 1000  # в миллисекундах
    
    print(f"Проверено коллизий: {iterations}")
    print(f"Общее время: {total_time:.3f} сек")
    print(f"Среднее время на проверку: {avg_time:.4f} мс")
    print(f"Коллизий найдено: {collision_count}")
    
    return avg_time

def test_bin_packing_performance():
    """Тестирует производительность алгоритма размещения."""
    print("\n=== Тест производительности размещения ===")
    
    # Создаем тестовые полигоны
    polygons = create_test_polygons(count=15)
    sheet_size = (200, 150)  # см
    
    start_time = time.time()
    placed, unplaced = bin_packing(polygons, sheet_size, verbose=False)
    end_time = time.time()
    
    total_time = end_time - start_time
    
    print(f"Полигонов для размещения: {len(polygons)}")
    print(f"Размещено: {len(placed)}")
    print(f"Не размещено: {len(unplaced)}")
    print(f"Время размещения: {total_time:.3f} сек")
    print(f"Среднее время на полигон: {(total_time / len(polygons)):.3f} сек")
    
    # Проверяем корректность размещения
    collision_count = 0
    for i, (poly1, *_) in enumerate(placed):
        for j, (poly2, *_) in enumerate(placed[i+1:], i+1):
            if check_collision(poly1, poly2):
                collision_count += 1
                print(f"⚠️ Коллизия между полигонами {i} и {j}")
    
    if collision_count == 0:
        print("✅ Все полигоны размещены без коллизий!")
    else:
        print(f"❌ Найдено {collision_count} коллизий")
    
    return total_time, len(placed), collision_count

def benchmark_comparison():
    """Сравнивает производительность с различными параметрами."""
    print("\n=== Сравнительный бенчмарк ===")
    
    sizes = [5, 10, 15, 20]
    
    for size in sizes:
        print(f"\nТест с {size} полигонами:")
        polygons = create_test_polygons(count=size)
        sheet_size = (250, 200)
        
        start_time = time.time()
        placed, unplaced = bin_packing(polygons, sheet_size, verbose=False)
        end_time = time.time()
        
        total_time = end_time - start_time
        efficiency = len(placed) / len(polygons) * 100
        
        print(f"  Время: {total_time:.3f} сек")
        print(f"  Эффективность размещения: {efficiency:.1f}%")
        print(f"  Производительность: {len(polygons)/total_time:.1f} полигонов/сек")

if __name__ == "__main__":
    print("🚀 Тестирование производительности оптимизированного алгоритма")
    print("=" * 60)
    
    # Тест производительности коллизий
    collision_time = test_collision_performance()
    
    # Тест производительности размещения
    placement_time, placed_count, collisions = test_bin_packing_performance()
    
    # Сравнительный бенчмарк
    benchmark_comparison()
    
    print("\n" + "=" * 60)
    print("📊 ИТОГОВЫЕ РЕЗУЛЬТАТЫ:")
    print(f"• Средняя проверка коллизий: {collision_time:.4f} мс")
    print(f"• Время размещения 15 полигонов: {placement_time:.3f} сек")
    print(f"• Количество коллизий: {collisions}")
    
    if collision_time < 0.1 and placement_time < 5.0 and collisions == 0:
        print("✅ ТЕСТ ПРОЙДЕН: Алгоритм работает быстро и корректно!")
    else:
        print("⚠️ ВНИМАНИЕ: Возможны проблемы с производительностью или корректностью")