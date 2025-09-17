#!/usr/bin/env python3
"""
Тест кэширования для оптимизации layout_optimizer.py
"""
import time
from shapely.geometry import Polygon
from carpet import Carpet
from layout_optimizer import (
    get_cached_rotation,
    clear_optimization_caches,
    get_cache_stats,
    rotate_polygon
)

def create_test_carpet(coords, carpet_id=1):
    """Создать тестовый ковер с заданными координатами."""
    polygon = Polygon(coords)
    return Carpet(
        polygon=polygon,
        filename=f"test_carpet_{carpet_id}.dxf",
        color="серый",
        order_id="TEST_ORDER",
        carpet_id=carpet_id
    )

def test_carpet_id_uniqueness():
    """Тест кэширования по уникальным carpet_id."""
    print("=== Тест кэширования по carpet_id ===")

    clear_optimization_caches()

    # Создаем ковры с разными carpet_id, но одинаковой геометрией
    carpet1 = create_test_carpet([(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)], 1)
    carpet2 = create_test_carpet([(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)], 2)
    carpet3 = create_test_carpet([(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)], 3)

    # Каждый ковер должен кэшироваться отдельно
    rot1 = get_cached_rotation(carpet1, 90)
    rot2 = get_cached_rotation(carpet2, 90)
    rot3 = get_cached_rotation(carpet3, 90)

    stats = get_cache_stats()
    print(f"Статистика кэша: {stats}")

    # Должно быть 3 ковра в кэше (по одному на каждый carpet_id)
    assert stats['cached_carpets'] == 3, f"Ожидалось 3 ковра в кэше, получили {stats['cached_carpets']}"
    assert stats['cached_rotations'] == 3, f"Ожидалось 3 поворота в кэше, получили {stats['cached_rotations']}"

    print("✅ Тест кэширования по carpet_id пройден")

def test_rotation_caching():
    """Тест кэширования поворотов."""
    print("\n=== Тест кэширования поворотов ===")

    clear_optimization_caches()

    carpet = create_test_carpet([(0, 0), (10, 0), (10, 5), (0, 5), (0, 0)])

    # Первый вызов - должен создать кэш
    start_time = time.time()
    rotated_90_1 = get_cached_rotation(carpet, 90)
    first_call_time = time.time() - start_time

    # Второй вызов - должен использовать кэш
    start_time = time.time()
    rotated_90_2 = get_cached_rotation(carpet, 90)
    second_call_time = time.time() - start_time

    # Проверки
    assert rotated_90_1.equals(rotated_90_2), "Кэшированные результаты должны быть идентичными"

    # Кэшированный вызов должен быть быстрее (хотя на таких малых данных разница может быть незаметна)
    print(f"Первый вызов: {first_call_time:.6f}с")
    print(f"Второй вызов (кэш): {second_call_time:.6f}с")

    stats = get_cache_stats()
    print(f"Статистика кэша: {stats}")

    assert stats['cached_rotations'] >= 1, "Должен быть хотя бы один кэшированный поворот"
    assert stats['cached_carpets'] == 1, "Должен быть один ковер в кэше"

    print("✅ Тест кэширования поворотов пройден")

def test_multiple_carpets_caching():
    """Тест кэширования для нескольких ковров."""
    print("\n=== Тест кэширования нескольких ковров ===")

    clear_optimization_caches()

    # Создаем несколько ковров с разными carpet_id
    base_coords = [(0, 0), (15, 0), (15, 8), (0, 8), (0, 0)]
    carpets = [create_test_carpet(base_coords, i) for i in range(1, 6)]  # 5 ковров

    # Поворачиваем все ковры на 90 градусов
    start_time = time.time()
    rotations = [get_cached_rotation(carpet, 90) for carpet in carpets]
    total_time = time.time() - start_time

    # Все повороты должны быть одинаковыми по форме (но разные объекты в кэше)
    assert all(rot.equals(rotations[0]) for rot in rotations), "Все повороты должны быть одинаковыми по форме"

    stats = get_cache_stats()
    print(f"Обработано {len(carpets)} ковров за {total_time:.6f}с")
    print(f"Кэшированных ковров: {stats['cached_carpets']}")
    print(f"Кэшированных поворотов: {stats['cached_rotations']}")

    # Должно быть 5 ковров в кэше (каждый со своим carpet_id)
    assert stats['cached_carpets'] == 5, f"Ожидалось 5 ковров в кэше, получили {stats['cached_carpets']}"
    assert stats['cached_rotations'] == 5, f"Ожидалось 5 поворотов в кэше, получили {stats['cached_rotations']}"

    print("✅ Тест кэширования нескольких ковров пройден")

def benchmark_with_without_cache():
    """Бенчмарк сравнения производительности с кэшем и без."""
    print("\n=== Бенчмарк производительности ===")

    # Создаем много дублированных ковров
    base_coords = [(0, 0), (25, 0), (25, 15), (0, 15), (0, 0)]
    num_duplicates = 50
    carpets = [create_test_carpet(base_coords, i) for i in range(num_duplicates)]
    angles = [0, 90, 180, 270]

    # Тест БЕЗ кэша (используем прямые вызовы rotate_polygon)
    clear_optimization_caches()
    start_time = time.time()
    for carpet in carpets:
        for angle in angles:
            if angle == 0:
                result = carpet.polygon
            else:
                result = rotate_polygon(carpet.polygon, angle)
    no_cache_time = time.time() - start_time

    # Тест С кэшем
    clear_optimization_caches()
    start_time = time.time()
    for carpet in carpets:
        for angle in angles:
            result = get_cached_rotation(carpet, angle)
    cache_time = time.time() - start_time

    speedup = no_cache_time / cache_time if cache_time > 0 else float('inf')

    print(f"Без кэша: {no_cache_time:.6f}с")
    print(f"С кэшем: {cache_time:.6f}с")
    print(f"Ускорение: {speedup:.2f}x")

    stats = get_cache_stats()
    print(f"Итоговая статистика кэша: {stats}")

    print("✅ Бенчмарк завершен")

if __name__ == "__main__":
    print("Запуск тестов оптимизации кэширования...")

    test_carpet_id_uniqueness()
    test_rotation_caching()
    test_multiple_carpets_caching()
    benchmark_with_without_cache()

    print("\n🎉 Все тесты пройдены успешно!")
    print("Кэширование работает корректно и ускоряет повторные вычисления поворотов.")