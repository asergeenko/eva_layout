#!/usr/bin/env python3
"""
Отладка алгоритма bin_packing для выявления источника наложений.
"""

from layout_optimizer import bin_packing, check_collision, rotate_polygon, translate_polygon
from shapely.geometry import Polygon
import matplotlib.pyplot as plt

def debug_bin_packing_step_by_step():
    """Пошаговая отладка bin_packing"""
    print("=== ПОШАГОВАЯ ОТЛАДКА BIN_PACKING ===")
    
    # Создаем простой тест с заведомо размещаемыми полигонами
    test_polygons = [
        (Polygon([(0, 0), (50, 0), (50, 30), (0, 30)]), "rect1.dxf", "черный", "order1"),  # 5x3 см
        (Polygon([(0, 0), (40, 0), (40, 25), (0, 25)]), "rect2.dxf", "черный", "order1"),  # 4x2.5 см
        (Polygon([(0, 0), (60, 0), (60, 35), (0, 35)]), "rect3.dxf", "черный", "order1"),  # 6x3.5 см
    ]
    
    sheet_size = (200, 100)  # 20x10 см - достаточно большой лист
    
    print(f"Тестируем размещение {len(test_polygons)} простых прямоугольников:")
    for i, (poly, name, color, order) in enumerate(test_polygons):
        bounds = poly.bounds
        print(f"  {i+1}. {name}: {(bounds[2]-bounds[0])/10:.1f}x{(bounds[3]-bounds[1])/10:.1f} см")
    
    print(f"Размер листа: {sheet_size[0]/10:.1f}x{sheet_size[1]/10:.1f} см")
    
    # Запускаем bin_packing с подробным выводом
    placed, unplaced = bin_packing(test_polygons, sheet_size, verbose=True)
    
    print(f"\nРезультат bin_packing:")
    print(f"  Размещено: {len(placed)}")
    print(f"  Не размещено: {len(unplaced)}")
    
    # Детальный анализ размещенных полигонов
    if placed:
        print(f"\nДетальный анализ размещенных полигонов:")
        placed_polygons = []
        
        for i, placed_item in enumerate(placed):
            poly = placed_item[0]
            x_offset = placed_item[1] if len(placed_item) > 1 else "N/A"
            y_offset = placed_item[2] if len(placed_item) > 2 else "N/A"
            angle = placed_item[3] if len(placed_item) > 3 else "N/A"
            filename = placed_item[4] if len(placed_item) > 4 else "N/A"
            
            bounds = poly.bounds
            print(f"  Полигон {i+1} ({filename}):")
            print(f"    Bounds: {bounds}")
            print(f"    Размер: {(bounds[2]-bounds[0])/10:.1f}x{(bounds[3]-bounds[1])/10:.1f} см")
            print(f"    Смещения: x={x_offset}, y={y_offset}")
            print(f"    Угол: {angle}°")
            
            placed_polygons.append(poly)
        
        # Проверяем коллизии между размещенными полигонами
        print(f"\nПроверка коллизий между размещенными полигонами:")
        collision_found = False
        
        for i in range(len(placed_polygons)):
            for j in range(i+1, len(placed_polygons)):
                poly1 = placed_polygons[i]
                poly2 = placed_polygons[j]
                
                if check_collision(poly1, poly2):
                    collision_found = True
                    print(f"  ❌ КОЛЛИЗИЯ между полигонами {i+1} и {j+1}")
                    print(f"    Полигон {i+1}: bounds={poly1.bounds}")
                    print(f"    Полигон {j+1}: bounds={poly2.bounds}")
                    
                    # Вычисляем пересечение
                    intersection = poly1.intersection(poly2)
                    if intersection.area > 0:
                        print(f"    Площадь пересечения: {intersection.area/100:.2f} см²")
                else:
                    print(f"  ✅ Полигоны {i+1} и {j+1}: коллизий нет")
        
        if not collision_found:
            print(f"  🎉 Все полигоны размещены без коллизий!")
        
        # Визуализация результата
        visualize_placement(placed_polygons, sheet_size, "debug_simple_test")
        
        return not collision_found
    else:
        print("❌ Ни один полигон не был размещен!")
        return False

def debug_collision_function():
    """Отладка функции check_collision"""
    print(f"\n=== ОТЛАДКА ФУНКЦИИ CHECK_COLLISION ===")
    
    # Тест 1: Полигоны не пересекаются
    poly1 = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])
    poly2 = Polygon([(20, 0), (30, 0), (30, 10), (20, 10)])
    
    collision1 = check_collision(poly1, poly2)
    print(f"Тест 1 - Не пересекаются:")
    print(f"  Полигон 1: bounds={poly1.bounds}")
    print(f"  Полигон 2: bounds={poly2.bounds}")
    print(f"  Коллизия: {collision1} (ожидается: False)")
    
    # Тест 2: Полигоны пересекаются
    poly3 = Polygon([(0, 0), (15, 0), (15, 10), (0, 10)])
    poly4 = Polygon([(10, 0), (25, 0), (25, 10), (10, 10)])
    
    collision2 = check_collision(poly3, poly4)
    print(f"\nТест 2 - Пересекаются:")
    print(f"  Полигон 3: bounds={poly3.bounds}")
    print(f"  Полигон 4: bounds={poly4.bounds}")
    print(f"  Коллизия: {collision2} (ожидается: True)")
    
    # Проверяем площадь пересечения для понимания
    intersection = poly3.intersection(poly4)
    print(f"  Площадь пересечения: {intersection.area}")
    
    # Тест 3: Полигоны касаются (граничный случай)
    poly5 = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])
    poly6 = Polygon([(10, 0), (20, 0), (20, 10), (10, 10)])
    
    collision3 = check_collision(poly5, poly6)
    print(f"\nТест 3 - Касаются:")
    print(f"  Полигон 5: bounds={poly5.bounds}")
    print(f"  Полигон 6: bounds={poly6.bounds}")
    print(f"  Коллизия: {collision3} (ожидается: False)")
    
    # Проверяем различные типы взаимодействий
    intersects = poly5.intersects(poly6)
    touches = poly5.touches(poly6)
    print(f"  Intersects: {intersects}, Touches: {touches}")
    
    return collision1 == False and collision2 == True and collision3 == False

def visualize_placement(polygons, sheet_size, title):
    """Создает визуализацию размещения"""
    fig, ax = plt.subplots(figsize=(12, 8))
    
    # Рисуем границы листа
    sheet_width_mm = sheet_size[0] * 10
    sheet_height_mm = sheet_size[1] * 10
    
    sheet_rect = plt.Rectangle((0, 0), sheet_width_mm, sheet_height_mm, 
                              fill=False, edgecolor='red', linewidth=3, linestyle='--')
    ax.add_patch(sheet_rect)
    
    # Рисуем полигоны
    colors = ['blue', 'green', 'orange', 'purple', 'brown']
    
    for i, polygon in enumerate(polygons):
        color = colors[i % len(colors)]
        x, y = polygon.exterior.xy
        
        ax.fill(x, y, alpha=0.6, color=color, edgecolor='black', linewidth=2, 
                label=f'Полигон {i+1}')
        
        # Добавляем номер в центр
        centroid = polygon.centroid
        ax.annotate(f'{i+1}', (centroid.x, centroid.y), 
                   ha='center', va='center', fontsize=12, fontweight='bold', color='white')
    
    ax.set_xlim(-10, sheet_width_mm + 10)
    ax.set_ylim(-10, sheet_height_mm + 10)
    ax.set_aspect("equal")
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_title(f"Отладка размещения: {title}")
    ax.set_xlabel("X (мм)")
    ax.set_ylabel("Y (мм)")
    
    plt.tight_layout()
    
    output_path = f"/tmp/{title}_debug.png"
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"📊 Визуализация сохранена: {output_path}")

def debug_real_file_creation():
    """Отладка создания реального файла как в приложении"""
    print(f"\n=== ОТЛАДКА СОЗДАНИЯ РЕАЛЬНОГО ФАЙЛА ===")
    
    # Попробуем воспроизвести условия, которые приводят к наложениям
    # Используем данные, похожие на те, что могут быть в реальном файле
    
    complex_polygons = [
        # Имитируем сложные формы ковров
        (Polygon([(0, 0), (100, 0), (100, 50), (80, 50), (80, 30), (0, 30)]), "complex1.dxf", "черный", "order1"),
        (Polygon([(0, 0), (60, 0), (60, 40), (40, 40), (40, 60), (0, 60)]), "complex2.dxf", "черный", "order1"),
        (Polygon([(0, 0), (90, 0), (90, 20), (70, 20), (70, 70), (0, 70)]), "complex3.dxf", "черный", "order1"),
    ]
    
    # Меньший лист для принуждения к более плотной упаковке
    sheet_size = (150, 120)  # 15x12 см
    
    print(f"Тестируем сложные полигоны на листе {sheet_size[0]/10:.1f}x{sheet_size[1]/10:.1f} см")
    
    placed, unplaced = bin_packing(complex_polygons, sheet_size, verbose=True)
    
    print(f"\nРезультат:")
    print(f"  Размещено: {len(placed)}")
    print(f"  Не размещено: {len(unplaced)}")
    
    if placed:
        # Проверяем коллизии
        placed_polygons = [item[0] for item in placed]
        
        collision_found = False
        for i in range(len(placed_polygons)):
            for j in range(i+1, len(placed_polygons)):
                if check_collision(placed_polygons[i], placed_polygons[j]):
                    collision_found = True
                    print(f"❌ Найдена коллизия между полигонами {i+1} и {j+1}")
                    break
            if collision_found:
                break
        
        if not collision_found:
            print("✅ Коллизий не найдено в сложном тесте")
        
        visualize_placement(placed_polygons, sheet_size, "debug_complex_test")
        
        return not collision_found
    
    return True  # Если ничего не размещено, это не ошибка коллизий

if __name__ == "__main__":
    print("=" * 60)
    print("ДИАГНОСТИКА АЛГОРИТМА BIN_PACKING")
    print("=" * 60)
    
    # Запускаем все тесты
    test1_ok = debug_collision_function()
    test2_ok = debug_bin_packing_step_by_step()
    test3_ok = debug_real_file_creation()
    
    print("\n" + "=" * 60)
    print("ИТОГОВЫЙ РЕЗУЛЬТАТ ДИАГНОСТИКИ")
    print("=" * 60)
    
    if test1_ok:
        print("✅ Функция check_collision работает корректно")
    else:
        print("❌ Проблема в функции check_collision")
    
    if test2_ok:
        print("✅ Простое размещение работает без коллизий")
    else:
        print("❌ Найдены коллизии в простом размещении")
    
    if test3_ok:
        print("✅ Сложное размещение работает без коллизий")
    else:
        print("❌ Найдены коллизии в сложном размещении")
    
    if test1_ok and test2_ok and test3_ok:
        print("\n🎉 Все тесты пройдены! Проблема может быть в других частях системы.")
        print("Возможно, проблема возникает при обработке реальных DXF данных или")
        print("в процессе сохранения/чтения файлов.")
    else:
        print("\n🚨 Обнаружены проблемы в базовых алгоритмах!")
        print("Требуется исправление найденных багов.")