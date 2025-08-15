#!/usr/bin/env python3
"""
Анализ конкретного файла 200_140_1_black.dxf на предмет наложений.
"""

from layout_optimizer import parse_dxf_complete, check_collision
import matplotlib.pyplot as plt

def analyze_overlap_in_file(filepath):
    """Анализирует файл на предмет наложений ковров"""
    print(f"=== Анализ файла {filepath} ===")
    
    # Читаем DXF файл
    result = parse_dxf_complete(filepath, verbose=True)
    
    if not result['polygons']:
        print("❌ Не удалось прочитать полигоны из файла")
        return False
    
    print(f"\nНайдено полигонов: {len(result['polygons'])}")
    
    # Выводим информацию о каждом полигоне
    print(f"\nИнформация о полигонах:")
    carpets = []
    for i, polygon in enumerate(result['polygons']):
        bounds = polygon.bounds
        width_mm = bounds[2] - bounds[0]
        height_mm = bounds[3] - bounds[1]
        area_cm2 = polygon.area / 100  # mm² to cm²
        
        print(f"  Полигон {i+1}:")
        print(f"    Bounds: {bounds}")
        print(f"    Размер: {width_mm/10:.1f}x{height_mm/10:.1f} см")
        print(f"    Площадь: {area_cm2:.2f} см²")
        
        # Первый полигон обычно границы листа
        if i == 0:
            print(f"    (Вероятно, границы листа)")
        else:
            carpets.append((polygon, f"Ковер_{i}"))
    
    if len(carpets) == 0:
        print("❌ Не найдено ковров (только границы листа)")
        return False
    
    print(f"\nАнализ коллизий между {len(carpets)} коврами:")
    
    # Проверяем коллизии между коврами
    overlaps = []
    for i in range(len(carpets)):
        for j in range(i+1, len(carpets)):
            poly1, name1 = carpets[i]
            poly2, name2 = carpets[j]
            
            if check_collision(poly1, poly2):
                overlaps.append((i+1, j+1, name1, name2))
                print(f"  ❌ НАЛОЖЕНИЕ между {name1} и {name2}")
                print(f"    {name1}: bounds={poly1.bounds}")
                print(f"    {name2}: bounds={poly2.bounds}")
                
                # Вычисляем область пересечения
                intersection = poly1.intersection(poly2)
                if intersection.area > 0:
                    intersection_cm2 = intersection.area / 100
                    print(f"    Площадь пересечения: {intersection_cm2:.2f} см²")
            else:
                print(f"  ✅ {name1} и {name2}: коллизий нет")
    
    # Создаем визуализацию
    print(f"\n=== Создание визуализации ===")
    
    fig, ax = plt.subplots(figsize=(12, 8))
    
    colors = ['red', 'blue', 'green', 'orange', 'purple', 'brown', 'pink', 'gray', 'olive', 'cyan']
    
    # Рисуем все полигоны
    for i, polygon in enumerate(result['polygons']):
        color = colors[i % len(colors)]
        alpha = 0.3 if i == 0 else 0.7  # Границы листа полупрозрачные
        
        x, y = polygon.exterior.xy
        ax.fill(x, y, alpha=alpha, color=color, edgecolor='black', linewidth=2, 
                label=f'Границы листа' if i == 0 else f'Ковер {i}')
        
        # Добавляем номер в центр полигона
        centroid = polygon.centroid
        label_text = 'ЛИСТ' if i == 0 else f'К{i}'
        ax.annotate(label_text, (centroid.x, centroid.y), 
                   ha='center', va='center', fontsize=10, fontweight='bold', 
                   color='white' if i > 0 else 'black')
    
    ax.set_aspect("equal")
    ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    ax.grid(True, alpha=0.3)
    ax.set_title(f"Анализ наложений в {filepath.split('/')[-1]}")
    ax.set_xlabel("X (мм)")
    ax.set_ylabel("Y (мм)")
    
    plt.tight_layout()
    
    # Сохраняем визуализацию
    output_image = filepath.replace('.dxf', '_analysis.png')
    plt.savefig(output_image, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"✅ Визуализация сохранена: {output_image}")
    
    # Итоговый результат
    print(f"\n=== РЕЗУЛЬТАТ АНАЛИЗА ===")
    if len(overlaps) == 0:
        print(f"✅ НАЛОЖЕНИЙ НЕ НАЙДЕНО")
        print(f"Все {len(carpets)} ковров размещены корректно")
        return True
    else:
        print(f"❌ НАЙДЕНО {len(overlaps)} НАЛОЖЕНИЙ:")
        for i, j, name1, name2 in overlaps:
            print(f"  - {name1} пересекается с {name2}")
        return False

if __name__ == "__main__":
    filepath = "/home/sasha/proj/2025/eva_layout/200_140_1_black.dxf"
    
    print("=" * 60)
    print("АНАЛИЗ НАЛОЖЕНИЙ В DXF ФАЙЛЕ")
    print("=" * 60)
    
    success = analyze_overlap_in_file(filepath)
    
    print("=" * 60)
    if success:
        print("🎉 ФАЙЛ В ПОРЯДКЕ - наложений не обнаружено")
    else:
        print("🚨 В ФАЙЛЕ ЕСТЬ ПРОБЛЕМЫ - найдены наложения!")
        print("Это подтверждает наличие бага в алгоритме размещения.")
    print("=" * 60)