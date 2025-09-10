#!/usr/bin/env python3
"""
Демонстрация улучшенного алгоритма размещения ковриков.
Сравнение стандартного и улучшенного подходов.
"""

import sys
import os
import logging
from shapely.geometry import Polygon
from layout_optimizer import Carpet, bin_packing
from improved_packing import improved_bin_packing

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_test_carpets():
    """Создает тестовые коврики разных размеров и форм."""
    carpets = []
    
    # Прямоугольные коврики разных размеров (реалистичные размеры для листа 140x200)
    sizes = [
        (300, 200, "Средний коврик"),      # 30x20 см
        (400, 150, "Длинный коврик"),      # 40x15 см  
        (200, 250, "Высокий коврик"),      # 20x25 см
        (350, 180, "Большой коврик"),      # 35x18 см
        (180, 180, "Квадратный коврик"),   # 18x18 см
        (250, 120, "Коврик среднего размера"), # 25x12 см
        (320, 160, "Широкий коврик"),      # 32x16 см
        (150, 150, "Маленький квадрат"),   # 15x15 см
        (280, 140, "Узкий коврик"),        # 28x14 см
        (200, 180, "Компактный коврик"),   # 20x18 см
        (160, 200, "Вертикальный коврик"), # 16x20 см
        (240, 130, "Прямоугольный коврик"), # 24x13 см
    ]
    
    # Сложные формы (L-образные, вырезы) - уменьшены для реалистичности
    complex_shapes = [
        # L-образный коврик 
        ([(0, 0), (250, 0), (250, 120), (120, 120), (120, 200), (0, 200)], "L-образный коврик"),
        # Коврик с небольшим вырезом
        ([(0, 0), (300, 0), (300, 180), (0, 180), (0, 0), (80, 60), (80, 120), (220, 120), (220, 60), (80, 60)], "Коврик с вырезом"),
    ]
    
    # Создаем прямоугольные коврики
    for i, (width, height, name) in enumerate(sizes):
        polygon = Polygon([(0, 0), (width, 0), (width, height), (0, height)])
        carpets.append(Carpet(polygon, f"{name}_{i+1}.dxf", "черный", f"order_{i+1}", 1))
    
    # Создаем сложные коврики
    for i, (coords, name) in enumerate(complex_shapes):
        polygon = Polygon(coords)
        carpets.append(Carpet(polygon, f"{name}_{i+1}.dxf", "черный", f"complex_{i+1}", 1))
    
    return carpets

def calculate_utilization(placed_polygons, sheet_size):
    """Рассчитывает эффективность использования листа."""
    if not placed_polygons:
        return 0.0
    
    total_area = sum(p[0].area for p in placed_polygons)
    sheet_area = (sheet_size[0] * 10) * (sheet_size[1] * 10)  # Convert to mm²
    return (total_area / sheet_area) * 100

def demo_packing_comparison():
    """Демонстрирует сравнение стандартного и улучшенного алгоритмов."""
    print("=== ДЕМОНСТРАЦИЯ УЛУЧШЕННОГО АЛГОРИТМА РАЗМЕЩЕНИЯ ===\n")
    
    # Создаем тестовые данные
    carpets = create_test_carpets()
    sheet_size = (140, 200)  # 140x200 см
    
    print(f"Создано {len(carpets)} тестовых ковриков для размещения на листе {sheet_size[0]}x{sheet_size[1]} см\n")
    
    # Тест 1: Стандартный алгоритм
    print("🔧 ТЕСТ 1: СТАНДАРТНЫЙ АЛГОРИТМ")
    print("-" * 40)
    import time
    start_time = time.time()
    
    placed_standard, unplaced_standard = bin_packing(carpets, sheet_size, verbose=False)
    
    standard_time = time.time() - start_time
    standard_utilization = calculate_utilization(placed_standard, sheet_size)
    
    print(f"✅ Размещено: {len(placed_standard)}/{len(carpets)} ковриков")
    print(f"✅ Эффективность: {standard_utilization:.1f}% использования листа")
    print(f"✅ Время выполнения: {standard_time:.2f} секунд")
    print(f"❌ Не размещено: {len(unplaced_standard)} ковриков\n")
    
    # Тест 2: Улучшенный алгоритм
    print("🚀 ТЕСТ 2: УЛУЧШЕННЫЙ АЛГОРИТМ")
    print("-" * 40)
    start_time = time.time()
    
    placed_improved, unplaced_improved = improved_bin_packing(carpets, sheet_size, verbose=False)
    
    improved_time = time.time() - start_time
    improved_utilization = calculate_utilization(placed_improved, sheet_size)
    
    print(f"✅ Размещено: {len(placed_improved)}/{len(carpets)} ковриков")
    print(f"✅ Эффективность: {improved_utilization:.1f}% использования листа")
    print(f"✅ Время выполнения: {improved_time:.2f} секунд")
    print(f"❌ Не размещено: {len(unplaced_improved)} ковриков\n")
    
    # Сравнение результатов
    print("📊 СРАВНЕНИЕ РЕЗУЛЬТАТОВ")
    print("=" * 50)
    
    placement_improvement = len(placed_improved) - len(placed_standard)
    utilization_improvement = improved_utilization - standard_utilization
    time_ratio = improved_time / standard_time if standard_time > 0 else float('inf')
    
    if placement_improvement > 0:
        print(f"🎯 Размещение: +{placement_improvement} ковриков ({(placement_improvement/len(carpets)*100):.1f}% улучшение)")
    elif placement_improvement < 0:
        print(f"⚠️  Размещение: {placement_improvement} ковриков ({abs(placement_improvement/len(carpets)*100):.1f}% хуже)")
    else:
        print("🟢 Размещение: Одинаково")
    
    if utilization_improvement > 1:
        print(f"📈 Эффективность: +{utilization_improvement:.1f}% лучше использование листа")
    elif utilization_improvement < -1:
        print(f"📉 Эффективность: {abs(utilization_improvement):.1f}% хуже использование листа")
    else:
        print("🟢 Эффективность: Примерно одинаково")
    
    if time_ratio > 1.5:
        print(f"⏱️  Время: В {time_ratio:.1f}x раз медленнее")
    elif time_ratio < 0.7:
        print(f"⚡ Время: В {1/time_ratio:.1f}x раз быстрее")
    else:
        print("🟢 Время: Сопоставимо")
    
    print("\n" + "=" * 50)
    
    # Рекомендация
    if placement_improvement > 0 or utilization_improvement > 2:
        if time_ratio < 3:
            print("💡 РЕКОМЕНДАЦИЯ: Улучшенный алгоритм показывает лучшие результаты")
            print("   при приемлемом увеличении времени выполнения.")
        else:
            print("💡 РЕКОМЕНДАЦИЯ: Улучшенный алгоритм лучше, но значительно медленнее.")
            print("   Используйте для критически важных задач или небольших объемов.")
    else:
        print("💡 РЕКОМЕНДАЦИЯ: Стандартный алгоритм достаточно эффективен")
        print("   и работает быстрее для данного набора ковриков.")
    
    return {
        'standard': {
            'placed': len(placed_standard),
            'utilization': standard_utilization,
            'time': standard_time
        },
        'improved': {
            'placed': len(placed_improved), 
            'utilization': improved_utilization,
            'time': improved_time
        }
    }

if __name__ == "__main__":
    try:
        results = demo_packing_comparison()
    except Exception as e:
        print(f"❌ Ошибка при выполнении демонстрации: {e}")
        sys.exit(1)
    
    print(f"\n🏁 Демонстрация завершена успешно")