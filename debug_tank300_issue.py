#!/usr/bin/env python3
"""Специальная отладка проблемы с файлами TANK 300."""

import sys
import os
import logging
import numpy as np
import matplotlib.pyplot as plt
from shapely.geometry import Polygon
from shapely import affinity

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('debug_tank300.log', mode='w', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

print("=== ОТЛАДКА ПРОБЛЕМЫ TANK 300 ===")

# Очистка импортов
if 'layout_optimizer' in sys.modules:
    del sys.modules['layout_optimizer']

# Импорт модуля
from layout_optimizer import (
    parse_dxf_complete, 
    bin_packing, 
    check_collision,
    rotate_polygon,
    translate_polygon,
    plot_layout,
    __version__
)

print(f"Версия модуля: {__version__}")

def test_tank300_files():
    """Тестирование файлов TANK 300."""
    print("\n=== ТЕСТИРОВАНИЕ ФАЙЛОВ TANK 300 ===")
    
    tank_folder = "dxf_samples/TANK 300"
    if not os.path.exists(tank_folder):
        print(f"Папка {tank_folder} не найдена!")
        return False
    
    # Загружаем все файлы из папки TANK 300
    dxf_files = []
    for i in range(1, 5):  # 1.dxf - 4.dxf
        file_path = os.path.join(tank_folder, f"{i}.dxf")
        if os.path.exists(file_path):
            dxf_files.append(file_path)
    
    if not dxf_files:
        print("Не найдено DXF файлов в папке TANK 300")
        return False
    
    print(f"Найдено файлов: {len(dxf_files)}")
    
    # Парсим файлы
    polygons = []
    original_data = {}
    
    for i, file_path in enumerate(dxf_files):
        print(f"\nПарсим файл {i+1}: {file_path}")
        
        try:
            result = parse_dxf_complete(file_path, verbose=False)
            if result and result['combined_polygon']:
                polygon = result['combined_polygon']
                bounds = polygon.bounds
                width_mm = bounds[2] - bounds[0]
                height_mm = bounds[3] - bounds[1]
                area_mm2 = polygon.area
                
                print(f"  Размеры: {width_mm/10:.1f} x {height_mm/10:.1f} см")
                print(f"  Площадь: {area_mm2/100:.2f} см²")
                
                filename = f"TANK300_{i+1}.dxf"
                color = "чёрный"
                order_id = f"tank_order_{i+1}"
                
                polygons.append((polygon, filename, color, order_id))
                original_data[filename] = result
                
            else:
                print(f"  ❌ Не удалось получить полигон")
        except Exception as e:
            print(f"  ❌ Ошибка парсинга: {e}")
    
    if not polygons:
        print("Не удалось получить полигоны из файлов")
        return False
    
    print(f"\nПолучено {len(polygons)} полигонов")
    
    # Тестируем размещение на листе 200x140 см
    sheet_size = (200, 140)
    print(f"\nТестируем размещение на листе {sheet_size[0]}x{sheet_size[1]} см")
    
    try:
        # Включаем детальное логирование для bin_packing
        logger.setLevel(logging.DEBUG)
        
        placed, unplaced = bin_packing(polygons, sheet_size, verbose=True)
        
        print(f"\nРезультат размещения:")
        print(f"  Размещено: {len(placed)}")
        print(f"  Не размещено: {len(unplaced)}")
        
        if placed:
            print("\n=== АНАЛИЗ РАЗМЕЩЕННЫХ ПОЛИГОНОВ ===")
            
            for i, placed_tuple in enumerate(placed):
                polygon = placed_tuple[0]
                x_offset = placed_tuple[1] if len(placed_tuple) > 1 else 0
                y_offset = placed_tuple[2] if len(placed_tuple) > 2 else 0
                angle = placed_tuple[3] if len(placed_tuple) > 3 else 0
                filename = placed_tuple[4] if len(placed_tuple) > 4 else f"polygon_{i}"
                
                bounds = polygon.bounds
                print(f"\nПолигон {i+1} ({filename}):")
                print(f"  Позиция: ({bounds[0]:.1f}, {bounds[1]:.1f}) - ({bounds[2]:.1f}, {bounds[3]:.1f})")
                print(f"  Смещение: ({x_offset:.1f}, {y_offset:.1f})")
                print(f"  Поворот: {angle}°")
                print(f"  Размер: {(bounds[2]-bounds[0])/10:.1f} x {(bounds[3]-bounds[1])/10:.1f} см")
                
                # Проверяем границы листа
                sheet_width_mm = sheet_size[0] * 10
                sheet_height_mm = sheet_size[1] * 10
                
                outside_bounds = (bounds[0] < -1 or bounds[1] < -1 or 
                                bounds[2] > sheet_width_mm + 1 or bounds[3] > sheet_height_mm + 1)
                
                if outside_bounds:
                    print(f"  ❌ ВЫХОДИТ ЗА ГРАНИЦЫ ЛИСТА!")
                    print(f"     Лист: (0, 0) - ({sheet_width_mm}, {sheet_height_mm})")
                else:
                    print(f"  ✅ В пределах листа")
            
            # Проверяем наложения
            print(f"\n=== ПРОВЕРКА НАЛОЖЕНИЙ ===")
            overlaps = 0
            
            for i in range(len(placed)):
                for j in range(i+1, len(placed)):
                    poly1 = placed[i][0]
                    poly2 = placed[j][0]
                    
                    collision = check_collision(poly1, poly2, min_gap=2.0)
                    
                    if collision:
                        overlaps += 1
                        print(f"❌ НАЛОЖЕНИЕ между полигоном {i+1} и {j+1}")
                        
                        # Детальная информация о наложении
                        bounds1 = poly1.bounds
                        bounds2 = poly2.bounds
                        
                        print(f"   Полигон {i+1}: ({bounds1[0]:.1f}, {bounds1[1]:.1f}) - ({bounds1[2]:.1f}, {bounds1[3]:.1f})")
                        print(f"   Полигон {j+1}: ({bounds2[0]:.1f}, {bounds2[1]:.1f}) - ({bounds2[2]:.1f}, {bounds2[3]:.1f})")
                        
                        # Проверяем пересечение
                        intersection = poly1.intersects(poly2)
                        print(f"   Пересекаются: {intersection}")
                        
                        if not intersection:
                            # Если не пересекаются, то проблема в расстоянии
                            try:
                                distance = poly1.distance(poly2)
                                print(f"   Расстояние: {distance:.2f}мм")
                            except:
                                print(f"   Расстояние: не удалось вычислить")
                    else:
                        distance_info = ""
                        try:
                            distance = poly1.distance(poly2)
                            distance_info = f" (расстояние: {distance:.1f}мм)"
                        except:
                            pass
                        print(f"✅ Полигоны {i+1} и {j+1} размещены корректно{distance_info}")
            
            if overlaps == 0:
                print(f"✅ Все {len(placed)} полигонов размещены без наложений!")
            else:
                print(f"❌ Найдено {overlaps} наложений из {len(placed)*(len(placed)-1)//2} возможных!")
            
            # Создаем визуализацию
            try:
                plot_buf = plot_layout(placed, sheet_size)
                with open("tank300_debug_layout.png", 'wb') as f:
                    f.write(plot_buf.getvalue())
                print(f"\n📊 Визуализация сохранена: tank300_debug_layout.png")
            except Exception as e:
                print(f"❌ Ошибка создания визуализации: {e}")
        
        return overlaps == 0 if placed else False
        
    except Exception as e:
        print(f"❌ Ошибка размещения: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_individual_polygon_placement():
    """Тестируем размещение отдельных полигонов."""
    print("\n=== ТЕСТ ИНДИВИДУАЛЬНОГО РАЗМЕЩЕНИЯ ===")
    
    # Создаем два простых прямоугольника
    rect1 = Polygon([(0, 0), (500, 0), (500, 300), (0, 300)])  # 50x30 см
    rect2 = Polygon([(0, 0), (600, 0), (600, 400), (0, 400)])  # 60x40 см
    
    polygons = [
        (rect1, "test1.dxf", "чёрный", "order1"),
        (rect2, "test2.dxf", "чёрный", "order2")
    ]
    
    sheet_size = (200, 140)
    print(f"Размещаем 2 прямоугольника на листе {sheet_size[0]}x{sheet_size[1]} см")
    
    try:
        placed, unplaced = bin_packing(polygons, sheet_size, verbose=True)
        
        print(f"Результат: {len(placed)} размещено, {len(unplaced)} не размещено")
        
        if len(placed) >= 2:
            collision = check_collision(placed[0][0], placed[1][0], min_gap=2.0)
            print(f"Наложение: {collision}")
            
            if collision:
                print("❌ ПРОСТЫЕ ПРЯМОУГОЛЬНИКИ НАКЛАДЫВАЮТСЯ!")
                return False
            else:
                print("✅ Простые прямоугольники размещены корректно")
                return True
        else:
            print("Не удалось разместить оба прямоугольника")
            return False
            
    except Exception as e:
        print(f"Ошибка: {e}")
        return False

if __name__ == "__main__":
    print("Запуск специальной отладки TANK 300...")
    
    success = True
    
    try:
        # Тест 1: Простые прямоугольники
        print("\n" + "="*60)
        simple_test = test_individual_polygon_placement()
        success &= simple_test
        
        if not simple_test:
            print("❌ БАЗОВЫЙ ТЕСТ НЕ ПРОШЕЛ! Проблема в алгоритме размещения.")
        
        # Тест 2: Файлы TANK 300
        print("\n" + "="*60)
        tank_test = test_tank300_files()
        success &= tank_test
        
        print("\n" + "="*60)
        if success:
            print("✅ ВСЕ ТЕСТЫ ПРОШЛИ! Проблема решена.")
        else:
            print("❌ ОБНАРУЖЕНЫ ПРОБЛЕМЫ! Требуется дополнительная доработка.")
            print("\nИнформация для отладки сохранена в: debug_tank300.log")
        
    except Exception as e:
        print(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)