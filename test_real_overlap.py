#!/usr/bin/env python3
"""
Тест для воспроизведения реальной проблемы наложения ковров.
"""

from layout_optimizer import rotate_polygon, translate_polygon, bin_packing, save_dxf_layout_complete, parse_dxf_complete
from shapely.geometry import Polygon
import tempfile
import os

def create_test_carpets():
    """Создание тестовых ковров"""
    # Создаем несколько ковров разной формы
    carpet1 = Polygon([(0, 0), (100, 0), (100, 60), (0, 60)])  # Прямоугольник 100x60
    carpet2 = Polygon([(0, 0), (80, 0), (80, 50), (0, 50)])    # Прямоугольник 80x50  
    carpet3 = Polygon([(0, 0), (90, 0), (90, 40), (0, 40)])    # Прямоугольник 90x40
    
    return [
        (carpet1, "carpet1.dxf", "серый", "order1"),
        (carpet2, "carpet2.dxf", "серый", "order1"), 
        (carpet3, "carpet3.dxf", "серый", "order1")
    ]

def test_overlap_issue():
    """Тест воспроизведения проблемы наложения"""
    print("=== Тест проблемы наложения ковров ===")
    
    carpets = create_test_carpets()
    sheet_size = (300, 200)  # 30x20 см лист
    
    print(f"Размещаем {len(carpets)} ковров на листе {sheet_size[0]/10}x{sheet_size[1]/10} см")
    
    # Запускаем bin_packing
    placed, unplaced = bin_packing(carpets, sheet_size, verbose=False)
    
    print(f"\nРезультат bin_packing:")
    print(f"  Размещено: {len(placed)}")
    print(f"  Не размещено: {len(unplaced)}")
    
    if len(placed) == 0:
        print("❌ Ни один ковер не размещен!")
        return False
    
    # Выводим информацию о размещенных коврах
    print(f"\nИнформация о размещенных коврах:")
    for i, placed_carpet in enumerate(placed):
        polygon = placed_carpet[0]
        x_offset = placed_carpet[1] if len(placed_carpet) > 1 else 0
        y_offset = placed_carpet[2] if len(placed_carpet) > 2 else 0
        angle = placed_carpet[3] if len(placed_carpet) > 3 else 0
        filename = placed_carpet[4] if len(placed_carpet) > 4 else "unknown"
        
        print(f"  Ковер {i+1} ({filename}):")
        print(f"    Bounds: {polygon.bounds}")
        print(f"    Смещение: ({x_offset}, {y_offset})")
        print(f"    Угол: {angle}°")
    
    # Проверяем коллизии в размещенных коврах
    print(f"\nПроверка коллизий:")
    from layout_optimizer import check_collision
    
    overlaps = []
    for i in range(len(placed)):
        for j in range(i+1, len(placed)):
            poly1 = placed[i][0]
            poly2 = placed[j][0]
            if check_collision(poly1, poly2):
                overlaps.append((i+1, j+1))
                print(f"  ❌ Коллизия между коврами {i+1} и {j+1}")
                print(f"    Ковер {i+1}: bounds={poly1.bounds}")
                print(f"    Ковер {j+1}: bounds={poly2.bounds}")
    
    if not overlaps:
        print(f"  ✅ Коллизий в bin_packing не найдено")
    
    # Теперь тестируем сохранение в DXF и чтение обратно
    print(f"\n=== Тест сохранения в DXF ===")
    
    # Создаем исходные данные с пустыми entity списками (как в реальной проблеме)
    original_dxf_data_map = {}
    for carpet_data in carpets:
        filename = carpet_data[1]
        original_polygon = carpet_data[0]
        original_dxf_data_map[filename] = {
            'combined_polygon': original_polygon,
            'original_entities': []  # Пустой список - источник проблемы
        }
    
    # Сохраняем в DXF с исходными данными (с пустыми entity)
    with tempfile.NamedTemporaryFile(suffix='.dxf', delete=False) as tmp_file:
        output_path = tmp_file.name
    
    try:
        save_dxf_layout_complete(
            placed, 
            sheet_size, 
            output_path, 
            original_dxf_data_map  # С пустыми entities
        )
        print(f"✅ DXF файл сохранен: {output_path}")
        
        # Читаем обратно
        result = parse_dxf_complete(output_path, verbose=True)
        
        print(f"Результат чтения DXF: найдено {len(result['polygons']) if result['polygons'] else 0} полигонов")
        
        if result['polygons'] and len(result['polygons']) > 1:
            # Пропускаем границы листа (первый полигон)
            dxf_carpets = result['polygons'][1:]  
            print(f"Из DXF прочитано {len(dxf_carpets)} ковров")
            
            # Проверяем коллизии в прочитанных из DXF коврах
            print(f"\nПроверка коллизий в DXF:")
            dxf_overlaps = []
            for i in range(len(dxf_carpets)):
                for j in range(i+1, len(dxf_carpets)):
                    poly1 = dxf_carpets[i]
                    poly2 = dxf_carpets[j] 
                    if check_collision(poly1, poly2):
                        dxf_overlaps.append((i+1, j+1))
                        print(f"  ❌ Коллизия в DXF между коврами {i+1} и {j+1}")
                        print(f"    Ковер {i+1}: bounds={poly1.bounds}")
                        print(f"    Ковер {j+1}: bounds={poly2.bounds}")
            
            if not dxf_overlaps:
                print(f"  ✅ Коллизий в DXF не найдено")
                
            # Сравниваем количество коллизий
            if len(overlaps) == 0 and len(dxf_overlaps) > 0:
                print(f"\n🚨 ПРОБЛЕМА НАЙДЕНА!")
                print(f"  - В bin_packing коллизий: {len(overlaps)}")
                print(f"  - В DXF коллизий: {len(dxf_overlaps)}")
                print(f"  Проблема в save_dxf_layout_complete!")
                return False
            elif len(overlaps) > 0 and len(dxf_overlaps) == 0:
                print(f"\n🤔 Странная ситуация:")
                print(f"  - В bin_packing коллизий: {len(overlaps)}")
                print(f"  - В DXF коллизий: {len(dxf_overlaps)}")
                return False
            elif len(overlaps) == len(dxf_overlaps) == 0:
                print(f"\n✅ Все в порядке - коллизий нет нигде")
                return True
            else:
                print(f"\n⚠️  Количество коллизий разное:")
                print(f"  - В bin_packing коллизий: {len(overlaps)}")  
                print(f"  - В DXF коллизий: {len(dxf_overlaps)}")
                return len(overlaps) == len(dxf_overlaps)
        else:
            print(f"❌ Не удалось прочитать ковры из DXF")
            return False
            
    finally:
        if os.path.exists(output_path):
            os.unlink(output_path)

if __name__ == "__main__":
    success = test_overlap_issue()
    print(f"\n=== ИТОГОВЫЙ РЕЗУЛЬТАТ ===")
    if success:
        print("✅ Проблема наложения не воспроизведена - все работает корректно")
    else:
        print("❌ Проблема наложения воспроизведена - требует исправления")