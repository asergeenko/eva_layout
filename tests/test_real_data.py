#!/usr/bin/env python3
"""
Тест с реальными данными из tests/sample_input_test.xlsx для проверки эффективности алгоритма.
"""

import sys
import os
import pandas as pd

# Добавляем корневую директорию в путь для импорта модулей
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from layout_optimizer import (
    parse_dxf_complete,
    bin_packing_with_inventory,
    Carpet,
)
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def main():
    print("=== ТЕСТ С РЕАЛЬНЫМИ ДАННЫМИ ===")
    
    # Проверяем наличие файла
    excel_path = "tests/sample_input_test.xlsx"
    if not os.path.exists(excel_path):
        print(f"❌ Файл {excel_path} не найден")
        return
    
    # Читаем Excel
    print(f"📂 Читаем файл: {excel_path}")
    df = pd.read_excel(excel_path, sheet_name='ZAKAZ')
    
    # Первая строка содержит заголовки, переназначим колонки
    header_row = df.iloc[0]
    df.columns = [str(header_row[i]) if pd.notna(header_row[i]) else f'col_{i}' for i in range(len(header_row))]
    df = df[1:].reset_index(drop=True)  # Убираем строку с заголовками
    
    print(f"📋 Всего заказов в файле: {len(df)}")
    
    # Берем первые 15 заказов для тестирования (включая разные типы)
    test_orders = df.head(15).copy()
    print(f"🧪 Тестируем с {len(test_orders)} заказами")
    
    # Создаем листы
    available_sheets = [
        {
            "name": "Черный лист 140x200",
            "width": 140,
            "height": 200,
            "color": "чёрный", 
            "count": 5,
            "used": 0
        },
        {
            "name": "Серый лист 140x200",
            "width": 140,
            "height": 200,
            "color": "серый",
            "count": 5,
            "used": 0
        }
    ]
    
    # Обрабатываем заказы и создаем полигоны
    polygons = []
    orders_info = []
    
    for idx, row in test_orders.iterrows():
        order_id = f"ZAKAZ_row_{idx + 2}"  # +2 для соответствия нумерации в логах
        article = row['Артикул']
        product_name = row['ТОВАР']
        order_type = article.split('+')[0] if '+' in str(article) else "unknown"
        
        # Определяем цвет по артикулу (12=черный, 11=серый)
        color = 'чёрный'
        if '+12' in str(article):
            color = 'чёрный'
        elif '+11' in str(article):
            color = 'серый'
        
        # Пытаемся найти DXF файлы для этого заказа
        try:
            dxf_files = []
            # Ищем в папках по имени товара
            for root, dirs, files in os.walk("dxf_samples"):
                if product_name.upper() in root.upper():
                    for file in files:
                        if file.endswith('.dxf'):
                            dxf_files.append(os.path.join(root, file))
                            if len(dxf_files) >= 5:  # Ограничиваем количество файлов
                                break
                    if dxf_files:
                        break
            
            if not dxf_files:
                # Создаем синтетические полигоны для заказов без DXF
                polygon_count = min(5, len(article.split('+')))  # Примерное количество
                for i in range(polygon_count):
                    # Простые прямоугольные полигоны
                    from shapely.geometry import Polygon
                    poly = Polygon([(0, 0), (200, 0), (200, 150), (0, 150)])
                    filename = f"{product_name}_{i+1}.dxf"
                    polygons.append(Carpet(poly, filename, color, order_id))
                
                orders_info.append({
                    'order_id': order_id,
                    'files_count': polygon_count,
                    'color': color,
                    'synthetic': True
                })
            else:
                # Обрабатываем найденные DXF файлы
                for dxf_file in dxf_files[:3]:  # Берем максимум 3 файла для теста
                    try:
                        polygon_data = parse_dxf_complete(dxf_file)
                        if polygon_data and polygon_data[0]:  # Проверяем что полигон создан
                            polygon = polygon_data[0]
                            filename = os.path.basename(dxf_file)
                            polygons.append(Carpet(polygon, filename, color, order_id))
                    except Exception as e:
                        print(f"⚠️ Ошибка обработки {dxf_file}: {e}")
                        continue
                
                orders_info.append({
                    'order_id': order_id,
                    'files_count': len([p for p in polygons if p[3] == order_id]),
                    'color': color,
                    'synthetic': False
                })
        
        except Exception as e:
            print(f"⚠️ Ошибка обработки заказа {order_id}: {e}")
            continue
    
    print(f"📊 Создано {len(polygons)} полигонов из {len(orders_info)} заказов")
    
    # Показываем информацию о заказах
    for order_info in orders_info:
        synthetic_mark = " (синтетический)" if order_info['synthetic'] else ""
        print(f"  {order_info['order_id']}: {order_info['files_count']} файлов, цвет {order_info['color']}{synthetic_mark}")
    

    # Запуск оптимизации
    print("\n=== ЗАПУСК ОПТИМИЗАЦИИ (MAX_SHEETS_PER_ORDER=5) ===")
    MAX_SHEETS_PER_ORDER = 5
    
    placed_layouts, unplaced = bin_packing_with_inventory(
        polygons,
        available_sheets,
        verbose=False,
        max_sheets_per_order=MAX_SHEETS_PER_ORDER,
    )
    
    # Анализ результатов
    print("\n=== РЕЗУЛЬТАТЫ ===")
    print(f"Размещенных листов: {len(placed_layouts)}")
    print(f"Неразмещенных полигонов: {len(unplaced)}")
    
    print("\nДетали по листам:")
    single_polygon_sheets = 0
    for i, layout in enumerate(placed_layouts, 1):
        poly_count = len(layout['placed_polygons'])
        usage = layout.get('usage_percent', 0)
        orders_on_sheet = layout.get('orders_on_sheet', set())
        print(f"  Лист {i}: {poly_count} полигонов, {usage:.1f}% заполнение, заказы: {', '.join(sorted(orders_on_sheet))}")
        if poly_count <= 2:
            single_polygon_sheets += 1
    
    # Оценка эффективности
    total_polygons = len(polygons) - len(unplaced)
    efficiency_ok = single_polygon_sheets <= 2  # Максимум 2 листа с малым количеством полигонов
    
    if efficiency_ok:
        print("\n✅ АЛГОРИТМ РАБОТАЕТ ЭФФЕКТИВНО")
        print(f"   Размещено {total_polygons} полигонов на {len(placed_layouts)} листах")
        print(f"   Листов с малым заполнением: {single_polygon_sheets} (приемлемо)")
    else:
        print("\n❌ АЛГОРИТМ НЕЭФФЕКТИВЕН")
        print(f"   Размещено {total_polygons} полигонов на {len(placed_layouts)} листах")
        print(f"   Слишком много листов с малым заполнением: {single_polygon_sheets}")

if __name__ == "__main__":
    main()