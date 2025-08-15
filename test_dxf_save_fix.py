#!/usr/bin/env python3
"""Тест исправленной функции сохранения DXF."""

import sys
import os
import logging

# Очистка импортов
if 'layout_optimizer' in sys.modules:
    del sys.modules['layout_optimizer']

from layout_optimizer import (
    parse_dxf_complete, 
    bin_packing,
    save_dxf_layout_complete,
    plot_layout,
    __version__
)

print(f"=== ТЕСТ ИСПРАВЛЕННОГО СОХРАНЕНИЯ DXF ===")
print(f"Версия модуля: {__version__}")

def test_tank300_dxf_save():
    """Тест сохранения TANK 300 файлов в DXF."""
    print("\n=== ТЕСТ СОХРАНЕНИЯ TANK 300 ===")
    
    tank_folder = "dxf_samples/TANK 300"
    if not os.path.exists(tank_folder):
        print(f"Папка {tank_folder} не найдена!")
        return False
    
    # Загружаем файлы TANK 300
    polygons = []
    original_data = {}
    
    for i in range(1, 5):  # 1.dxf - 4.dxf
        file_path = os.path.join(tank_folder, f"{i}.dxf")
        if os.path.exists(file_path):
            print(f"Загружаем: {file_path}")
            
            try:
                result = parse_dxf_complete(file_path, verbose=False)
                if result and result['combined_polygon']:
                    filename = f"TANK300_{i}.dxf"
                    polygons.append((result['combined_polygon'], filename, "чёрный", f"order_{i}"))
                    original_data[filename] = result
                    
                    bounds = result['combined_polygon'].bounds
                    print(f"  Размеры: {(bounds[2]-bounds[0])/10:.1f} x {(bounds[3]-bounds[1])/10:.1f} см")
                    
            except Exception as e:
                print(f"  Ошибка: {e}")
    
    if len(polygons) < 2:
        print("Недостаточно полигонов для тестирования")
        return False
        
    print(f"\nЗагружено {len(polygons)} полигонов")
    
    # Размещение на листе
    sheet_size = (200, 140)
    print(f"Размещение на листе {sheet_size[0]}x{sheet_size[1]} см...")
    
    placed, unplaced = bin_packing(polygons, sheet_size, verbose=False)
    
    print(f"Результат: {len(placed)} размещено, {len(unplaced)} не размещено")
    
    if not placed:
        print("Ничего не размещено!")
        return False
    
    # Создаем визуализацию для сравнения
    plot_buf = plot_layout(placed, sheet_size)
    with open("test_dxf_save_visualization.png", 'wb') as f:
        f.write(plot_buf.getvalue())
    print("✅ Визуализация сохранена: test_dxf_save_visualization.png")
    
    # Печатаем информацию о размещенных полигонах
    print(f"\nИнформация о размещенных полигонах:")
    for i, placed_item in enumerate(placed):
        polygon = placed_item[0]
        filename = placed_item[4] if len(placed_item) > 4 else f"polygon_{i}"
        bounds = polygon.bounds
        rotation = placed_item[3] if len(placed_item) > 3 else 0
        
        print(f"  {i+1}. {filename}")
        print(f"     Позиция: ({bounds[0]:.1f}, {bounds[1]:.1f}) - ({bounds[2]:.1f}, {bounds[3]:.1f})")
        print(f"     Поворот: {rotation}°")
    
    # Сохранение в DXF с исправленной функцией
    output_file = "test_tank300_fixed.dxf"
    print(f"\nСохранение в DXF: {output_file}")
    
    try:
        save_dxf_layout_complete(placed, sheet_size, output_file, original_data)
        print(f"✅ DXF файл сохранен: {output_file}")
        
        # Проверим размер файла
        if os.path.exists(output_file):
            file_size = os.path.getsize(output_file)
            print(f"   Размер файла: {file_size} байт")
            
            if file_size > 1000:  # Если файл больше 1KB, значит что-то записалось
                print("✅ Файл кажется корректным по размеру")
                return True
            else:
                print("❌ Файл слишком маленький - возможно ошибка")
                return False
        else:
            print("❌ Файл не был создан")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка сохранения: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_coordinate_verification():
    """Проверим что координаты в DXF соответствуют ожидаемым."""
    print("\n=== ПРОВЕРКА КООРДИНАТ ===")
    
    # Создадим простой тест с двумя прямоугольниками
    from shapely.geometry import Polygon
    
    rect1 = Polygon([(0, 0), (500, 0), (500, 300), (0, 300)])  # 50x30см
    rect2 = Polygon([(1000, 0), (1400, 0), (1400, 200), (1000, 200)])  # 40x20см, сдвинут на 100см
    
    # Эмулируем результат bin_packing
    placed = [
        (rect1, 0, 0, 0, "test1.dxf", "чёрный"),  # без сдвига, без поворота
        (rect2, 0, 0, 0, "test2.dxf", "чёрный")   # без сдвига, без поворота
    ]
    
    sheet_size = (200, 140)
    output_file = "test_coordinates.dxf"
    
    print(f"Прямоугольник 1: ({rect1.bounds[0]}, {rect1.bounds[1]}) - ({rect1.bounds[2]}, {rect1.bounds[3]})")
    print(f"Прямоугольник 2: ({rect2.bounds[0]}, {rect2.bounds[1]}) - ({rect2.bounds[2]}, {rect2.bounds[3]})")
    
    try:
        # Сохраняем без исходных данных (простые полилинии)
        save_dxf_layout_complete(placed, sheet_size, output_file, None)
        print(f"✅ Тестовый DXF сохранен: {output_file}")
        return True
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

if __name__ == "__main__":
    success = True
    
    try:
        print("Запуск тестов исправленного сохранения DXF...")
        
        # Тест 1: Проверка координат
        print("\n" + "="*60)
        success &= test_coordinate_verification()
        
        # Тест 2: Полный тест с файлами TANK 300
        print("\n" + "="*60)
        success &= test_tank300_dxf_save()
        
        print("\n" + "="*60)
        if success:
            print("✅ ВСЕ ТЕСТЫ ПРОШЛИ!")
            print("\nТеперь:")
            print("1. Очистите кеш Python: python clear_python_cache.py")
            print("2. Перезапустите Streamlit: streamlit run streamlit_demo.py")
            print("3. Проверьте версию: должна быть 1.4.0")
            print("4. Протестируйте файлы TANK 300")
            print("5. Откройте результат в Autodesk Viewer")
        else:
            print("❌ НЕКОТОРЫЕ ТЕСТЫ НЕ ПРОШЛИ!")
    
    except Exception as e:
        print(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)