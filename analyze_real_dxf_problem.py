#!/usr/bin/env python3
"""
Анализ реального DXF файла для выявления проблемы с позиционированием.
"""

import ezdxf
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MPLPolygon
import numpy as np
from io import BytesIO

def analyze_real_dxf_file():
    """Анализирует реальный DXF файл."""
    print("=== АНАЛИЗ РЕАЛЬНОГО DXF ФАЙЛА ===")
    
    dxf_path = "/home/sasha/proj/2025/eva_layout/200_140_1_black.dxf"
    
    try:
        # Читаем DXF файл
        doc = ezdxf.readfile(dxf_path)
        msp = doc.modelspace()
        
        print(f"📁 Файл: {dxf_path}")
        print(f"📏 DXF версия: {doc.dxfversion}")
        
        # Находим все элементы
        all_entities = list(msp)
        print(f"🔢 Всего элементов в DXF: {len(all_entities)}")
        
        # Группируем элементы по типам
        entity_types = {}
        for entity in all_entities:
            entity_type = entity.dxftype()
            entity_types[entity_type] = entity_types.get(entity_type, 0) + 1
        
        print("📋 Типы элементов:")
        for etype, count in entity_types.items():
            print(f"  {etype}: {count}")
        
        # Анализируем LWPOLYLINES (основные формы деталей)
        polylines = [e for e in all_entities if e.dxftype() == 'LWPOLYLINE']
        
        print(f"\n🔍 Анализ {len(polylines)} polylines:")
        
        # Ищем sheet boundary и детали
        sheet_boundary = None
        part_polylines = []
        
        for i, polyline in enumerate(polylines):
            layer = getattr(polyline.dxf, 'layer', 'UNKNOWN')
            points = list(polyline.get_points())
            
            if not points:
                continue
                
            xs = [p[0] for p in points]
            ys = [p[1] for p in points]
            bounds = (min(xs), min(ys), max(xs), max(ys))
            width = bounds[2] - bounds[0]
            height = bounds[3] - bounds[1]
            
            print(f"  Polyline {i+1}: layer='{layer}'")
            print(f"    Точек: {len(points)}")
            print(f"    Bounds: {bounds}")
            print(f"    Размеры: {width:.1f} x {height:.1f}")
            
            # Определяем, это sheet boundary или деталь
            if 'BOUNDARY' in layer.upper() or (width > 1500 and height > 1500):
                print(f"    🔲 SHEET BOUNDARY")
                sheet_boundary = polyline
            else:
                print(f"    🧩 ДЕТАЛЬ")
                part_polylines.append((polyline, layer, bounds))
        
        if sheet_boundary:
            sheet_points = list(sheet_boundary.get_points())
            sheet_xs = [p[0] for p in sheet_points]
            sheet_ys = [p[1] for p in sheet_points] 
            sheet_bounds = (min(sheet_xs), min(sheet_ys), max(sheet_xs), max(sheet_ys))
            sheet_width = sheet_bounds[2] - sheet_bounds[0]
            sheet_height = sheet_bounds[3] - sheet_bounds[1]
            
            print(f"\n📐 Лист: {sheet_width:.0f} x {sheet_height:.0f} мм")
            print(f"   Bounds: {sheet_bounds}")
        
        print(f"\n🧩 Найдено {len(part_polylines)} деталей:")
        
        # Анализируем позиции деталей
        problems = []
        
        for i, (polyline, layer, bounds) in enumerate(part_polylines):
            x_min, y_min, x_max, y_max = bounds
            width = x_max - x_min
            height = y_max - y_min
            
            print(f"  Деталь {i+1} ({layer}):")
            print(f"    Позиция: ({x_min:.1f}, {y_min:.1f})")
            print(f"    Размеры: {width:.1f} x {height:.1f}")
            
            # Проверяем проблемы
            if x_min < -10 or y_min < -10:
                problems.append(f"Деталь {i+1} имеет отрицательные координаты: ({x_min:.1f}, {y_min:.1f})")
            
            if sheet_boundary:
                if x_max > sheet_bounds[2] + 10 or y_max > sheet_bounds[3] + 10:
                    problems.append(f"Деталь {i+1} выходит за границы листа")
            
            # Проверяем пересечения с другими деталями
            for j, (other_polyline, other_layer, other_bounds) in enumerate(part_polylines[i+1:], i+1):
                # Простая проверка пересечения bounding boxes
                if not (bounds[2] <= other_bounds[0] or bounds[0] >= other_bounds[2] or 
                       bounds[3] <= other_bounds[1] or bounds[1] >= other_bounds[3]):
                    problems.append(f"Детали {i+1} и {j+1} пересекаются по bounding box")
        
        print(f"\n⚠️ Найдено проблем: {len(problems)}")
        for problem in problems:
            print(f"  🔴 {problem}")
        
        # Создаем визуализацию DXF
        create_dxf_visualization(part_polylines, sheet_boundary)
        
        return len(problems) == 0
        
    except Exception as e:
        print(f"❌ Ошибка при чтении DXF: {e}")
        return False

def create_dxf_visualization(part_polylines, sheet_boundary):
    """Создает визуализацию содержимого DXF файла."""
    print("\n🎨 Создание визуализации DXF...")
    
    fig, ax = plt.subplots(figsize=(12, 8))
    
    # Рисуем лист (boundary)
    if sheet_boundary:
        sheet_points = list(sheet_boundary.get_points())
        sheet_coords = [(p[0], p[1]) for p in sheet_points]
        sheet_patch = MPLPolygon(sheet_coords, fill=False, edgecolor='black', linewidth=2, linestyle='--')
        ax.add_patch(sheet_patch)
    
    # Рисуем детали
    colors = ['red', 'blue', 'green', 'orange', 'purple', 'brown', 'pink', 'gray']
    
    for i, (polyline, layer, bounds) in enumerate(part_polylines):
        points = list(polyline.get_points())
        coords = [(p[0], p[1]) for p in points if len(p) >= 2]
        
        if coords:
            color = colors[i % len(colors)]
            patch = MPLPolygon(coords, alpha=0.7, facecolor=color, edgecolor='black', linewidth=1)
            ax.add_patch(patch)
            
            # Добавляем подпись
            center_x = sum(c[0] for c in coords) / len(coords)
            center_y = sum(c[1] for c in coords) / len(coords)
            ax.annotate(f"{i+1}\\n{layer[:10]}", (center_x, center_y), 
                       ha='center', va='center', fontsize=8, weight='bold')
    
    # Настраиваем оси
    ax.set_aspect('equal')
    ax.grid(True, alpha=0.3)
    ax.set_title("Содержимое DXF файла (200_140_1_black.dxf)")
    ax.set_xlabel("X (мм)")
    ax.set_ylabel("Y (мм)")
    
    # Автоматически подбираем масштаб
    all_coords = []
    if sheet_boundary:
        sheet_points = list(sheet_boundary.get_points())
        all_coords.extend([(p[0], p[1]) for p in sheet_points])
    
    for polyline, _, _ in part_polylines:
        points = list(polyline.get_points())
        all_coords.extend([(p[0], p[1]) for p in points if len(p) >= 2])
    
    if all_coords:
        xs = [c[0] for c in all_coords]
        ys = [c[1] for c in all_coords]
        margin = 50  # 50мм запас
        ax.set_xlim(min(xs) - margin, max(xs) + margin)
        ax.set_ylim(min(ys) - margin, max(ys) + margin)
    
    plt.tight_layout()
    
    # Сохраняем
    output_path = "/home/sasha/proj/2025/eva_layout/dxf_actual_content.png"
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"✅ Визуализация сохранена: {output_path}")

if __name__ == "__main__":
    print("🔍 Анализ реального DXF файла для диагностики проблемы")
    print("=" * 60)
    
    success = analyze_real_dxf_file()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ DXF файл корректен")
    else:
        print("❌ В DXF файле есть проблемы!")
    
    print("\nСравните:")
    print("  - visualization.png (ожидаемый результат)")
    print("  - dxf_actual_content.png (реальное содержимое DXF)")
    print("  - autodesk.png (как видит Autodesk Viewer)")