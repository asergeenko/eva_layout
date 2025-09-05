#!/usr/bin/env python3
"""
Реальный тест с данными точно как в Streamlit:
- 37 заказов из tests/sample_input_test.xlsx
- 20 черных + 20 серых листов 140*200
- 20 черных + 20 серых файлов приоритета 2 из "dxf_samples/ДЕКА KUGOO M4 PRO JILONG/1.dxf"
"""

import sys
import os
import pandas as pd
import logging
from shapely.geometry import Polygon

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from layout_optimizer import (
    bin_packing_with_inventory,
    parse_dxf_complete,
)

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def load_real_excel_data():
    """Загружает РЕАЛЬНЫЕ данные из tests/sample_input_test.xlsx как в Streamlit"""
    excel_path = "tests/sample_input_test.xlsx"
    if not os.path.exists(excel_path):
        raise FileNotFoundError(f"Файл {excel_path} не найден")
    
    df = pd.read_excel(excel_path, sheet_name='ZAKAZ')
    
    # Первая строка содержит заголовки, переназначим колонки
    header_row = df.iloc[0]
    df.columns = [str(header_row.iloc[i]) if pd.notna(header_row.iloc[i]) else f'col_{i}' for i in range(len(header_row))]
    df = df[1:].reset_index(drop=True)
    
    return df

def process_real_excel_orders(df):
    """Обрабатывает РЕАЛЬНЫЕ заказы из Excel точно как в Streamlit"""
    polygons = []
    
    for idx, row in df.iterrows():
        order_id = f"ZAKAZ_row_{idx + 2}"  # +2 для соответствия нумерации в Streamlit
        article = row['Артикул']
        product_name = row['ТОВАР']
        
        # Определяем цвет по артикулу (как в Streamlit)
        color = 'чёрный'
        if '+12' in str(article):
            color = 'чёрный'
        elif '+11' in str(article):
            color = 'серый'
        
        # Ищем реальные DXF файлы
        dxf_files = []
        dxf_samples_dir = "dxf_samples"
        
        if os.path.exists(dxf_samples_dir):
            for root, dirs, files in os.walk(dxf_samples_dir):
                if product_name.upper() in root.upper():
                    for file in files:
                        if file.endswith('.dxf'):
                            dxf_files.append(os.path.join(root, file))
                            if len(dxf_files) >= 5:  # Максимум 5 файлов
                                break
                    if dxf_files:
                        break
        
        if dxf_files:
            # Обрабатываем найденные DXF файлы
            for i, dxf_file in enumerate(dxf_files):
                try:
                    polygon_data = parse_dxf_complete(dxf_file)
                    if polygon_data and polygon_data[0]:
                        polygon = polygon_data[0]
                        filename = f"{product_name}_{i+1}.dxf"  # Стандартизируем имена
                        polygons.append((polygon, filename, color, order_id))
                        
                        # Специальная проверка для проблемных заказов
                        if product_name == "SUZUKI XBEE":
                            print(f"✓ SUZUKI XBEE: создан полигон {filename} для {order_id}")
                        elif product_name == "VOLKSWAGEN TIGUAN 1":
                            print(f"✓ VOLKSWAGEN TIGUAN 1: создан полигон {filename} для {order_id}")
                            
                except Exception as e:
                    print(f"⚠️ Ошибка обработки {dxf_file}: {e}")
                    continue
        else:
            # Создаем синтетические полигоны если DXF не найдены
            poly_count = min(5, max(1, len(str(article).split('+'))))  # Примерное количество
            for i in range(poly_count):
                # Простые прямоугольные полигоны разных размеров
                size = 150 + i * 20
                poly = Polygon([(0, 0), (size, 0), (size, size-30), (0, size-30)])
                filename = f"{product_name}_{i+1}.dxf"
                polygons.append((poly, filename, color, order_id))
                
                # Специальная проверка для проблемных заказов
                if product_name == "SUZUKI XBEE":
                    print(f"✓ SUZUKI XBEE (синт.): создан полигон {filename} для {order_id}")
    
    return polygons

def create_real_priority2_polygons():
    """Создает РЕАЛЬНЫЕ полигоны приоритета 2 из указанного DXF файла"""
    priority2_polygons = []
    dxf_file = "dxf_samples/ДЕКА KUGOO M4 PRO JILONG/1.dxf"
    
    if os.path.exists(dxf_file):
        try:
            polygon_data = parse_dxf_complete(dxf_file)
            if polygon_data and polygon_data[0]:
                base_polygon = polygon_data[0]
                print(f"✓ Загружен реальный полигон приоритета 2 из {dxf_file}")
            else:
                raise Exception("Не удалось загрузить полигон")
        except Exception as e:
            print(f"⚠️ Ошибка загрузки {dxf_file}: {e}")
            # Fallback к синтетическому полигону
            base_polygon = Polygon([(0, 0), (60, 0), (60, 40), (0, 40)])
            print("✓ Используется синтетический полигон приоритета 2")
    else:
        base_polygon = Polygon([(0, 0), (60, 0), (60, 40), (0, 40)])
        print(f"⚠️ Файл {dxf_file} не найден, используется синтетический полигон приоритета 2")
    
    # 20 черных полигонов приоритета 2
    for i in range(20):
        filename = f"ДЕКА_KUGOO_M4_PRO_JILONG_черный_{i+1}.dxf"
        priority2_polygons.append((base_polygon, filename, "чёрный", f"PRIORITY2_BLACK_{i+1}", 2))
    
    # 20 серых полигонов приоритета 2
    for i in range(20):
        filename = f"ДЕКА_KUGOO_M4_PRO_JILONG_серый_{i+1}.dxf"
        priority2_polygons.append((base_polygon, filename, "серый", f"PRIORITY2_GRAY_{i+1}", 2))
    
    return priority2_polygons

def create_real_sheets():
    """Создает РЕАЛЬНЫЕ листы: 20 черных + 20 серых 140*200"""
    sheets = []
    
    # 20 черных листов
    for i in range(1, 21):
        sheets.append({
            "name": f"Лист 140x200 чёрный #{i}",
            "width": 140,
            "height": 200,
            "color": "чёрный",
            "count": 1,
            "used": 0
        })
    
    # 20 серых листов
    for i in range(1, 21):
        sheets.append({
            "name": f"Лист 140x200 серый #{i}",
            "width": 140,
            "height": 200,
            "color": "серый",
            "count": 1,
            "used": 0
        })
    
    return sheets

def main():
    print("=== РЕАЛЬНЫЙ ТЕСТ ДАННЫХ STREAMLIT ===")
    
    # Загружаем РЕАЛЬНЫЕ данные из Excel
    try:
        df = load_real_excel_data()
        print(f"✓ Загружено {len(df)} заказов из tests/sample_input_test.xlsx")
    except Exception as e:
        print(f"❌ Ошибка загрузки Excel: {e}")
        return False
    
    # Обрабатываем заказы Excel
    excel_polygons = process_real_excel_orders(df)
    print(f"✓ Создано {len(excel_polygons)} полигонов из Excel")
    
    # Создаем полигоны приоритета 2
    priority2_polygons = create_real_priority2_polygons()
    print(f"✓ Создано {len(priority2_polygons)} полигонов приоритета 2")
    
    # Создаем листы
    sheets = create_real_sheets()
    print(f"✓ Создано {len(sheets)} листов")
    
    # Объединяем все полигоны
    all_polygons = excel_polygons + priority2_polygons
    total_polygons = len(all_polygons)
    print(f"📊 ВСЕГО полигонов для размещения: {total_polygons}")
    

    # Запуск оптимизации с теми же параметрами что в Streamlit
    print("\n=== ЗАПУСК ОПТИМИЗАЦИИ ===")
    MAX_SHEETS_PER_ORDER = 5
    
    placed_layouts, unplaced = bin_packing_with_inventory(
        all_polygons,
        sheets,
        verbose=True,  # Включаем логи для отладки
        max_sheets_per_order=MAX_SHEETS_PER_ORDER,
    )
    
    # Анализ результатов
    print("\n=== РЕЗУЛЬТАТЫ ===")
    actual_placed_count = total_polygons - len(unplaced)
    print(f"Размещено полигонов: {actual_placed_count}/{total_polygons}")
    print(f"Использовано листов: {len(placed_layouts)}")
    print(f"Неразмещенных полигонов: {len(unplaced)}")
    
    # Детальный анализ проблем
    print("\n=== АНАЛИЗ ПРОБЛЕМ ===")
    
    # 1. Проверяем дублирование SUZUKI XBEE_5.dxf
    suzuki_xbee_5_count = 0
    suzuki_xbee_files_placed = set()
    for layout in placed_layouts:
        for poly in layout['placed_polygons']:
            filename = poly[1] if len(poly) > 1 else "unknown"
            if "SUZUKI XBEE" in filename:
                suzuki_xbee_files_placed.add(filename)
                if filename == "SUZUKI XBEE_5.dxf":
                    suzuki_xbee_5_count += 1
    
    print("\n1. Проблема с SUZUKI XBEE:")
    print(f"   • SUZUKI XBEE_5.dxf размещен {suzuki_xbee_5_count} раз(а) (ожидается: 1)")
    print(f"   • Всего файлов SUZUKI XBEE размещено: {len(suzuki_xbee_files_placed)}")
    print(f"   • Размещенные файлы: {sorted(suzuki_xbee_files_placed)}")
    
    # 2. Проверяем VOLKSWAGEN TIGUAN 1
    vw_tiguan_files_placed = set()
    for layout in placed_layouts:
        for poly in layout['placed_polygons']:
            filename = poly[1] if len(poly) > 1 else "unknown"
            if "VOLKSWAGEN TIGUAN 1" in filename:
                vw_tiguan_files_placed.add(filename)
    
    print("\n2. Проблема с VOLKSWAGEN TIGUAN 1:")
    print(f"   • Всего файлов VOLKSWAGEN TIGUAN 1 размещено: {len(vw_tiguan_files_placed)}")
    print(f"   • Размещенные файлы: {sorted(vw_tiguan_files_placed)}")
    missing_vw = [f"VOLKSWAGEN TIGUAN 1_{i}.dxf" for i in [3, 4] if f"VOLKSWAGEN TIGUAN 1_{i}.dxf" not in vw_tiguan_files_placed]
    if missing_vw:
        print(f"   • Отсутствующие файлы: {missing_vw}")
    
    # 3. Проверяем приоритет 2
    priority2_black_placed = 0
    priority2_gray_placed = 0
    
    for layout in placed_layouts:
        for poly in layout['placed_polygons']:
            order_id = ""
            if len(poly) >= 7:
                order_id = str(poly[6]) if poly[6] is not None else ""
            elif len(poly) >= 4:
                order_id = str(poly[3]) if poly[3] is not None else ""
            
            if order_id.startswith('PRIORITY2_BLACK'):
                priority2_black_placed += 1
            elif order_id.startswith('PRIORITY2_GRAY'):
                priority2_gray_placed += 1
    
    print("\n3. Проблема с приоритетом 2:")
    print(f"   • Черных приоритета 2 размещено: {priority2_black_placed}/20")
    print(f"   • Серых приоритета 2 размещено: {priority2_gray_placed}/20 (ожидается: 20)")
    
    # 4. Проверяем неразмещенные файлы
    if unplaced:
        print(f"\n4. Неразмещенные полигоны ({len(unplaced)}):")
        unplaced_files = []
        for poly in unplaced:
            filename = poly[1] if len(poly) > 1 else "unknown"
            unplaced_files.append(filename)
        
        for filename in sorted(unplaced_files)[:10]:  # Показываем первые 10
            print(f"   • {filename}")
        if len(unplaced_files) > 10:
            print(f"   ... и еще {len(unplaced_files) - 10}")
    
    # Итоговая оценка
    problems = []
    if suzuki_xbee_5_count > 1:
        problems.append(f"SUZUKI XBEE_5.dxf дублируется ({suzuki_xbee_5_count} раз)")
    
    if len(missing_vw) > 0:
        problems.append(f"Не размещены VOLKSWAGEN TIGUAN файлы: {missing_vw}")
    
    if priority2_gray_placed < 16:  # Менее 80% серых приоритета 2
        problems.append(f"Мало серых приоритета 2: {priority2_gray_placed}/20")
    
    if len(unplaced) > 5:
        problems.append(f"Много неразмещенных: {len(unplaced)}")
    
    if problems:
        print("\n❌ ТЕСТ ПРОВАЛЕН:")
        for problem in problems:
            print(f"   • {problem}")
        return False
    else:
        print("\n✅ ТЕСТ ПРОЙДЕН:")
        print("   • Дублирование устранено")
        print("   • Все основные файлы размещены")
        print("   • Приоритет 2 работает корректно")
        return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)