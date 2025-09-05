#!/usr/bin/env python3
"""
Debug script to track VOLKSWAGEN TIGUAN polygon placement through the algorithm
"""

import sys
import os
import pandas as pd
import logging
from shapely.geometry import Polygon

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from layout_optimizer import (
    bin_packing_with_inventory,
)

# Настройка логирования для детальной отладки
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

def create_minimal_test_data():
    """Создает минимальный набор данных только с VOLKSWAGEN TIGUAN 1"""
    
    # Создаем только VOLKSWAGEN TIGUAN полигоны
    polygons = []
    
    # 5 полигонов VOLKSWAGEN TIGUAN 1 как в реальных данных
    for i in range(5):
        size = 80 + i * 10  
        poly = Polygon([(0, 0), (size, 0), (size, size-20), (0, size-20)])
        filename = f"VOLKSWAGEN TIGUAN 1_{i+1}.dxf"
        polygons.append((poly, filename, "чёрный", "ZAKAZ_row_17"))
        print(f"✓ Создан полигон: {filename}")
    
    # Добавим пару полигонов приоритета 2
    for i in range(5):
        poly = Polygon([(0, 0), (60, 0), (60, 40), (0, 40)])
        filename = f"PRIORITY2_BLACK_{i+1}.dxf"
        polygons.append((poly, filename, "чёрный", f"PRIORITY2_BLACK_{i+1}", 2))
    
    return polygons

def create_test_sheets():
    """Создает минимальный набор листов"""
    sheets = []
    
    # 3 черных листа
    for i in range(1, 4):
        sheets.append({
            "name": f"Черный лист {i}",
            "width": 140,
            "height": 200,
            "color": "чёрный",
            "count": 1,
            "used": 0
        })
    
    return sheets

def track_volkswagen_placement():
    """Отслеживает размещение VOLKSWAGEN TIGUAN файлов"""
    
    print("=== ТЕСТ РАЗМЕЩЕНИЯ VOLKSWAGEN TIGUAN ===")
    
    # Создаем тестовые данные
    test_polygons = create_minimal_test_data()
    test_sheets = create_test_sheets()
    
    print(f"📊 Создано {len(test_polygons)} полигонов")
    print(f"📄 Создано {len(test_sheets)} листов")
    
    # Проверяем какие файлы созданы
    input_volkswagen = []
    input_priority2 = []
    for poly in test_polygons:
        filename = poly[1]
        if "VOLKSWAGEN TIGUAN 1" in filename:
            input_volkswagen.append(filename)
        elif "PRIORITY2" in filename:
            input_priority2.append(filename)
    
    print(f"📋 Входные VOLKSWAGEN файлы: {input_volkswagen}")
    print(f"📋 Входные PRIORITY2 файлы: {input_priority2}")
    

    # Запуск алгоритма с включенным verbose
    print(f"\n=== ЗАПУСК АЛГОРИТМА ===")
    placed_layouts, unplaced = bin_packing_with_inventory(
        test_polygons,
        test_sheets,
        verbose=True,
        max_sheets_per_order=5,
    )
    
    print(f"\n=== РЕЗУЛЬТАТЫ ===")
    print(f"Использовано листов: {len(placed_layouts)}")
    print(f"Неразмещенных полигонов: {len(unplaced)}")
    
    # Анализ размещенных файлов
    placed_volkswagen = []
    placed_priority2 = []
    
    for i, layout in enumerate(placed_layouts, 1):
        print(f"\nЛист {i}:")
        poly_count = len(layout['placed_polygons'])
        usage = layout.get('usage_percent', 0)
        print(f"  • Полигонов: {poly_count}, заполнение: {usage:.1f}%")
        
        for poly in layout['placed_polygons']:
            filename = str(poly[1]) if len(poly) > 1 else "unknown"
            print(f"    - {filename}")
            
            if "VOLKSWAGEN TIGUAN 1" in filename:
                placed_volkswagen.append(filename)
            elif "PRIORITY2" in filename:
                placed_priority2.append(filename)
    
    # Анализ неразмещенных
    if unplaced:
        print(f"\nНЕРАЗМЕЩЕННЫЕ ({len(unplaced)}):")
        unplaced_volkswagen = []
        unplaced_priority2 = []
        
        for poly in unplaced:
            filename = str(poly[1]) if len(poly) > 1 else "unknown"
            print(f"  • {filename}")
            
            if "VOLKSWAGEN TIGUAN 1" in filename:
                unplaced_volkswagen.append(filename)
            elif "PRIORITY2" in filename:
                unplaced_priority2.append(filename)
    else:
        unplaced_volkswagen = []
        unplaced_priority2 = []
    
    # Итоговый анализ
    print(f"\n=== ИТОГОВЫЙ АНАЛИЗ ===")
    print(f"VOLKSWAGEN TIGUAN 1:")
    print(f"  • Входных файлов: {len(input_volkswagen)}")
    print(f"  • Размещенных файлов: {len(placed_volkswagen)}")
    print(f"  • Неразмещенных файлов: {len(unplaced_volkswagen)}")
    
    if unplaced_volkswagen:
        print(f"  • Неразмещенные: {unplaced_volkswagen}")
    
    target_files = ["VOLKSWAGEN TIGUAN 1_3.dxf", "VOLKSWAGEN TIGUAN 1_4.dxf"]
    for target in target_files:
        if target in placed_volkswagen:
            print(f"    ✅ {target} - РАЗМЕЩЕН")
        elif target in unplaced_volkswagen:
            print(f"    ❌ {target} - НЕ РАЗМЕЩЕН")
        else:
            print(f"    ⚠️ {target} - НЕ НАЙДЕН В РЕЗУЛЬТАТАХ")
    
    print(f"\nPRIORITY2:")
    print(f"  • Входных файлов: {len(input_priority2)}")
    print(f"  • Размещенных файлов: {len(placed_priority2)}")
    print(f"  • Неразмещенных файлов: {len(unplaced_priority2)}")
    
    if len(unplaced_volkswagen) > 0:
        print(f"\n❌ ПРОБЛЕМА: {len(unplaced_volkswagen)} VOLKSWAGEN файлов не размещены")
        return False
    else:
        print(f"\n✅ ВСЕ VOLKSWAGEN файлы размещены успешно")
        return True

if __name__ == "__main__":
    success = track_volkswagen_placement()
    sys.exit(0 if success else 1)