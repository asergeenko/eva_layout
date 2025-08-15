#!/usr/bin/env python3
"""Тест производительности оптимизированного алгоритма."""

import sys
import os
import time
import logging

# Отключаем логгинг для чистого теста производительности
logging.getLogger().setLevel(logging.CRITICAL)

# Очистка импортов
if 'layout_optimizer' in sys.modules:
    del sys.modules['layout_optimizer']

from layout_optimizer import (
    parse_dxf_complete, 
    bin_packing,
    __version__
)

print("=" * 70)
print("🚀 ТЕСТ ПРОИЗВОДИТЕЛЬНОСТИ ОПТИМИЗИРОВАННОГО АЛГОРИТМА")
print("=" * 70)
print(f"📋 Версия модуля: {__version__}")

def benchmark_tank300():
    """Бенчмарк файлов TANK 300."""
    print(f"\n🎯 Бенчмарк TANK 300:")
    
    tank_folder = "dxf_samples/TANK 300"
    if not os.path.exists(tank_folder):
        print(f"❌ Папка {tank_folder} не найдена!")
        return None, None
    
    # Загрузка файлов
    print(f"   Загрузка DXF файлов...")
    start_load = time.time()
    
    polygons = []
    for i in range(1, 5):
        file_path = os.path.join(tank_folder, f"{i}.dxf")
        if os.path.exists(file_path):
            result = parse_dxf_complete(file_path, verbose=False)
            if result and result['combined_polygon']:
                filename = f"TANK300_{i}.dxf"
                polygons.append((result['combined_polygon'], filename, "чёрный", f"order_{i}"))
    
    load_time = time.time() - start_load
    print(f"   ⏱️  Загрузка {len(polygons)} файлов: {load_time:.2f} сек")
    
    if len(polygons) < 4:
        print(f"❌ Загружено недостаточно полигонов: {len(polygons)}")
        return None, None
    
    # Размещение
    print(f"   Запуск алгоритма размещения...")
    start_placement = time.time()
    
    placed, unplaced = bin_packing(polygons, (200, 140), verbose=False)
    
    placement_time = time.time() - start_placement
    total_time = load_time + placement_time
    
    print(f"   ⏱️  Размещение: {placement_time:.2f} сек")
    print(f"   ⏱️  ОБЩЕЕ ВРЕМЯ: {total_time:.2f} сек")
    print(f"   📊 Результат: {len(placed)} размещено, {len(unplaced)} не размещено")
    
    return placement_time, total_time

def benchmark_multiple_runs():
    """Множественные запуски для проверки стабильности."""
    print(f"\n🔄 Тест стабильности (5 запусков):")
    
    times = []
    results_consistent = True
    baseline_result = None
    
    for run in range(5):
        print(f"   Запуск {run + 1}/5...", end=" ")
        
        tank_folder = "dxf_samples/TANK 300"
        polygons = []
        for i in range(1, 5):
            file_path = os.path.join(tank_folder, f"{i}.dxf")
            if os.path.exists(file_path):
                result = parse_dxf_complete(file_path, verbose=False)
                if result and result['combined_polygon']:
                    filename = f"TANK300_{i}.dxf"
                    polygons.append((result['combined_polygon'], filename, "чёрный", f"order_{i}"))
        
        start_time = time.time()
        placed, unplaced = bin_packing(polygons, (200, 140), verbose=False)
        end_time = time.time()
        
        run_time = end_time - start_time
        times.append(run_time)
        
        # Проверяем консистентность результатов
        current_result = (len(placed), len(unplaced))
        if baseline_result is None:
            baseline_result = current_result
        elif baseline_result != current_result:
            results_consistent = False
        
        print(f"{run_time:.2f} сек ({len(placed)} размещено)")
    
    avg_time = sum(times) / len(times)
    min_time = min(times)
    max_time = max(times)
    
    print(f"   📊 Среднее время: {avg_time:.2f} сек")
    print(f"   📊 Мин/Макс: {min_time:.2f} / {max_time:.2f} сек")
    print(f"   📊 Разброс: ±{((max_time - min_time) / avg_time * 100):.1f}%")
    
    if results_consistent:
        print(f"   ✅ Результаты стабильны: {baseline_result[0]} размещено, {baseline_result[1]} не размещено")
    else:
        print(f"   ❌ Результаты нестабильны - есть проблема в алгоритме!")
    
    return avg_time, results_consistent

def performance_comparison():
    """Сравнение ожидаемой и фактической производительности."""
    print(f"\n⚡ Анализ производительности:")
    
    # Запускаем тест
    placement_time, total_time = benchmark_tank300()
    avg_time, consistent = benchmark_multiple_runs()
    
    if placement_time is None:
        print(f"❌ Не удалось провести тесты производительности")
        return False
    
    # Анализируем результаты
    print(f"\n📈 РЕЗУЛЬТАТЫ ОПТИМИЗАЦИИ:")
    
    # Ожидаемые времена для разных категорий производительности
    if avg_time < 1.0:
        performance_rating = "🚀 ОТЛИЧНО"
        performance_desc = "Очень быстро"
    elif avg_time < 3.0:
        performance_rating = "✅ ХОРОШО" 
        performance_desc = "Быстро"
    elif avg_time < 10.0:
        performance_rating = "⚠️ ПРИЕМЛЕМО"
        performance_desc = "Умеренно"
    else:
        performance_rating = "❌ МЕДЛЕННО"
        performance_desc = "Требуется дополнительная оптимизация"
    
    print(f"   Производительность: {performance_rating}")
    print(f"   Описание: {performance_desc}")
    print(f"   Среднее время размещения: {avg_time:.2f} сек")
    
    # Основные оптимизации
    print(f"\n🔧 ПРИМЕНЁННЫЕ ОПТИМИЗАЦИИ:")
    print(f"   1. ✅ Быстрая проверка bounding box в check_collision")
    print(f"   2. ✅ Раннее прерывание циклов коллизий")
    print(f"   3. ✅ Предварительная проверка границ")
    print(f"   4. ✅ Минимизация создания полигонов")
    print(f"   5. ✅ Кеширование вычислений offset'ов")
    
    success = avg_time < 10.0 and consistent
    
    if success:
        print(f"\n🎉 ОПТИМИЗАЦИЯ УСПЕШНА!")
        print(f"   Алгоритм работает быстро и стабильно")
    else:
        print(f"\n⚠️ Требуется дополнительная работа")
        if not consistent:
            print(f"   - Результаты нестабильны")
        if avg_time >= 10.0:
            print(f"   - Время выполнения слишком большое")
    
    return success

if __name__ == "__main__":
    print("Запуск тестов производительности...")
    
    try:
        success = performance_comparison()
        
        print("\n" + "=" * 70)
        if success:
            print("✅ ОПТИМИЗАЦИЯ ЗАВЕРШЕНА УСПЕШНО!")
            print(f"   Версия {__version__} готова к использованию")
        else:
            print("❌ ТРЕБУЕТСЯ ДОПОЛНИТЕЛЬНАЯ ОПТИМИЗАЦИЯ")
            
        print("\nДля применения оптимизаций:")
        print("1. Очистите кеш: python clear_python_cache.py")
        print("2. Перезапустите Streamlit: streamlit run streamlit_demo.py")
        print(f"3. Проверьте версию: должна быть {__version__}")
        print("=" * 70)
        
    except Exception as e:
        print(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)