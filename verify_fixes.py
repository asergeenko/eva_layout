#!/usr/bin/env python3
"""Проверка что исправления наложений работают."""

import os
import sys

# Очистка импортов
if 'layout_optimizer' in sys.modules:
    del sys.modules['layout_optimizer']

from layout_optimizer import bin_packing, check_collision, __version__
from shapely.geometry import Polygon

print("=== ПРОВЕРКА ИСПРАВЛЕНИЙ НАЛОЖЕНИЙ ===")
print(f"Версия модуля: {__version__}")

def test_simple_collision():
    """Простой тест функции проверки коллизий."""
    print("\nТест функции check_collision:")
    
    # Два прямоугольника с зазором 1мм (должно быть коллизией при min_gap=2мм)
    rect1 = Polygon([(0, 0), (100, 0), (100, 50), (0, 50)])
    rect2 = Polygon([(101, 0), (201, 0), (201, 50), (101, 50)])  # зазор 1мм
    
    collision = check_collision(rect1, rect2, min_gap=2.0)
    print(f"  Зазор 1мм при min_gap=2мм: collision = {collision} (должно быть True)")
    
    # Два прямоугольника с зазором 5мм (должно быть НЕ коллизией)
    rect3 = Polygon([(105, 0), (205, 0), (205, 50), (105, 50)])  # зазор 5мм
    collision2 = check_collision(rect1, rect3, min_gap=2.0)
    print(f"  Зазор 5мм при min_gap=2мм: collision = {collision2} (должно быть False)")
    
    return collision and not collision2

def test_bin_packing():
    """Тест алгоритма упаковки."""
    print("\nТест bin_packing:")
    
    # Создаем 2 простых прямоугольника
    rect1 = Polygon([(0, 0), (500, 0), (500, 300), (0, 300)])  # 50x30см
    rect2 = Polygon([(0, 0), (400, 0), (400, 200), (0, 200)])  # 40x20см
    
    polygons = [
        (rect1, "test1.dxf", "чёрный", "order1"),
        (rect2, "test2.dxf", "чёрный", "order2")
    ]
    
    # Размещаем на листе 200x140см
    placed, unplaced = bin_packing(polygons, (200, 140), verbose=False)
    
    print(f"  Размещено: {len(placed)}, Не размещено: {len(unplaced)}")
    
    if len(placed) >= 2:
        # Проверяем наложения
        collision = check_collision(placed[0][0], placed[1][0], min_gap=2.0)
        print(f"  Наложение между размещенными: {collision} (должно быть False)")
        return not collision
    else:
        print("  Не удалось разместить оба прямоугольника")
        return False

# Запуск тестов
success = True
success &= test_simple_collision()
success &= test_bin_packing()

print(f"\n{'='*50}")
if success:
    print("✅ ВСЕ ТЕСТЫ ПРОШЛИ! Исправления работают.")
    print("\nТеперь:")
    print("1. Перезапустите Streamlit приложение")
    print("2. В интерфейсе проверьте версию модуля: должна быть 1.3.0")
    print("3. Попробуйте размещение файлов TANK 300")
else:
    print("❌ ТЕСТЫ НЕ ПРОШЛИ! Проблема не решена.")
    
print("\nДля проверки в Streamlit:")
print("1. Закройте текущую сессию Streamlit (Ctrl+C)")
print("2. Запустите: streamlit run streamlit_demo.py")
print("3. В интерфейсе должно показать: 'Layout optimizer version: 1.3.0'")