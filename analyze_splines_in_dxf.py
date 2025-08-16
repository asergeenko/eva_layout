#!/usr/bin/env python3
"""
Анализ SPLINE элементов в DXF файле.
"""

import ezdxf
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MPLPolygon
import numpy as np

def analyze_splines_in_dxf():
    """Анализирует SPLINE элементы в DXF файле."""
    print("=== АНАЛИЗ SPLINE ЭЛЕМЕНТОВ ===")
    
    dxf_path = "/home/sasha/proj/2025/eva_layout/200_140_1_black.dxf"
    
    try:
        doc = ezdxf.readfile(dxf_path)
        msp = doc.modelspace()
        
        # Находим все SPLINE элементы
        splines = [e for e in msp if e.dxftype() == 'SPLINE']
        
        print(f"🔍 Найдено {len(splines)} SPLINE элементов")
        
        fig, ax = plt.subplots(figsize=(12, 8))
        
        colors = ['red', 'blue', 'green', 'orange', 'purple', 'brown', 'pink', 'gray', 'cyan', 'magenta']
        
        spline_info = []
        
        for i, spline in enumerate(splines):
            layer = getattr(spline.dxf, 'layer', 'UNKNOWN')
            
            try:
                # Получаем контрольные точки SPLINE
                control_points = spline.control_points
                
                if control_points is None or len(control_points) == 0:
                    print(f"  SPLINE {i+1}: нет контрольных точек")
                    continue
                
                # Преобразуем в координаты (контрольные точки могут быть numpy arrays)
                points = []
                for cp in control_points:
                    if hasattr(cp, 'x') and hasattr(cp, 'y'):
                        points.append((cp.x, cp.y))
                    elif len(cp) >= 2:  # numpy array or tuple
                        points.append((float(cp[0]), float(cp[1])))
                    else:
                        print(f"    Неизвестный формат точки: {cp}")
                        continue
                
                if len(points) < 2:
                    print(f"  SPLINE {i+1}: недостаточно точек ({len(points)})")
                    continue
                
                # Вычисляем bounds
                xs = [p[0] for p in points]
                ys = [p[1] for p in points]
                bounds = (min(xs), min(ys), max(xs), max(ys))
                width = bounds[2] - bounds[0]
                height = bounds[3] - bounds[1]
                
                print(f"  SPLINE {i+1}: layer='{layer}'")
                print(f"    Контрольных точек: {len(points)}")
                print(f"    Bounds: {bounds}")
                print(f"    Размеры: {width:.1f} x {height:.1f}")
                
                spline_info.append((points, layer, bounds, i+1))
                
                # Рисуем SPLINE как ломаную линию
                color = colors[i % len(colors)]
                
                # Соединяем контрольные точки
                if len(points) >= 3:
                    # Создаем полигон из точек
                    polygon = MPLPolygon(points, alpha=0.7, facecolor=color, edgecolor='black', linewidth=1)
                    ax.add_patch(polygon)
                else:
                    # Если точек мало, рисуем как линию
                    xs, ys = zip(*points)
                    ax.plot(xs, ys, color=color, linewidth=2, marker='o')
                
                # Добавляем подпись
                center_x = sum(xs) / len(xs)
                center_y = sum(ys) / len(ys)
                ax.annotate(f"S{i+1}\\n{layer[:15]}", (center_x, center_y), 
                           ha='center', va='center', fontsize=8, weight='bold')
                
            except Exception as e:
                print(f"  SPLINE {i+1}: ошибка обработки - {e}")
        
        # Добавляем sheet boundary если есть
        lwpolylines = [e for e in msp if e.dxftype() == 'LWPOLYLINE']
        for polyline in lwpolylines:
            layer = getattr(polyline.dxf, 'layer', 'UNKNOWN')
            if 'BOUNDARY' in layer.upper():
                points = list(polyline.get_points())
                if points:
                    coords = [(p[0], p[1]) for p in points]
                    boundary_patch = MPLPolygon(coords, fill=False, edgecolor='black', linewidth=2, linestyle='--')
                    ax.add_patch(boundary_patch)
        
        # Настраиваем график
        ax.set_aspect('equal')
        ax.grid(True, alpha=0.3)
        ax.set_title("SPLINE элементы в DXF файле")
        ax.set_xlabel("X (мм)")
        ax.set_ylabel("Y (мм)")
        
        # Автоматический масштаб
        if spline_info:
            all_xs = []
            all_ys = []
            for points, _, _, _ in spline_info:
                all_xs.extend([p[0] for p in points])
                all_ys.extend([p[1] for p in points])
            
            if all_xs and all_ys:
                margin = 100
                ax.set_xlim(min(all_xs) - margin, max(all_xs) + margin)
                ax.set_ylim(min(all_ys) - margin, max(all_ys) + margin)
        
        plt.tight_layout()
        
        # Сохраняем
        output_path = "/home/sasha/proj/2025/eva_layout/dxf_splines_content.png"
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        print(f"\\n✅ Визуализация SPLINE'ов сохранена: {output_path}")
        
        # Анализируем проблемы с позиционированием
        print(f"\\n🔍 Анализ позиций SPLINE'ов:")
        
        problems = []
        for i, (points, layer, bounds, spline_num) in enumerate(spline_info):
            x_min, y_min, x_max, y_max = bounds
            
            print(f"  SPLINE {spline_num} ({layer}):")
            print(f"    Позиция: ({x_min:.1f}, {y_min:.1f}) -> ({x_max:.1f}, {y_max:.1f})")
            
            # Проверяем странные позиции
            if x_min < -100 or y_min < -100:
                problems.append(f"SPLINE {spline_num} имеет очень отрицательные координаты")
            
            if x_max > 2000 or y_max > 2500:
                problems.append(f"SPLINE {spline_num} имеет очень большие координаты")
            
            # Проверяем пересечения
            for j, (other_points, other_layer, other_bounds, other_num) in enumerate(spline_info[i+1:], i+1):
                if not (bounds[2] <= other_bounds[0] or bounds[0] >= other_bounds[2] or 
                       bounds[3] <= other_bounds[1] or bounds[1] >= other_bounds[3]):
                    problems.append(f"SPLINE {spline_num} и {other_num} пересекаются")
        
        print(f"\\n⚠️ Найдено проблем: {len(problems)}")
        for problem in problems:
            print(f"  🔴 {problem}")
        
        return len(spline_info), len(problems)
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return 0, 1

if __name__ == "__main__":
    print("🔍 Анализ SPLINE элементов в DXF для диагностики")
    print("=" * 60)
    
    spline_count, problem_count = analyze_splines_in_dxf()
    
    print("\\n" + "=" * 60)
    print(f"📊 ИТОГ: {spline_count} SPLINE'ов, {problem_count} проблем")
    
    if problem_count == 0:
        print("✅ SPLINE элементы расположены корректно")
    else:
        print("❌ Найдены проблемы с позиционированием SPLINE'ов!")
    
    print("\\nСравните:")
    print("  - visualization.png (ожидаемый результат)")  
    print("  - dxf_splines_content.png (реальные SPLINE'ы в DXF)")
    print("  - autodesk.png (как видит Autodesk Viewer)")