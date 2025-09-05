#!/usr/bin/env python3
"""
Pytest тест для проверки размещения полигонов приоритета 2.
Запуск: python -m pytest test_priority2_pytest.py -v
"""

import sys
import os
import pytest
import logging
from shapely.geometry import Polygon

# Добавляем корневую директорию в путь для импорта модулей
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from layout_optimizer import bin_packing_with_inventory

# Настройка логирования для pytest
logging.basicConfig(level=logging.WARNING)  # Минимум логов для чистого вывода

@pytest.fixture
def sample_data():
    """Создает тестовые данные для проверки приоритета 2"""
    
    # Excel заказы (обычные)
    excel_polygons = []
    for i in range(10):  # 10 заказов по 2-3 полигона
        order_id = f"ZAKAZ_row_{i+2}"
        poly_count = 2 if i < 5 else 3  # Первые 5 - по 2, остальные - по 3
        color = "чёрный" if i % 2 == 0 else "серый"
        
        for j in range(poly_count):
            # Разные размеры полигонов
            size = 80 + i * 5
            poly = Polygon([(0, 0), (size, 0), (size, size-20), (0, size-20)])
            filename = f"order_{i+1}_{j+1}.dxf"
            excel_polygons.append((poly, filename, color, order_id))
    
    # Полигоны приоритета 2
    priority2_polygons = []
    
    # 10 черных приоритета 2
    for i in range(10):
        poly = Polygon([(0, 0), (50, 0), (50, 30), (0, 30)])  # Маленькие
        filename = f"priority2_black_{i+1}.dxf"
        priority2_polygons.append((poly, filename, "чёрный", f"P2_BLACK_{i+1}", 2))
    
    # 10 серых приоритета 2
    for i in range(10):
        poly = Polygon([(0, 0), (50, 0), (50, 30), (0, 30)])  # Маленькие
        filename = f"priority2_gray_{i+1}.dxf"
        priority2_polygons.append((poly, filename, "серый", f"P2_GRAY_{i+1}", 2))
    
    return excel_polygons, priority2_polygons

@pytest.fixture
def available_sheets():
    """Создает листы для тестирования"""
    sheets = []
    
    # 5 черных листов
    for i in range(1, 6):
        sheets.append({
            "name": f"Черный лист {i}",
            "width": 140,
            "height": 200,
            "color": "чёрный",
            "count": 1,
            "used": 0
        })
    
    # 5 серых листов
    for i in range(1, 6):
        sheets.append({
            "name": f"Серый лист {i}",
            "width": 140,
            "height": 200,
            "color": "серый",
            "count": 1,
            "used": 0
        })
    
    return sheets

def test_priority2_recognition(sample_data, available_sheets):
    """Проверяет, что алгоритм правильно распознает полигоны приоритета 2"""
    excel_polygons, priority2_polygons = sample_data
    all_polygons = excel_polygons + priority2_polygons
    
    # Запуск оптимизации
    placed_layouts, unplaced = bin_packing_with_inventory(
        all_polygons,
        available_sheets,
        verbose=False,
        max_sheets_per_order=5,
    )
    
    # Проверки
    assert len(placed_layouts) > 0, "Должны быть созданы листы"
    assert len(unplaced) == 0, "Все полигоны должны быть размещены"
    
    # Проверяем, что полигоны приоритета 2 размещены
    priority2_black_placed = 0
    priority2_gray_placed = 0
    
    for layout in placed_layouts:
        for poly in layout['placed_polygons']:
            order_id = ""
            if len(poly) >= 7:  # bin_packing_with_existing формат
                order_id = str(poly[6]) if poly[6] is not None else ""
            elif len(poly) >= 4:  # обычный формат
                order_id = str(poly[3]) if poly[3] is not None else ""
            
            if order_id.startswith('P2_BLACK'):
                priority2_black_placed += 1
            elif order_id.startswith('P2_GRAY'):
                priority2_gray_placed += 1
    
    # Основные проверки
    assert priority2_black_placed > 0, f"Черные приоритета 2 должны размещаться (размещено {priority2_black_placed}/10)"
    assert priority2_gray_placed > 0, f"Серые приоритета 2 должны размещаться (размещено {priority2_gray_placed}/10)"
    assert priority2_black_placed + priority2_gray_placed >= 15, "Должно размещаться минимум 75% полигонов приоритета 2"

def test_priority2_color_compatibility(sample_data, available_sheets):
    """Проверяет, что полигоны приоритета 2 размещаются на листы правильного цвета"""
    excel_polygons, priority2_polygons = sample_data
    all_polygons = excel_polygons + priority2_polygons
    

    # Запуск оптимизации
    placed_layouts, unplaced = bin_packing_with_inventory(
        all_polygons,
        available_sheets,
        verbose=False,
        max_sheets_per_order=5,
    )
    
    # Проверяем цветовую совместимость
    for layout in placed_layouts:
        sheet_color = layout.get('sheet_color', 'неизвестный')
        
        for poly in layout['placed_polygons']:
            # Обрабатываем разные форматы полигонов
            poly_color = "серый"  # default
            order_id = ""
            
            if len(poly) >= 7:  # bin_packing_with_existing формат
                order_id = str(poly[6]) if poly[6] is not None else ""
                # В 7-элементном формате цвет может быть в разных местах
                if len(poly) > 2 and isinstance(poly[2], str):
                    poly_color = poly[2]
                elif len(poly) > 5 and isinstance(poly[5], str):
                    poly_color = poly[5]
            elif len(poly) >= 4:  # обычный формат
                order_id = str(poly[3]) if poly[3] is not None else ""
                if isinstance(poly[2], str):
                    poly_color = poly[2]
            
            # Проверяем только полигоны приоритета 2
            if order_id.startswith('P2_'):
                # Упрощенная проверка: черные P2 должны быть на черных листах, серые на серых
                expected_color = "чёрный" if order_id.startswith('P2_BLACK') else "серый"
                assert sheet_color == expected_color, f"Полигон приоритета 2 {order_id} размещен на лист неправильного цвета: ожидался {expected_color}, получен {sheet_color}"

def test_priority2_efficiency(sample_data, available_sheets):
    """Проверяет эффективность размещения приоритета 2"""
    excel_polygons, priority2_polygons = sample_data
    all_polygons = excel_polygons + priority2_polygons
    

    # Запуск оптимизации
    placed_layouts, unplaced = bin_packing_with_inventory(
        all_polygons,
        available_sheets,
        verbose=False,
        max_sheets_per_order=5,
    )
    
    total_excel = len(excel_polygons)
    total_priority2 = len(priority2_polygons)
    total_polygons = total_excel + total_priority2
    
    actual_placed = total_polygons - len(unplaced)
    
    # Проверки эффективности
    assert actual_placed >= total_polygons * 0.9, f"Должно размещаться минимум 90% полигонов ({actual_placed}/{total_polygons})"
    assert len(placed_layouts) <= 6, f"Должно использоваться разумное количество листов ({len(placed_layouts)})"
    
    # Проверяем, что есть листы с приоритетом 2
    sheets_with_priority2 = 0
    for layout in placed_layouts:
        has_priority2 = False
        for poly in layout['placed_polygons']:
            order_id = ""
            if len(poly) >= 7:
                order_id = str(poly[6]) if poly[6] is not None else ""
            elif len(poly) >= 4:
                order_id = str(poly[3]) if poly[3] is not None else ""
            
            if order_id.startswith('P2_'):
                has_priority2 = True
                break
        
        if has_priority2:
            sheets_with_priority2 += 1
    
    assert sheets_with_priority2 > 0, "Должны быть листы с полигонами приоритета 2"

def test_priority2_threshold_behavior():
    """Проверяет, что приоритет 2 не размещается на очень заполненные листы"""
    
    # Создаем данные: один большой полигон + маленькие приоритета 2
    large_poly = Polygon([(0, 0), (120, 0), (120, 150), (0, 150)])  # Большой полигон
    small_priority2 = Polygon([(0, 0), (30, 0), (30, 20), (0, 20)])  # Маленький приоритет 2
    
    polygons = [
        (large_poly, "large.dxf", "чёрный", "LARGE_ORDER"),  # Заполнит лист почти полностью
        (small_priority2, "small_p2.dxf", "чёрный", "P2_TEST", 2)  # Приоритет 2
    ]
    
    sheets = [{
        "name": "Тест лист",
        "width": 140,
        "height": 200,
        "color": "чёрный",
        "count": 1,
        "used": 0
    }]
    

    # Запуск оптимизации
    placed_layouts, unplaced = bin_packing_with_inventory(
        polygons,
        sheets,
        verbose=False,
        max_sheets_per_order=5,
    )
    
    # Если лист заполнен более чем на 60%, приоритет 2 не должен размещаться
    if len(placed_layouts) > 0:
        first_layout = placed_layouts[0]
        usage = first_layout.get('usage_percent', 0)
        
        if usage > 60:
            # Проверяем, что приоритет 2 не размещен
            priority2_found = False
            for poly in first_layout['placed_polygons']:
                order_id = ""
                if len(poly) >= 7:
                    order_id = str(poly[6]) if poly[6] is not None else ""
                elif len(poly) >= 4:
                    order_id = str(poly[3]) if poly[3] is not None else ""
                
                if order_id.startswith('P2_'):
                    priority2_found = True
                    break
            
            assert not priority2_found, f"Приоритет 2 не должен размещаться на лист с заполнением {usage:.1f}%"

if __name__ == "__main__":
    # Запуск тестов если файл запущен напрямую
    pytest.main([__file__, "-v"])