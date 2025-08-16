#!/usr/bin/env python3

"""
Тест IMAGE трансформации с реальными данными из Streamlit
"""

import sys
import os
import pandas as pd
sys.path.append('.')

from layout_optimizer import (
    parse_dxf_complete, 
    bin_packing_with_inventory,
    save_dxf_layout_complete,
    get_color_for_file
)

def load_real_excel_data():
    """Загружаем реальные данные из Excel как в Streamlit"""
    
    excel_file = "13.08 вечер.xlsx"
    if not os.path.exists(excel_file):
        print(f"❌ Excel файл не найден: {excel_file}")
        return None, None
    
    try:
        # Читаем из листа "ZAKAZ" как в Streamlit
        df = pd.read_excel(excel_file, sheet_name="ZAKAZ")
        print(f"✅ Загружен Excel: {len(df)} строк")
        
        # Фильтруем только нужные строки (как в Streamlit)
        df_filtered = df[df['Заказ в работе'] == 'да'].copy()
        print(f"✅ Отфильтровано: {len(df_filtered)} заказов в работе")
        
        return df_filtered, excel_file
        
    except Exception as e:
        print(f"❌ Ошибка чтения Excel: {e}")
        return None, None

def test_real_image_transformation():
    """Тест с реальными данными из Excel"""
    
    print("=== ТЕСТ РЕАЛЬНОЙ IMAGE ТРАНСФОРМАЦИИ ===")
    
    # Загружаем Excel данные
    df, excel_file = load_real_excel_data()
    if df is None:
        return
    
    # Берем только первые несколько заказов для теста
    df_sample = df.head(3)  # Первые 3 заказа
    
    print(f"\nТестируем с {len(df_sample)} заказами:")
    for idx, row in df_sample.iterrows():
        print(f"  - {row['Заказчик/название проекта']}: {row['DXF файл для раскроя']}")
    
    # Загружаем DXF данные
    original_dxf_data_map = {}
    polygons_for_placement = []
    
    for idx, row in df_sample.iterrows():
        dxf_filename = row['DXF файл для раскроя']
        customer_name = row['Заказчик/название проекта']
        color = row['Цвет материала']
        quantity = int(row['Кол-во'])
        
        # Путь к DXF файлу
        dxf_path = f"dxf_samples/{customer_name}/{dxf_filename}"
        
        if os.path.exists(dxf_path):
            try:
                print(f"\nЗагружаем {dxf_path}...")
                dxf_data = parse_dxf_complete(dxf_path)
                
                # Проверяем наличие IMAGE сущностей
                image_count = sum(1 for ed in dxf_data['original_entities'] if ed['type'] == 'IMAGE')
                print(f"  IMAGE сущностей: {image_count}")
                
                original_dxf_data_map[dxf_path] = dxf_data
                
                # Добавляем полигоны с количеством
                polygon = dxf_data['combined_polygon']
                if polygon:
                    for q in range(quantity):
                        order_id = f"{customer_name}_{dxf_filename}_{q+1}"
                        polygons_for_placement.append((polygon, dxf_filename, color, order_id))
                        
            except Exception as e:
                print(f"  ❌ Ошибка загрузки {dxf_path}: {e}")
        else:
            print(f"  ❌ Файл не найден: {dxf_path}")
    
    if not polygons_for_placement:
        print("❌ Нет полигонов для размещения")
        return
    
    print(f"\n✅ Подготовлено {len(polygons_for_placement)} полигонов для размещения")
    
    # Выполняем размещение
    sheet_size = (1400, 2000)  # 140x200 см
    available_sheets = [
        {'width': sheet_size[0], 'height': sheet_size[1], 'count': 10, 'used': 0, 'color': 'черный'}
    ]
    
    print(f"\nВыполняем размещение...")
    try:
        layouts, unplaced = bin_packing_with_inventory(
            polygons_for_placement,
            available_sheets,
            verbose=False  # Отключаем verbose для чистоты вывода
        )
        
        if layouts:
            layout = layouts[0]  # Берем первый лист
            print(f"✅ Размещено {len(layout['placed_polygons'])} полигонов на первом листе")
            
            # Вызываем save_dxf_layout_complete
            output_file = "test_real_image_fix.dxf"
            
            print(f"\nСохраняем в DXF с исправленной IMAGE трансформацией...")
            save_dxf_layout_complete(
                layout['placed_polygons'], 
                layout['sheet_size'], 
                output_file, 
                original_dxf_data_map
            )
            
            print(f"✅ DXF файл сохранен: {output_file}")
            
            # Анализируем результат
            import ezdxf
            doc = ezdxf.readfile(output_file)
            msp = doc.modelspace()
            
            image_entities = [e for e in msp if e.dxftype() == 'IMAGE']
            print(f"\nАнализ результата:")
            print(f"  IMAGE сущностей в результате: {len(image_entities)}")
            
            in_bounds_count = 0
            for i, img in enumerate(image_entities):
                if hasattr(img.dxf, 'insert'):
                    pos = img.dxf.insert
                    
                    # Проверим, в пределах ли листа
                    if 0 <= pos[0] <= sheet_size[0] and 0 <= pos[1] <= sheet_size[1]:
                        in_bounds_count += 1
                        status = "✅"
                    else:
                        status = "❌"
                    
                    print(f"  IMAGE {i+1}: {status} позиция ({pos[0]:.1f}, {pos[1]:.1f})")
            
            print(f"\n📊 Статистика:")
            print(f"  Всего IMAGE: {len(image_entities)}")
            print(f"  В пределах листа: {in_bounds_count}")
            print(f"  Вне пределов: {len(image_entities) - in_bounds_count}")
            
            if in_bounds_count == len(image_entities):
                print(f"🎉 Все IMAGE сущности в правильных координатах!")
            else:
                print(f"⚠️  {len(image_entities) - in_bounds_count} IMAGE сущностей вне листа")
                
        else:
            print("❌ Размещение не удалось")
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_real_image_transformation()