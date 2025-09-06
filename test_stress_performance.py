#!/usr/bin/env python3

"""
Stress test to simulate real-world performance bottlenecks
"""

import time
import logging
from shapely.geometry import Polygon
from layout_optimizer import bin_packing_with_inventory, Carpet

# Включаем логирование WARNING для профилирования
logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(levelname)s - %(message)s')

def create_stress_test_data():
    """Create challenging test data that simulates real-world complexity"""
    
    # Реалистичные размеры листов (большие)
    available_sheets = []
    
    black_sheet = {
        "name": "Лист 140x200 чёрный", 
        "width": 140, 
        "height": 200,
        "color": "чёрный", 
        "count": 5,  # 5 листов
        "used": 0,
    }
    gray_sheet = {
        "name": "Лист 140x200 серый",
        "width": 140,
        "height": 200, 
        "color": "серый",
        "count": 5,  # 5 листов
        "used": 0,
    }
    available_sheets.extend([black_sheet, gray_sheet])
    
    # Создаем много ковров с реалистичными размерами
    carpets = []
    
    # Первая волна - крупные ковры (создают много препятствий)
    for i in range(40):  # 40 крупных ковров
        order_id = f"LARGE_{i:02d}"
        color = "чёрный" if i % 2 == 0 else "серый"
        filename = f"large_{i}.dxf"
        
        # Крупные размеры 60-100мм 
        size_x = 60 + (i % 15) * 3  # 60-102мм
        size_y = 70 + (i % 12) * 2  # 70-92мм
        
        # Создаем сложные формы (L-образные, U-образные)
        if i % 3 == 0:
            # L-образная форма
            polygon = Polygon([
                (0, 0), (size_x, 0), (size_x, size_y//2), 
                (size_x//2, size_y//2), (size_x//2, size_y), (0, size_y)
            ])
        elif i % 3 == 1:
            # U-образная форма
            w3 = size_x // 3
            polygon = Polygon([
                (0, 0), (size_x, 0), (size_x, size_y), (2*w3, size_y),
                (2*w3, size_y//2), (w3, size_y//2), (w3, size_y), (0, size_y)
            ])
        else:
            # Простой прямоугольник
            polygon = Polygon([(0, 0), (size_x, 0), (size_x, size_y), (0, size_y)])
        
        carpet = Carpet(
            polygon=polygon,
            filename=filename,
            color=color,
            order_id=order_id,
            priority=1
        )
        carpets.append(carpet)
    
    # Вторая волна - мелкие ковры (сложное размещение между препятствиями)
    for i in range(60):  # 60 мелких ковров
        order_id = f"SMALL_{i:02d}"
        color = "чёрный" if i % 2 == 0 else "серый"
        filename = f"small_{i}.dxf"
        
        # Мелкие размеры 20-40мм
        size = 20 + (i % 8) * 3  # 20-41мм
        
        # Различные простые формы
        if i % 4 == 0:
            # Квадрат
            polygon = Polygon([(0, 0), (size, 0), (size, size), (0, size)])
        elif i % 4 == 1:
            # Прямоугольник
            polygon = Polygon([(0, 0), (size*1.5, 0), (size*1.5, size), (0, size)])
        elif i % 4 == 2:
            # Треугольник
            polygon = Polygon([(0, 0), (size, 0), (size/2, size), (0, 0)])
        else:
            # Шестиугольник
            import math
            points = []
            for angle in range(0, 360, 60):
                x = size/2 + (size/2) * math.cos(math.radians(angle))
                y = size/2 + (size/2) * math.sin(math.radians(angle))
                points.append((x, y))
            polygon = Polygon(points)
        
        carpet = Carpet(
            polygon=polygon,
            filename=filename,
            color=color,
            order_id=order_id,
            priority=1
        )
        carpets.append(carpet)
    
    return available_sheets, carpets

def main():
    print("=== СТРЕСС-ТЕСТ ПРОИЗВОДИТЕЛЬНОСТИ ===")
    
    available_sheets, carpets = create_stress_test_data()
    
    print(f"Создано {len(available_sheets)} типов листов")
    print(f"Создано {len(carpets)} ковров")
    print(f"  - Крупные ковры: 40 шт (60-100мм)")
    print(f"  - Мелкие ковры: 60 шт (20-40мм)")
    print("Включено профилирование медленных операций...\n")
    
    start_time = time.time()
    
    try:
        placed_layouts, unplaced_carpets = bin_packing_with_inventory(
            carpets,
            available_sheets,
            verbose=False,
            max_sheets_per_order=5,
        )
        
        end_time = time.time()
        total_time = end_time - start_time
        
        print(f"\n=== РЕЗУЛЬТАТЫ СТРЕСС-ТЕСТА ===")
        print(f"⏱️  ОБЩЕЕ ВРЕМЯ: {total_time:.2f} секунд")
        print(f"📊 Размещенных листов: {len(placed_layouts)}")
        print(f"📦 Неразмещенных ковров: {len(unplaced_carpets)}")
        
        if placed_layouts:
            total_placed = sum(len(layout['placed_polygons']) for layout in placed_layouts)
            avg_usage = sum(layout.get('usage_percent', 0) for layout in placed_layouts) / len(placed_layouts)
            print(f"🎯 Всего ковров размещено: {total_placed}")
            print(f"📈 Среднее заполнение листов: {avg_usage:.1f}%")
            
            print("\nДетали по листам:")
            for layout in placed_layouts[:5]:  # Показываем первые 5
                print(f"  Лист {layout['sheet_number']}: {len(layout['placed_polygons'])} ковров, {layout.get('usage_percent', 0):.1f}%")
            if len(placed_layouts) > 5:
                print(f"  ... еще {len(placed_layouts) - 5} листов")
        
        # Оценка производительности
        carpets_per_second = len(carpets) / total_time if total_time > 0 else float('inf')
        print(f"\n🚀 ПРОИЗВОДИТЕЛЬНОСТЬ: {carpets_per_second:.1f} ковров/сек")
        
        if total_time < 10.0:
            print("✅ ОТЛИЧНАЯ производительность!")
        elif total_time < 30.0:
            print("✅ Хорошая производительность")
        elif total_time < 60.0:
            print("⚠️  Приемлемая производительность")
        elif total_time < 120.0:
            print("❌ Медленная производительность")
        else:
            print("❌❌ ОЧЕНЬ медленная производительность - критические узкие места!")
        
        print("\n=== УЗКИЕ МЕСТА ===")
        print("Если выше были предупреждения ⏱️, то узкие места:")
        print("- Медленный поиск позиций (много препятствий)")
        print("- Медленный расчет waste (сложная геометрия)")
        print("- Медленное дозаполнение (много полигонов)")
        
    except Exception as e:
        print(f"❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()