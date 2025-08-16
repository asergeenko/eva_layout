#!/usr/bin/env python3
"""
Тест синхронизации между визуализацией и сохранением DXF.
Проверяет, что детали в DXF файле точно соответствуют позициям на визуализации.
"""

import tempfile
import os
from shapely.geometry import Polygon
import ezdxf
import matplotlib.pyplot as plt
from layout_optimizer import (
    bin_packing, save_dxf_layout_complete, plot_layout,
    apply_placement_transform, parse_dxf_complete
)

def create_test_data():
    """Создает тестовые данные для проверки синхронизации."""
    
    # Создаем простые тестовые полигоны
    polygons = []
    
    # Прямоугольник 1
    rect1 = Polygon([(0, 0), (30, 0), (30, 20), (0, 20)])
    polygons.append((rect1, "rect1.dxf", "красный", "test_order"))
    
    # Прямоугольник 2 (будет повернут)
    rect2 = Polygon([(0, 0), (25, 0), (25, 15), (0, 15)])
    polygons.append((rect2, "rect2.dxf", "синий", "test_order"))
    
    # L-образная фигура
    l_shape = Polygon([(0, 0), (20, 0), (20, 10), (10, 10), (10, 20), (0, 20)])
    polygons.append((l_shape, "l_shape.dxf", "зеленый", "test_order"))
    
    return polygons

def create_original_dxf_data(polygons):
    """Создает данные оригинальных DXF файлов."""
    original_dxf_data_map = {}
    
    for polygon, filename, color, order_id in polygons:
        # Имитируем данные оригинального DXF
        original_dxf_data_map[filename] = {
            'combined_polygon': polygon,
            'original_entities': [],  # Упрощенный тест без оригинальных entities
            'polygons': [polygon],
            'bounds': polygon.bounds
        }
    
    return original_dxf_data_map

def test_placement_transformation():
    """Тестирует корректность функции apply_placement_transform."""
    print("=== Тест функции apply_placement_transform ===")
    
    # Создаем тестовый полигон
    original = Polygon([(10, 5), (40, 5), (40, 25), (10, 25)])
    
    # Параметры трансформации
    x_offset = 50
    y_offset = 30
    rotation_angle = 90
    
    # Применяем трансформацию
    transformed = apply_placement_transform(original, x_offset, y_offset, rotation_angle)
    
    print(f"Оригинальный полигон: bounds={original.bounds}")
    print(f"Трансформированный: bounds={transformed.bounds}")
    
    # Проверяем, что трансформация работает
    assert transformed.bounds != original.bounds, "Трансформация должна изменить bounds"
    
    print("✅ Функция apply_placement_transform работает корректно")
    return True

def test_dxf_visualization_sync():
    """Основной тест синхронизации DXF и визуализации."""
    print("\n=== Тест синхронизации DXF и визуализации ===")
    
    # Создаем тестовые данные
    polygons = create_test_data()
    original_dxf_data_map = create_original_dxf_data(polygons)
    sheet_size = (150, 100)  # см
    
    print(f"Тестируем {len(polygons)} полигонов на листе {sheet_size[0]}x{sheet_size[1]} см")
    
    # Выполняем размещение
    placed, unplaced = bin_packing(polygons, sheet_size, verbose=False)
    
    print(f"Размещено: {len(placed)}, не размещено: {len(unplaced)}")
    
    if not placed:
        print("❌ ОШИБКА: Не удалось разместить ни одного полигона")
        return False
    
    # Создаем временные файлы
    with tempfile.NamedTemporaryFile(suffix='.dxf', delete=False) as tmp_dxf:
        dxf_path = tmp_dxf.name
    
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_png:
        png_path = tmp_png.name
    
    try:
        # Сохраняем DXF
        save_dxf_layout_complete(placed, sheet_size, dxf_path, original_dxf_data_map)
        print(f"✅ DXF сохранен: {dxf_path}")
        
        # Создаем визуализацию
        plot_buf = plot_layout(placed, sheet_size)
        with open(png_path, 'wb') as f:
            f.write(plot_buf.getvalue())
        print(f"✅ Визуализация сохранена: {png_path}")
        
        # Читаем DXF и сравниваем позиции
        print("\n--- Проверка позиций в DXF ---")
        doc = ezdxf.readfile(dxf_path)
        msp = doc.modelspace()
        
        dxf_entities = list(msp)
        print(f"Найдено {len(dxf_entities)} элементов в DXF")
        
        # Сравниваем позиции
        sync_errors = 0
        
        for i, placed_item in enumerate(placed):
            if len(placed_item) >= 5:
                transformed_polygon, x_offset, y_offset, rotation_angle, file_name = placed_item[:5]
            else:
                continue
                
            print(f"\nПолигон {i+1} ({file_name}):")
            viz_bounds = transformed_polygon.bounds
            print(f"  Визуализация bounds: {viz_bounds}")
            
            # Ищем соответствующие элементы в DXF
            matching_entities = []
            for entity in dxf_entities:
                if hasattr(entity.dxf, 'layer') and file_name.replace('.dxf', '') in entity.dxf.layer:
                    matching_entities.append(entity)
            
            if matching_entities:
                print(f"  Найдено {len(matching_entities)} соответствующих элементов в DXF")
                
                # Проверяем bounds первого элемента
                entity = matching_entities[0]
                if entity.dxftype() == 'LWPOLYLINE':
                    points = list(entity.get_points())
                    if points:
                        xs = [p[0] for p in points]
                        ys = [p[1] for p in points]
                        dxf_bounds = (min(xs), min(ys), max(xs), max(ys))
                        print(f"  DXF bounds: {dxf_bounds}")
                        
                        # Проверяем соответствие (с допуском на погрешность)
                        tolerance = 1.0  # 1мм
                        bounds_match = all(
                            abs(viz_bounds[j] - dxf_bounds[j]) < tolerance 
                            for j in range(4)
                        )
                        
                        if bounds_match:
                            print(f"  ✅ Позиции соответствуют (допуск {tolerance}мм)")
                        else:
                            print(f"  ❌ НЕСООТВЕТСТВИЕ позиций!")
                            print(f"     Разность: {[viz_bounds[j] - dxf_bounds[j] for j in range(4)]}")
                            sync_errors += 1
            else:
                print(f"  ❌ Не найдено соответствующих элементов в DXF")
                sync_errors += 1
        
        # Итоговый результат
        if sync_errors == 0:
            print(f"\n✅ ТЕСТ ПРОЙДЕН: Все {len(placed)} полигонов синхронизированы между визуализацией и DXF")
            return True
        else:
            print(f"\n❌ ТЕСТ НЕ ПРОЙДЕН: Найдено {sync_errors} ошибок синхронизации")
            return False\n            \n    finally:\n        # Очистка временных файлов\n        for temp_file in [dxf_path, png_path]:\n            if os.path.exists(temp_file):\n                try:\n                    os.unlink(temp_file)\n                except:\n                    pass\n\ndef run_comprehensive_test():\n    \"\"\"Запускает полный набор тестов.\"\"\"\n    print(\"🔄 Комплексный тест синхронизации DXF и визуализации\")\n    print(\"=\" * 60)\n    \n    # Тест 1: Функция трансформации\n    test1_result = test_placement_transformation()\n    \n    # Тест 2: Синхронизация DXF и визуализации\n    test2_result = test_dxf_visualization_sync()\n    \n    print(\"\\n\" + \"=\" * 60)\n    print(\"📊 ИТОГОВЫЕ РЕЗУЛЬТАТЫ:\")\n    print(f\"• Тест функции трансформации: {'✅ ПРОЙДЕН' if test1_result else '❌ НЕ ПРОЙДЕН'}\")\n    print(f\"• Тест синхронизации DXF/визуализация: {'✅ ПРОЙДЕН' if test2_result else '❌ НЕ ПРОЙДЕН'}\")\n    \n    overall_success = test1_result and test2_result\n    if overall_success:\n        print(\"\\n🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ! Синхронизация работает корректно.\")\n    else:\n        print(\"\\n⚠️ ОБНАРУЖЕНЫ ПРОБЛЕМЫ! Требуется дополнительная отладка.\")\n    \n    return overall_success\n\nif __name__ == \"__main__\":\n    success = run_comprehensive_test()\n    exit(0 if success else 1)