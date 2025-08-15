#!/usr/bin/env python3
"""
Тест для проверки наложения ковров с поворотами.
"""

from layout_optimizer import rotate_polygon, translate_polygon, bin_packing, save_dxf_layout_complete, parse_dxf_complete, check_collision
from shapely.geometry import Polygon
import tempfile
import os

def create_test_carpets_for_rotation():
    """Создание тестовых ковров которые требуют поворота для размещения"""
    # Создаем ковры так, чтобы без поворотов они не помещались на листе 200x100
    carpet1 = Polygon([(0, 0), (150, 0), (150, 40), (0, 40)])  # 150x40 - поместится без поворота
    carpet2 = Polygon([(0, 0), (120, 0), (120, 60), (0, 60)])  # 120x60 - потребует поворот на узком листе
    carpet3 = Polygon([(0, 0), (100, 0), (100, 70), (0, 70)])  # 100x70 - потребует поворот
    
    return [
        (carpet1, "long_carpet.dxf", "серый", "order1"),
        (carpet2, "wide_carpet1.dxf", "серый", "order1"), 
        (carpet3, "wide_carpet2.dxf", "серый", "order1")
    ]

def test_rotation_overlap():
    """Тест наложения ковров при поворотах"""
    print("=== Тест наложения ковров с поворотами ===")
    
    carpets = create_test_carpets_for_rotation()
    sheet_size = (120, 120)  # Квадратный лист 12x12 см - потребует поворотов
    
    print(f"Размещаем {len(carpets)} ковров на узком листе {sheet_size[0]/10}x{sheet_size[1]/10} см")
    for i, carpet_data in enumerate(carpets):
        poly = carpet_data[0]
        name = carpet_data[1]
        bounds = poly.bounds
        width_cm = (bounds[2] - bounds[0]) / 10
        height_cm = (bounds[3] - bounds[1]) / 10
        print(f"  Ковер {i+1} ({name}): {width_cm:.1f}x{height_cm:.1f} см")
    
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
    rotated_count = 0
    for i, placed_carpet in enumerate(placed):
        polygon = placed_carpet[0]
        x_offset = placed_carpet[1] if len(placed_carpet) > 1 else 0
        y_offset = placed_carpet[2] if len(placed_carpet) > 2 else 0
        angle = placed_carpet[3] if len(placed_carpet) > 3 else 0
        filename = placed_carpet[4] if len(placed_carpet) > 4 else "unknown"
        
        if angle != 0:
            rotated_count += 1
        
        bounds = polygon.bounds
        width_mm = bounds[2] - bounds[0]
        height_mm = bounds[3] - bounds[1]
        
        print(f"  Ковер {i+1} ({filename}):")
        print(f"    Bounds: {polygon.bounds}")
        print(f"    Размер: {width_mm/10:.1f}x{height_mm/10:.1f} см")
        print(f"    Смещение: ({x_offset}, {y_offset})")
        print(f"    Угол: {angle}° {'(ПОВЕРНУТ!)' if angle != 0 else ''}")
    
    print(f"\nКоличество повернутых ковров: {rotated_count}")
    
    # Проверяем коллизии в размещенных коврах
    print(f"\nПроверка коллизий в bin_packing:")
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
    
    # Тестируем сохранение в DXF
    print(f"\n=== Тест сохранения повернутых ковров в DXF ===")
    
    # Создаем исходные данные
    original_dxf_data_map = {}
    for carpet_data in carpets:
        filename = carpet_data[1]
        original_polygon = carpet_data[0]
        original_dxf_data_map[filename] = {
            'combined_polygon': original_polygon,
            'original_entities': []  # Пустой список
        }
    
    # Сохраняем в DXF
    with tempfile.NamedTemporaryFile(suffix='.dxf', delete=False) as tmp_file:
        output_path = tmp_file.name
    
    try:
        save_dxf_layout_complete(
            placed, 
            sheet_size, 
            output_path, 
            original_dxf_data_map
        )
        print(f"✅ DXF файл с поворотами сохранен: {output_path}")
        
        # Читаем обратно
        result = parse_dxf_complete(output_path, verbose=False)
        
        print(f"Из DXF прочитано: {len(result['polygons']) if result['polygons'] else 0} полигонов")
        
        if result['polygons'] and len(result['polygons']) > 1:
            # Пропускаем границы листа (первый полигон)
            dxf_carpets = result['polygons'][1:]
            print(f"Ковров в DXF: {len(dxf_carpets)}")
            
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
            
            # Сравниваем результаты
            success = len(overlaps) == len(dxf_overlaps) == 0
            
            if success:
                print(f"\n✅ УСПЕХ: Повернутые ковры размещены правильно без наложений!")
                if rotated_count > 0:
                    print(f"   🔄 Успешно обработано {rotated_count} поворотов")
                return True
            else:
                print(f"\n❌ ПРОБЛЕМА: Найдены наложения в повернутых коврах!")
                print(f"   Коллизий в bin_packing: {len(overlaps)}")
                print(f"   Коллизий в DXF: {len(dxf_overlaps)}")
                return False
        else:
            print(f"❌ Не удалось прочитать ковры из DXF")
            return False
            
    finally:
        if os.path.exists(output_path):
            os.unlink(output_path)

if __name__ == "__main__":
    success = test_rotation_overlap()
    print(f"\n=== ИТОГОВЫЙ РЕЗУЛЬТАТ ===")
    if success:
        print("🎉 Проблема наложения ковров с поворотами НЕ ВОСПРОИЗВЕДЕНА!")
        print("Все исправления работают корректно.")
    else:
        print("🚨 Проблема наложения ковров с поворотами ВОСПРОИЗВЕДЕНА!")
        print("Требуются дополнительные исправления.")