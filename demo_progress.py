#!/usr/bin/env python3
"""
Демо-скрипт для демонстрации прогресса оптимизации.
"""

import sys
import os
from shapely.geometry import Polygon

# Добавляем корневую директорию в путь для импорта модулей
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from layout_optimizer import (
    bin_packing_with_inventory,
    scale_polygons_to_fit,
)


def demo_progress():
    """Демонстрация работы прогресса."""
    print("=== ДЕМО ПРОГРЕССА ОПТИМИЗАЦИИ ===\n")
    
    # Настройка листов
    available_sheets = [
        {
            "name": "Лист 150x200 чёрный",
            "width": 150,
            "height": 200,
            "color": "чёрный", 
            "count": 10,
            "used": 0
        },
        {
            "name": "Лист 150x200 серый",
            "width": 150,
            "height": 200,
            "color": "серый", 
            "count": 10,
            "used": 0
        }
    ]
    
    # Создаем полигоны
    polygons = []
    
    print("Создаем тестовые полигоны...")
    
    # Priority 1 полигоны (Excel файлы)
    for i in range(15):
        # Варьируем размеры
        width = 400 + (i % 5) * 100  # От 400 до 800 мм
        height = 300 + (i % 4) * 100  # От 300 до 600 мм
        color = "чёрный" if i % 2 == 0 else "серый"
        
        polygon = Polygon([(0, 0), (width, 0), (width, height), (0, height)])
        polygons.append((
            polygon,
            f"excel_file_{i}.dxf",
            color,
            f"excel_order_{i}",
            1  # Priority 1
        ))
    
    # Priority 2 полигоны (дополнительные файлы)
    for i in range(8):
        # Меньшие размеры для заполнения пустот
        width = 200 + (i % 3) * 50   # От 200 до 300 мм
        height = 150 + (i % 3) * 50  # От 150 до 250 мм
        color = "чёрный" if i % 3 != 2 else "серый"
        
        polygon = Polygon([(0, 0), (width, 0), (width, height), (0, height)])
        polygons.append((
            polygon,
            f"priority2_file_{i}.dxf",
            color,
            f"group_priority2_{i}",
            2  # Priority 2
        ))
    
    print(f"Создано {len(polygons)} полигонов:")
    priority1_count = len([p for p in polygons if len(p) >= 5 and p[4] == 1])
    priority2_count = len([p for p in polygons if len(p) >= 5 and p[4] == 2])
    print(f"  - Priority 1 (Excel): {priority1_count}")
    print(f"  - Priority 2 (дополнительные): {priority2_count}")
    print()
    
    # Масштабирование
    print("Масштабирование полигонов...")
    reference_sheet_size = (150, 200)
    scaled_polygons = scale_polygons_to_fit(polygons, reference_sheet_size, verbose=False)
    print()
    
    # Колбек прогресса с визуализацией
    def show_progress(percent, status):
        # Создаем простую визуализацию прогресса
        bar_length = 40
        filled_length = int(bar_length * percent / 100)
        bar = "█" * filled_length + "░" * (bar_length - filled_length)
        print(f"\r[{bar}] {percent:5.1f}% - {status}", end="", flush=True)
        if percent >= 100:
            print()  # Новая строка в конце
    
    print("Начинаем оптимизацию с прогрессом:")
    
    # Запускаем оптимизацию
    layouts, unplaced = bin_packing_with_inventory(
        scaled_polygons,
        available_sheets,
        verbose=False,
        progress_callback=show_progress
    )
    
    print()
    print("=== РЕЗУЛЬТАТЫ ===")
    print(f"Создано листов: {len(layouts)}")
    print(f"Размещено объектов: {sum(len(layout['placed_polygons']) for layout in layouts)}")
    print(f"Не размещено: {len(unplaced)}")
    
    # Анализ по приоритетам
    priority1_placed = 0
    priority2_placed = 0
    
    for layout in layouts:
        for placed_tuple in layout["placed_polygons"]:
            if len(placed_tuple) >= 5:
                filename = placed_tuple[4]
                if "excel_" in filename:
                    priority1_placed += 1
                elif "priority2_" in filename:
                    priority2_placed += 1
    
    priority2_unplaced = 0
    for unplaced_tuple in unplaced:
        if len(unplaced_tuple) >= 2 and "priority2_" in unplaced_tuple[1]:
            priority2_unplaced += 1
    
    print()
    print("Размещение по приоритетам:")
    print(f"  Priority 1: {priority1_placed}/{priority1_count} размещено")
    print(f"  Priority 2: {priority2_placed}/{priority2_count} размещено, {priority2_unplaced} не размещено")
    
    # Информация о листах
    print()
    print("Информация о листах:")
    for i, layout in enumerate(layouts, 1):
        usage = layout["usage_percent"]
        sheet_type = layout["sheet_type"]
        objects_count = len(layout["placed_polygons"])
        print(f"  Лист #{i}: {sheet_type}, {objects_count} объектов, заполнение {usage:.1f}%")


if __name__ == "__main__":
    demo_progress()