#!/usr/bin/env python3
"""Debugging script to understand and fix the overlap issue."""

import sys
import os
import logging
import numpy as np
import matplotlib.pyplot as plt
from shapely.geometry import Polygon
from shapely import affinity

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('debug_overlap.log', mode='w', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

print("=== ОТЛАДКА ПРОБЛЕМЫ НАЛОЖЕНИЯ ===")
logger.info("Начинаем отладку проблемы наложения ковров")

# Force clear imports and reload
if 'layout_optimizer' in sys.modules:
    del sys.modules['layout_optimizer']

# Import our fixed module
from layout_optimizer import (
    parse_dxf_complete, 
    bin_packing, 
    check_collision,
    rotate_polygon,
    translate_polygon,
    plot_layout,
    __version__
)

print(f"Версия модуля layout_optimizer: {__version__}")
logger.info(f"Загружена версия модуля: {__version__}")

def test_collision_detection_detailed():
    """Детальная проверка функции проверки коллизий."""
    print("\n=== ДЕТАЛЬНАЯ ПРОВЕРКА КОЛЛИЗИЙ ===")
    
    # Создаем два простых прямоугольника
    poly1 = Polygon([(0, 0), (100, 0), (100, 50), (0, 50)])  # 100x50мм
    poly2 = Polygon([(101, 0), (201, 0), (201, 50), (101, 50)])  # 100x50мм, зазор 1мм
    poly3 = Polygon([(103, 0), (203, 0), (203, 50), (103, 50)])  # 100x50мм, зазор 3мм
    poly4 = Polygon([(99, 0), (199, 0), (199, 50), (99, 50)])   # 100x50мм, перекрытие 1мм
    
    print("Тест 1: Полигоны с зазором 1мм")
    collision1 = check_collision(poly1, poly2, min_gap=2.0)
    print(f"Результат: collision = {collision1} (должно быть True)")
    
    print("\nТест 2: Полигоны с зазором 3мм")
    collision2 = check_collision(poly1, poly3, min_gap=2.0)
    print(f"Результат: collision = {collision2} (должно быть False)")
    
    print("\nТест 3: Перекрывающиеся полигоны")
    collision3 = check_collision(poly1, poly4, min_gap=2.0)
    print(f"Результат: collision = {collision3} (должно быть True)")
    
    return collision1 and not collision2 and collision3

def create_simple_test_polygons():
    """Создать простые тестовые полигоны для проверки."""
    polygons = []
    
    # Создаем 4 прямоугольника 500x300мм каждый
    for i in range(4):
        # Располагаем их далеко друг от друга изначально
        x_offset = i * 1000  # 1000мм между центрами
        polygon = Polygon([
            (x_offset, 0), 
            (x_offset + 500, 0), 
            (x_offset + 500, 300), 
            (x_offset, 300)
        ])
        polygons.append((polygon, f"test_carpet_{i+1}.dxf", "чёрный", f"order_{i+1}"))
    
    return polygons

def test_bin_packing_detailed():
    """Детальная проверка алгоритма упаковки."""
    print("\n=== ДЕТАЛЬНАЯ ПРОВЕРКА УПАКОВКИ ===")
    
    # Создаем простые тестовые полигоны
    polygons = create_simple_test_polygons()
    
    # Большой лист для размещения всех полигонов
    sheet_size = (300, 200)  # 300x200 см
    
    print(f"Размещаем {len(polygons)} полигонов на листе {sheet_size[0]}x{sheet_size[1]} см")
    
    # Включаем детальное логирование
    logger.setLevel(logging.DEBUG)
    
    try:
        placed, unplaced = bin_packing(polygons, sheet_size, verbose=True)
        
        print(f"\nРезультат упаковки:")
        print(f"- Размещено: {len(placed)}")
        print(f"- Не размещено: {len(unplaced)}")
        
        if len(placed) > 1:
            print("\n=== ПРОВЕРКА НАЛОЖЕНИЙ СРЕДИ РАЗМЕЩЕННЫХ ===")
            overlaps = 0
            for i in range(len(placed)):
                for j in range(i+1, len(placed)):
                    poly1 = placed[i][0]
                    poly2 = placed[j][0]
                    
                    collision = check_collision(poly1, poly2, min_gap=2.0)
                    if collision:
                        overlaps += 1
                        bounds1 = poly1.bounds
                        bounds2 = poly2.bounds
                        print(f"❌ НАЛОЖЕНИЕ между полигоном {i} и {j}")
                        print(f"   Полигон {i}: ({bounds1[0]:.1f}, {bounds1[1]:.1f}) - ({bounds1[2]:.1f}, {bounds1[3]:.1f})")
                        print(f"   Полигон {j}: ({bounds2[0]:.1f}, {bounds2[1]:.1f}) - ({bounds2[2]:.1f}, {bounds2[3]:.1f})")
                        
                        # Вычисляем фактическое расстояние
                        try:
                            distance = poly1.distance(poly2)
                            print(f"   Расстояние: {distance:.2f}мм")
                        except:
                            print(f"   Расстояние: не удалось вычислить")
                        
                        # Проверяем пересечение
                        intersection = poly1.intersects(poly2)
                        print(f"   Пересечение: {intersection}")
                    else:
                        print(f"✅ Полигоны {i} и {j} размещены корректно")
            
            if overlaps == 0:
                print("✅ Все полигоны размещены без наложений!")
                return True
            else:
                print(f"❌ Найдено {overlaps} наложений!")
                return False
        else:
            print("Недостаточно размещенных полигонов для проверки наложений")
            return len(placed) > 0
            
    except Exception as e:
        print(f"❌ Ошибка в bin_packing: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_real_file():
    """Тест с реальным проблемным файлом."""
    print("\n=== ТЕСТ С РЕАЛЬНЫМ ФАЙЛОМ ===")
    
    dxf_file = "200_140_1_black.dxf"
    if not os.path.exists(dxf_file):
        print(f"Файл {dxf_file} не найден!")
        return False
    
    try:
        # Парсим файл
        result = parse_dxf_complete(dxf_file, verbose=False)
        if not result['combined_polygon']:
            print("Не удалось получить полигон из файла")
            return False
        
        polygon = result['combined_polygon']
        bounds = polygon.bounds
        original_width = (bounds[2] - bounds[0]) / 10  # в см
        original_height = (bounds[3] - bounds[1]) / 10  # в см
        
        print(f"Оригинальные размеры: {original_width:.1f} x {original_height:.1f} см")
        
        # Создаем два экземпляра ковра для тестирования наложения
        file_name = "test_carpet.dxf"
        color = "чёрный"
        order_id1 = "order_1"
        order_id2 = "order_2"
        
        polygons = [
            (polygon, f"{file_name}_1", color, order_id1),
            (polygon, f"{file_name}_2", color, order_id2)
        ]
        
        # Тестируем на разных размерах листов
        test_sheets = [
            (400, 300),  # Большой лист
            (300, 250),  # Средний лист
            (250, 200),  # Маленький лист
        ]
        
        for sheet_size in test_sheets:
            print(f"\nТестируем на листе {sheet_size[0]}x{sheet_size[1]} см:")
            
            try:
                placed, unplaced = bin_packing(polygons, sheet_size, verbose=False)
                
                print(f"  Размещено: {len(placed)}, Не размещено: {len(unplaced)}")
                
                if len(placed) >= 2:
                    # Проверяем наложения
                    collision = check_collision(placed[0][0], placed[1][0], min_gap=2.0)
                    print(f"  Наложение между коврами: {collision}")
                    
                    if collision:
                        # Детальная проверка
                        poly1 = placed[0][0]
                        poly2 = placed[1][0]
                        bounds1 = poly1.bounds
                        bounds2 = poly2.bounds
                        
                        print(f"    Ковер 1: ({bounds1[0]:.1f}, {bounds1[1]:.1f}) - ({bounds1[2]:.1f}, {bounds1[3]:.1f})")
                        print(f"    Ковер 2: ({bounds2[0]:.1f}, {bounds2[1]:.1f}) - ({bounds2[2]:.1f}, {bounds2[3]:.1f})")
                        
                        # Создаем визуализацию проблемы
                        try:
                            plot_buf = plot_layout(placed, sheet_size)
                            with open(f"problem_layout_{sheet_size[0]}x{sheet_size[1]}.png", 'wb') as f:
                                f.write(plot_buf.getvalue())
                            print(f"    Сохранена визуализация: problem_layout_{sheet_size[0]}x{sheet_size[1]}.png")
                        except Exception as e:
                            print(f"    Ошибка создания визуализации: {e}")
                
                if len(placed) > 0 and len(unplaced) == 0:
                    print("  ✅ Все ковры размещены успешно")
                elif len(placed) > 0:
                    print("  ⚠️ Частично размещены")
                else:
                    print("  ❌ Ничего не размещено")
                    
            except Exception as e:
                print(f"  ❌ Ошибка упаковки: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка обработки файла: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = True
    
    try:
        print("Запуск отладочных тестов...")
        
        # Тест 1: Проверка коллизий
        print("\n" + "="*50)
        success &= test_collision_detection_detailed()
        
        # Тест 2: Проверка упаковки с простыми полигонами
        print("\n" + "="*50)
        success &= test_bin_packing_detailed()
        
        # Тест 3: Проверка с реальным файлом
        print("\n" + "="*50)
        success &= test_real_file()
        
        print("\n" + "="*50)
        if success:
            print("✅ ВСЕ ТЕСТЫ ПРОШЛИ УСПЕШНО!")
            print("Проблема с наложениями должна быть решена.")
        else:
            print("❌ ОБНАРУЖЕНЫ ПРОБЛЕМЫ!")
            print("Требуется дополнительная отладка.")
            
        print(f"\nЛог отладки сохранен в: debug_overlap.log")
        
    except Exception as e:
        print(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)