#!/usr/bin/env python3
"""
Тест исправления проблемы с приоритетом 2 (серые дополнительные коврики)
Имитирует точно такую же ситуацию как у пользователя в Streamlit
"""

import sys
import os
import logging
from shapely.geometry import Polygon

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from layout_optimizer import bin_packing_with_inventory

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def create_test_data():
    """
    Создает данные точно как в проблеме пользователя:
    - 37 заказов из Excel (разные размеры)
    - 20 черных + 20 серых дополнительных файлов приоритета 2
    """
    
    polygons = []
    
    # Имитируем 37 заказов из sample_input.xlsx с разными размерами
    excel_orders = [
        # Большие заказы (многополигонные)
        ("AUDI A4 1", "чёрный", [(0, 0), (120, 0), (120, 80), (0, 80)], 4),
        ("BMW X5 1", "чёрный", [(0, 0), (130, 0), (130, 90), (0, 90)], 3),
        ("MERCEDES-BENZ E-CLASS", "серый", [(0, 0), (125, 0), (125, 85), (0, 85)], 5),
        ("VOLKSWAGEN TIGUAN 1", "чёрный", [(0, 0), (115, 0), (115, 75), (0, 75)], 4),  # Этот не должен размещаться
        ("TOYOTA CAMRY 8", "серый", [(0, 0), (120, 0), (120, 80), (0, 80)], 3),
        
        # Средние заказы
        ("HYUNDAI SONATA 7", "чёрный", [(0, 0), (100, 0), (100, 60), (0, 60)], 2),
        ("KIA OPTIMA 4", "серый", [(0, 0), (105, 0), (105, 65), (0, 65)], 2),
        ("NISSAN X-TRAIL 3", "чёрный", [(0, 0), (110, 0), (110, 70), (0, 70)], 3),
        ("FORD FOCUS 4", "серый", [(0, 0), (95, 0), (95, 55), (0, 55)], 2),
        ("SKODA OCTAVIA 3", "чёрный", [(0, 0), (100, 0), (100, 60), (0, 60)], 2),
        
        # Маленькие заказы (по 1 полигону)
        ("SUZUKI XBEE", "чёрный", [(0, 0), (80, 0), (80, 50), (0, 50)], 1),  # Этот не должен размещаться
        ("LADA VESTA", "серый", [(0, 0), (85, 0), (85, 55), (0, 55)], 1),
        ("RENAULT LOGAN", "чёрный", [(0, 0), (90, 0), (90, 60), (0, 60)], 1),
        ("DACIA DUSTER", "серый", [(0, 0), (95, 0), (95, 65), (0, 65)], 1),
    ]
    
    # Добавляем еще заказы для достижения 37 заказов
    for i in range(len(excel_orders), 37):
        color = "чёрный" if i % 2 == 0 else "серый"
        size = 80 + (i % 20)  # Вариативные размеры
        order_name = f"AUTO_ORDER_{i+1}"
        poly_count = 1 if i > 30 else 2  # Последние заказы - по одному полигону
        excel_orders.append((order_name, color, [(0, 0), (size, 0), (size, size-20), (0, size-20)], poly_count))
    
    # Создаем полигоны для заказов Excel
    for idx, (product_name, color, coords, poly_count) in enumerate(excel_orders):
        order_id = f"ZAKAZ_row_{idx + 2}"  # Начинаем с row_2 как в Excel
        
        for poly_idx in range(poly_count):
            poly = Polygon(coords)
            filename = f"{product_name}_{poly_idx + 1}.dxf"
            polygons.append((poly, filename, color, order_id))
    
    print(f"Создано {len(polygons)} полигонов из {len(excel_orders)} заказов Excel")
    
    # Создаем дополнительные файлы приоритета 2
    priority2_polygons = []
    
    # 20 черных дополнительных файлов приоритета 2
    for i in range(20):
        poly = Polygon([(0, 0), (60, 0), (60, 40), (0, 40)])  # Размер как у ДЕКА KUGOO
        filename = f"ДЕКА_KUGOO_M4_PRO_JILONG_черный_{i+1}.dxf"
        priority2_polygons.append((poly, filename, "чёрный", f"PRIORITY2_BLACK_{i+1}", 2))  # priority=2!
    
    # 20 серых дополнительных файлов приоритета 2
    for i in range(20):
        poly = Polygon([(0, 0), (60, 0), (60, 40), (0, 40)])  # Размер как у ДЕКА KUGOO
        filename = f"ДЕКА_KUGOO_M4_PRO_JILONG_серый_{i+1}.dxf"
        priority2_polygons.append((poly, filename, "серый", f"PRIORITY2_GRAY_{i+1}", 2))  # priority=2!
    
    print(f"Создано {len(priority2_polygons)} полигонов приоритета 2 (20 черных + 20 серых)")
    
    return polygons, priority2_polygons

def create_sheets():
    """Создает листы: 20 черных + 20 серых 140*200"""
    sheets = []
    
    # 20 черных листов
    for i in range(1, 21):
        sheets.append({
            "name": f"Черный лист {i}",
            "width": 140,
            "height": 200,
            "color": "чёрный", 
            "count": 1,
            "used": 0
        })
    
    # 20 серых листов  
    for i in range(1, 21):
        sheets.append({
            "name": f"Серый лист {i}",
            "width": 140,
            "height": 200,
            "color": "серый", 
            "count": 1,
            "used": 0
        })
    
    return sheets

def main():
    print("=== ТЕСТ ИСПРАВЛЕНИЯ ПРИОРИТЕТА 2 ===")
    
    # Создаем данные
    excel_polygons, priority2_polygons = create_test_data()
    sheets = create_sheets()
    
    # Объединяем все полигоны
    all_polygons = excel_polygons + priority2_polygons
    total_polygons = len(all_polygons)
    
    print(f"📊 Всего для размещения: {total_polygons} полигонов")
    print(f"📄 Доступно листов: {len(sheets)} (20 черных + 20 серых)")
    

    # Запуск оптимизации
    print(f"\n=== ЗАПУСК ОПТИМИЗАЦИИ ===")
    MAX_SHEETS_PER_ORDER = 5
    
    placed_layouts, unplaced = bin_packing_with_inventory(
        all_polygons,
        sheets,
        verbose=True,
        max_sheets_per_order=MAX_SHEETS_PER_ORDER,
    )
    
    # Анализ результатов
    print(f"\n=== РЕЗУЛЬТАТЫ ===")
    actual_placed_count = total_polygons - len(unplaced)
    print(f"Размещено полигонов: {actual_placed_count}/{total_polygons}")
    print(f"Использовано листов: {len(placed_layouts)}")
    print(f"Неразмещенных полигонов: {len(unplaced)}")
    
    if unplaced:
        print(f"\n❌ НЕРАЗМЕЩЕННЫЕ ПОЛИГОНЫ:")
        excel_unplaced = []
        priority2_black_unplaced = []
        priority2_gray_unplaced = []
        
        for poly in unplaced:
            filename = poly[1] if len(poly) > 1 else "unknown"
            order_id = poly[3] if len(poly) > 3 else "unknown"
            
            if str(order_id).startswith('PRIORITY2_BLACK'):
                priority2_black_unplaced.append(filename)
            elif str(order_id).startswith('PRIORITY2_GRAY'):
                priority2_gray_unplaced.append(filename)
            else:
                excel_unplaced.append(filename)
        
        if excel_unplaced:
            print(f"   📋 Excel файлы ({len(excel_unplaced)}):")
            for f in excel_unplaced[:5]:  # Показываем первые 5
                print(f"      • {f}")
            if len(excel_unplaced) > 5:
                print(f"      ... и еще {len(excel_unplaced) - 5}")
        
        if priority2_black_unplaced:
            print(f"   ⚫ Черные приоритет 2 ({len(priority2_black_unplaced)}):")
            for f in priority2_black_unplaced[:3]:
                print(f"      • {f}")
            if len(priority2_black_unplaced) > 3:
                print(f"      ... и еще {len(priority2_black_unplaced) - 3}")
        
        if priority2_gray_unplaced:
            print(f"   🔘 Серые приоритет 2 ({len(priority2_gray_unplaced)}):")
            for f in priority2_gray_unplaced[:3]:
                print(f"      • {f}")
            if len(priority2_gray_unplaced) > 3:
                print(f"      ... и еще {len(priority2_gray_unplaced) - 3}")
    
    # Детальный анализ листов
    print(f"\n=== АНАЛИЗ ЛИСТОВ ===")
    priority2_black_placed = 0
    priority2_gray_placed = 0
    sheets_with_low_usage = []
    
    for i, layout in enumerate(placed_layouts, 1):
        poly_count = len(layout['placed_polygons'])
        usage = layout.get('usage_percent', 0)
        sheet_color = layout.get('sheet_color', 'неизвестный')
        
        # Подсчет приоритета 2 - полигоны могут быть в разных форматах
        p2_black = 0
        p2_gray = 0
        for p in layout['placed_polygons']:
            # Проверяем разные форматы полигонов
            order_id = ""
            if len(p) >= 7:  # bin_packing_with_existing возвращает 7-элементные кортежи
                order_id = str(p[6]) if p[6] is not None else ""
            elif len(p) >= 4:  # обычные 4-элементные кортежи
                order_id = str(p[3]) if p[3] is not None else ""
            elif len(p) >= 5:  # 5-элементные с приоритетом
                order_id = str(p[3]) if p[3] is not None else ""
            
            if order_id.startswith('PRIORITY2_BLACK'):
                p2_black += 1
            elif order_id.startswith('PRIORITY2_GRAY'):
                p2_gray += 1
        
        priority2_black_placed += p2_black
        priority2_gray_placed += p2_gray
        
        # Отслеживаем листы с низким заполнением начиная с 18 (как указал пользователь)
        if i >= 18 and usage < 70:
            sheets_with_low_usage.append((i, usage, sheet_color))
        
        sheet_info = f"  Лист {i} ({sheet_color}): {poly_count} полигонов, {usage:.1f}%"
        if p2_black > 0 or p2_gray > 0:
            sheet_info += f" [+{p2_black}чер.П2, +{p2_gray}сер.П2]"
        
        # Показываем только проблемные листы или те, что с приоритетом 2
        if i >= 18 or p2_black > 0 or p2_gray > 0:
            print(sheet_info)
    
    print(f"\n=== АНАЛИЗ ПРИОРИТЕТА 2 ===")
    print(f"Черных приоритета 2 размещено: {priority2_black_placed}/20")
    print(f"Серых приоритета 2 размещено: {priority2_gray_placed}/20")
    
    if sheets_with_low_usage:
        print(f"\n⚠️ Листы с низким заполнением (начиная с 18):")
        for sheet_num, usage, color in sheets_with_low_usage:
            print(f"   Лист {sheet_num} ({color}): {usage:.1f}%")
    
    # Проверка на успешность исправления
    problems = []
    
    # Проверяем основные проблемы пользователя
    excel_unplaced_count = len([p for p in unplaced if not str(p[3] if len(p) > 3 else "").startswith('PRIORITY2')])
    if excel_unplaced_count > 5:  # Пользователь говорил о 5 неразмещенных
        problems.append(f"Слишком много неразмещенных Excel файлов: {excel_unplaced_count}")
    
    priority2_gray_unplaced_count = len([p for p in unplaced if str(p[3] if len(p) > 3 else "").startswith('PRIORITY2_GRAY')])
    if priority2_gray_unplaced_count > 4:  # Пользователь говорил о 4 неразмещенных серых
        problems.append(f"Слишком много неразмещенных серых приоритета 2: {priority2_gray_unplaced_count}")
    
    if len(sheets_with_low_usage) > 5:
        problems.append(f"Много листов с низким заполнением начиная с 18: {len(sheets_with_low_usage)}")
    
    if priority2_gray_placed < 16:  # Ожидаем хотя бы 80% серых
        problems.append(f"Мало размещенных серых приоритета 2: {priority2_gray_placed}/20")
    
    if problems:
        print(f"\n❌ ПРОБЛЕМЫ НЕ ИСПРАВЛЕНЫ:")
        for problem in problems:
            print(f"   • {problem}")
        print(f"\n🔧 Рекомендации:")
        print(f"   • Проверить логику приоритета 2 для серых листов")
        print(f"   • Убедиться что алгоритм доходит до листов начиная с 18")
        print(f"   • Снизить порог заполнения для приоритета 2 еще больше")
        return False
    else:
        print(f"\n✅ ПРОБЛЕМЫ ИСПРАВЛЕНЫ!")
        print(f"   • Excel файлы: неразмещенных {excel_unplaced_count} (приемлемо)")
        print(f"   • Серые приоритет 2: размещено {priority2_gray_placed}/20")
        print(f"   • Черные приоритет 2: размещено {priority2_black_placed}/20")
        print(f"   • Листы с низким заполнением: {len(sheets_with_low_usage)} (приемлемо)")
        return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)