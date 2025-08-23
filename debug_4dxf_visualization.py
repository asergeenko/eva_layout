#!/usr/bin/env python3
"""
Анализ проблемы отображения файла 4.dxf в визуализации
"""

import sys
sys.path.insert(0, '.')

import os
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPolygon
from io import BytesIO
from layout_optimizer import parse_dxf_complete

def debug_4dxf_visualization():
    """Диагностика отображения 4.dxf"""
    print("🔍 ДИАГНОСТИКА ОТОБРАЖЕНИЯ 4.DXF")
    print("=" * 50)
    
    tank_file = "dxf_samples/TANK 300/4.dxf"
    if not os.path.exists(tank_file):
        print(f"❌ Файл {tank_file} не найден!")
        return
    
    # Парсим файл
    result = parse_dxf_complete(tank_file, verbose=False)
    
    print(f"Полигонов для визуализации: {len(result['polygons'])}")
    print(f"Главный слой: {result['bottom_layer_name']}")
    
    # Анализируем каждый полигон
    for i, poly in enumerate(result['polygons']):
        bounds = poly.bounds
        width = bounds[2] - bounds[0]
        height = bounds[3] - bounds[1]
        area = poly.area
        
        print(f"\nПолигон {i}:")
        print(f"  Размер: {width:.1f}×{height:.1f}мм")
        print(f"  Площадь: {area:.0f}")
        print(f"  Bounds: ({bounds[0]:.1f}, {bounds[1]:.1f}, {bounds[2]:.1f}, {bounds[3]:.1f})")
        
        # Проверяем геометрию полигона
        coords = list(poly.exterior.coords)
        print(f"  Точек в контуре: {len(coords)}")
        
        # Проверяем на треугольность
        if len(coords) <= 4:  # треугольник + замыкающая точка
            print(f"  ⚠️ ТРЕУГОЛЬНАЯ ФОРМА! Координаты:")
            for j, coord in enumerate(coords[:3]):  # первые 3 точки
                print(f"    {j}: ({coord[0]:.1f}, {coord[1]:.1f})")
        else:
            print(f"  ✅ Сложная форма с {len(coords)-1} точками")
    
    # Создаем визуализацию для сравнения
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 8))
    
    # Левая панель - все полигоны отдельно
    ax1.set_title("Все полигоны 4.dxf (отдельно)")
    colors = ['red', 'blue', 'green', 'orange', 'purple', 'brown', 'pink', 'gray']
    
    all_x, all_y = [], []
    for i, poly in enumerate(result['polygons']):
        x, y = poly.exterior.xy
        all_x.extend(x)
        all_y.extend(y)
        
        color = colors[i % len(colors)]
        ax1.fill(x, y, alpha=0.7, color=color, edgecolor='black', linewidth=1, 
                label=f"Полигон {i} (площадь: {poly.area:.0f})")
    
    ax1.set_xlim(min(all_x) - 50, max(all_x) + 50)
    ax1.set_ylim(min(all_y) - 50, max(all_y) + 50)
    ax1.set_aspect('equal')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # Правая панель - объединение полигонов (как в реальной визуализации)
    ax2.set_title("4.dxf как в алгоритме размещения")
    
    # Берем самый большой полигон (как делает алгоритм)
    if result['polygons']:
        largest_poly = max(result['polygons'], key=lambda p: p.area)
        x, y = largest_poly.exterior.xy
        ax2.fill(x, y, alpha=0.7, color='blue', edgecolor='black', linewidth=2, 
                label=f"Самый большой полигон (площадь: {largest_poly.area:.0f})")
        
        ax2.set_xlim(min(x) - 50, max(x) + 50)
        ax2.set_ylim(min(y) - 50, max(y) + 50)
        ax2.set_aspect('equal')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig("4dxf_analysis.png", dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"\n💾 Анализ сохранен в 4dxf_analysis.png")

if __name__ == "__main__":
    debug_4dxf_visualization()