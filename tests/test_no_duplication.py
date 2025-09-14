#!/usr/bin/env python3

"""
Test for no duplication issue - ensures carpets are removed from remaining_orders correctly
"""

import sys
import os
import importlib

# Добавляем корневую директорию в путь для импорта модулей
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Force reload of the module to ensure we get the latest version
if 'layout_optimizer' in sys.modules:
    importlib.reload(sys.modules["layout_optimizer"])

from layout_optimizer import bin_packing_with_inventory, Carpet
from shapely.geometry import Polygon

def test_no_duplication():
    """Test that carpets are not duplicated during placement - they should be placed exactly once"""
    
    # Large sheets to ensure polygons fit
    available_sheets = [
        {
            "name": "Лист чёрный", 
            "width": 1400,
            "height": 2000,
            "color": "чёрный", 
            "count": 20,
            "used": 0,
        },
        {
            "name": "Лист серый", 
            "width": 1400,
            "height": 2000,
            "color": "серый", 
            "count": 20,
            "used": 0,
        }
    ]
    
    polygons = []
    
    # Create test polygons with different orders and colors
    # Mix of black and gray colors to test different scenarios
    test_data = [
        ("Order_A", "чёрный", 5),
        ("Order_B", "серый", 4),
        ("Order_C", "чёрный", 3),
        ("Order_D", "серый", 6),
        ("Order_E", "чёрный", 2),
    ]
    
    expected_placements = {}
    total_expected = 0
    
    for order_id, color, count in test_data:
        for i in range(count):
            filename = f"{order_id}_carpet_{i+1}.dxf"
            width = 200 + (i * 10)  # Slightly different sizes
            height = 200 + (i * 5)
            polygon = Polygon([(0, 0), (width, 0), (width, height), (0, height)])
            priority = 1
            polygons.append(Carpet(polygon, filename, color, order_id, priority))
            expected_placements[filename] = 0  # Should be placed exactly once
            total_expected += 1
    
    print("=== ТЕСТ НА ОТСУТСТВИЕ ДУБЛИРОВАНИЯ ===")
    print(f"Всего полигонов: {len(polygons)}")
    print("Заказы и количества:")
    for order_id, color, count in test_data:
        print(f"  {order_id} ({color}): {count} ковров")
    print("ОЖИДАНИЕ: каждый ковер должен быть размещен ровно один раз")
    
    placed_layouts, unplaced_polygons = bin_packing_with_inventory(
        polygons,
        available_sheets,
        verbose=False,
    )
    
    print("\n=== РЕЗУЛЬТАТ ===")
    print(f"Листов создано: {len(placed_layouts)}")
    print(f"Неразмещенных полигонов: {len(unplaced_polygons)}")
    
    total_placed = sum(len(layout.placed_polygons) for layout in placed_layouts)
    print(f"Всего размещено: {total_placed}")
    
    # Check for duplications
    actual_placements = {}
    
    for layout in placed_layouts:
        for placed_tuple in layout.placed_polygons:
            # Handle different tuple structures
            filename = placed_tuple.filename
            if filename in expected_placements:
                actual_placements[filename] = actual_placements.get(filename, 0) + 1
    
    print("\nПроверка дублирования:")
    duplications = 0
    missing = 0
    correct_placements = 0
    
    for filename in expected_placements:
        count = actual_placements.get(filename, 0)
        if count == 0:
            print(f"  ❌ {filename}: не размещен (0 раз)")
            missing += 1
        elif count == 1:
            print(f"  ✅ {filename}: размещен корректно (1 раз)")
            correct_placements += 1
        else:
            print(f"  ❌ {filename}: дублирован ({count} раз)")
            duplications += count - 1
    
    # Check for unexpected files
    for filename, count in actual_placements.items():
        if filename not in expected_placements:
            print(f"  ⚠️  {filename}: неожиданный файл ({count} раз)")
    
    print(f"\nСТАТИСТИКА:")
    print(f"  Корректно размещено: {correct_placements}")
    print(f"  Дублировано: {duplications} дублирований")
    print(f"  Не размещено: {missing}")
    
    # Test passes if no duplications and no missing
    success = (duplications == 0) and (missing == 0) and (correct_placements == total_expected)
    
    if success:
        print("\n✅ ТЕСТ ПРОШЕЛ: НИ ОДНОГО ДУБЛИРОВАНИЯ НЕ ОБНАРУЖЕНО")
    else:
        print(f"\n❌ ТЕСТ НЕ ПРОШЕЛ:")
        if duplications > 0:
            print(f"   - Обнаружено {duplications} дублирований")
        if missing > 0:
            print(f"   - Не размещено {missing} ковров") 
    
    return success

def test_specific_sample_input():
    """Test with smaller subset similar to sample_input_test.xlsx structure"""
    
    available_sheets = [
        {
            "name": "Лист чёрный 140x200", 
            "width": 1400,
            "height": 2000,
            "color": "чёрный", 
            "count": 5,
            "used": 0,
        },
        {
            "name": "Лист серый 140x200", 
            "width": 1400,
            "height": 2000,
            "color": "серый", 
            "count": 5,
            "used": 0,
        }
    ]
    
    polygons = []
    
    # Simulate some real orders like in sample_input_test.xlsx
    orders = [
        ("ORD_001", "чёрный", 3),
        ("ORD_002", "серый", 2),
        ("ORD_003", "чёрный", 4),
        ("ORD_004", "серый", 1),
        ("ORD_005", "чёрный", 2),
    ]
    
    expected_count = 0
    for order_id, color, carpet_count in orders:
        for i in range(carpet_count):
            filename = f"{order_id}_{color}_carpet_{i+1}.dxf"
            # Realistic carpet sizes
            width = 300 + (i * 20)
            height = 250 + (i * 15)
            polygon = Polygon([(0, 0), (width, 0), (width, height), (0, height)])
            priority = 1
            polygons.append(Carpet(polygon, filename, color, order_id, priority))
            expected_count += 1
    
    print("\n=== ТЕСТ С ИМИТАЦИЕЙ РЕАЛЬНЫХ ДАННЫХ ===")
    print(f"Заказов: {len(orders)}")
    print(f"Всего ковров: {expected_count}")
    
    placed_layouts, unplaced_polygons = bin_packing_with_inventory(
        polygons,
        available_sheets,
        verbose=False,
    )
    
    # Count unique placements
    placed_files = set()
    total_placed = 0
    
    for layout in placed_layouts:
        for placed_tuple in layout.placed_polygons:
            total_placed += 1
            filename = placed_tuple.filename
            placed_files.add(filename)
    
    unique_placed = len(placed_files)
    duplications = total_placed - unique_placed
    
    print(f"Общее количество размещений: {total_placed}")
    print(f"Уникальных файлов размещено: {unique_placed}")
    print(f"Дублирований: {duplications}")
    
    success = duplications == 0
    
    if success:
        print("✅ ТЕСТ С РЕАЛЬНЫМИ ДАННЫМИ ПРОШЕЛ")
    else:
        print("❌ ТЕСТ С РЕАЛЬНЫМИ ДАННЫМИ НЕ ПРОШЕЛ")
    
    return success

if __name__ == "__main__":
    print("Запуск тестов на отсутствие дублирования...")
    
    result1 = test_no_duplication()
    result2 = test_specific_sample_input()
    
    overall_success = result1 and result2
    
    print(f"\n{'='*50}")
    print(f"ОБЩИЙ РЕЗУЛЬТАТ: {'✅ ВСЕ ТЕСТЫ ПРОШЛИ' if overall_success else '❌ ЕСТЬ ПРОВАЛЕННЫЕ ТЕСТЫ'}")