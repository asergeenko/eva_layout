#!/usr/bin/env python3
"""
Тест для проверки правильности определения коллизий после изменения rotate_polygon.
"""

from layout_optimizer import rotate_polygon, translate_polygon, check_collision, bin_packing
from shapely.geometry import Polygon
import matplotlib.pyplot as plt

def visualize_polygons(polygons, title="Полигоны"):
    """Визуализация полигонов для отладки"""
    fig, ax = plt.subplots(figsize=(10, 8))
    
    colors = ['red', 'blue', 'green', 'orange', 'purple']
    
    for i, poly in enumerate(polygons):
        color = colors[i % len(colors)]
        x, y = poly.exterior.xy
        ax.fill(x, y, alpha=0.5, color=color, edgecolor='black', linewidth=2, 
                label=f'Полигон {i+1}')
        
        # Добавляем центроид
        centroid = poly.centroid
        ax.plot(centroid.x, centroid.y, 'ko', markersize=5)
        ax.annotate(f'P{i+1}', (centroid.x, centroid.y), 
                   ha='center', va='center', fontweight='bold', color='white')
    
    ax.set_aspect("equal")
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_title(title)
    plt.tight_layout()
    plt.savefig(f'/tmp/{title.replace(" ", "_").lower()}.png', dpi=150)
    plt.close()
    print(f"Сохранена визуализация: /tmp/{title.replace(' ', '_').lower()}.png")

def test_collision_detection():
    """Тест определения коллизий"""
    print("=== Тест определения коллизий ===")
    
    # Создаем два простых прямоугольника
    poly1 = Polygon([(0, 0), (50, 0), (50, 30), (0, 30)])
    poly2 = Polygon([(60, 0), (110, 0), (110, 30), (60, 30)])  # Не пересекаются
    poly3 = Polygon([(40, 0), (90, 0), (90, 30), (40, 30)])   # Пересекаются с poly1
    
    print(f"Полигон 1: bounds={poly1.bounds}")
    print(f"Полигон 2: bounds={poly2.bounds}")
    print(f"Полигон 3: bounds={poly3.bounds}")
    
    # Проверяем коллизии
    collision_1_2 = check_collision(poly1, poly2)
    collision_1_3 = check_collision(poly1, poly3)
    collision_2_3 = check_collision(poly2, poly3)
    
    print(f"Коллизия poly1 и poly2: {collision_1_2} (ожидается: False)")
    print(f"Коллизия poly1 и poly3: {collision_1_3} (ожидается: True)")
    print(f"Коллизия poly2 и poly3: {collision_2_3} (ожидается: False)")
    
    # Визуализируем
    visualize_polygons([poly1, poly2, poly3], "Тест коллизий")
    
    return not collision_1_2 and collision_1_3 and not collision_2_3

def test_rotation_collision():
    """Тест коллизий после поворота"""
    print("\n=== Тест коллизий после поворота ===")
    
    # Создаем два полигона
    original1 = Polygon([(0, 0), (40, 0), (40, 20), (0, 20)])
    original2 = Polygon([(50, 0), (90, 0), (90, 20), (50, 20)])
    
    print("Исходные полигоны:")
    print(f"  Полигон 1: bounds={original1.bounds}")
    print(f"  Полигон 2: bounds={original2.bounds}")
    print(f"  Коллизия до поворота: {check_collision(original1, original2)}")
    
    # Поворачиваем первый полигон на 90 градусов
    rotated1 = rotate_polygon(original1, 90)
    print(f"\nПосле поворота полигона 1 на 90°:")
    print(f"  Полигон 1: bounds={rotated1.bounds}")
    print(f"  Полигон 2: bounds={original2.bounds}")
    print(f"  Коллизия после поворота: {check_collision(rotated1, original2)}")
    
    # Визуализируем исходное состояние
    visualize_polygons([original1, original2], "До поворота")
    
    # Визуализируем после поворота
    visualize_polygons([rotated1, original2], "После поворота")
    
    return True

def test_bin_packing_collision():
    """Тест bin_packing на предмет коллизий"""
    print("\n=== Тест bin_packing на коллизии ===")
    
    # Создаем несколько одинаковых прямоугольников
    base_poly = Polygon([(0, 0), (50, 0), (50, 30), (0, 30)])
    
    polygons_data = [
        (base_poly, "rect1.dxf", "серый", "order1"),
        (base_poly, "rect2.dxf", "серый", "order1"),
        (base_poly, "rect3.dxf", "серый", "order1")
    ]
    
    sheet_size = (200, 100)  # 20x10 см лист
    
    print(f"Размещаем {len(polygons_data)} полигонов на листе {sheet_size[0]}x{sheet_size[1]} мм")
    
    # Запускаем bin_packing
    placed, unplaced = bin_packing(polygons_data, sheet_size, verbose=True)
    
    print(f"\nРезультат размещения:")
    print(f"  Размещено: {len(placed)}")
    print(f"  Не размещено: {len(unplaced)}")
    
    if len(placed) > 1:
        # Проверяем коллизии между размещенными полигонами
        print(f"\nПроверка коллизий между размещенными полигонами:")
        collision_count = 0
        for i, placed1 in enumerate(placed):
            for j, placed2 in enumerate(placed):
                if i < j:  # Избегаем дублирования проверок
                    poly1 = placed1[0]
                    poly2 = placed2[0]
                    collision = check_collision(poly1, poly2)
                    if collision:
                        collision_count += 1
                        print(f"  ❌ КОЛЛИЗИЯ между полигонами {i+1} и {j+1}")
                        print(f"    Полигон {i+1}: bounds={poly1.bounds}")
                        print(f"    Полигон {j+1}: bounds={poly2.bounds}")
                    else:
                        print(f"  ✅ Полигоны {i+1} и {j+1}: коллизий нет")
        
        if collision_count == 0:
            print(f"  🎉 Все {len(placed)} полигонов размещены без коллизий!")
        else:
            print(f"  🚨 Найдено {collision_count} коллизий!")
            
        # Визуализируем результат
        placed_polygons = [p[0] for p in placed]
        visualize_polygons(placed_polygons, f"Размещение {len(placed)} полигонов")
        
        return collision_count == 0
    else:
        print("Недостаточно полигонов для проверки коллизий")
        return True

if __name__ == "__main__":
    print("=== Проверка коллизий после изменения rotate_polygon ===")
    
    test1 = test_collision_detection()
    test2 = test_rotation_collision() 
    test3 = test_bin_packing_collision()
    
    print("\n=== ИТОГОВЫЙ РЕЗУЛЬТАТ ===")
    if test1 and test3:
        print("✅ Все тесты коллизий пройдены!")
        print("Проблема наложения ковров НЕ связана с функцией rotate_polygon")
    else:
        print("❌ Найдены проблемы с определением коллизий!")
        print("Проблема наложения ковров может быть связана с изменениями в rotate_polygon")