#!/usr/bin/env python3
"""
Глубокий анализ текущего DXF файла для понимания проблемы.
"""

import ezdxf
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MPLPolygon
import numpy as np

def analyze_current_dxf():
    """Анализирует текущий DXF файл детально."""
    print("=== ГЛУБОКИЙ АНАЛИЗ ТЕКУЩЕГО DXF ФАЙЛА ===")
    
    dxf_path = "/home/sasha/proj/2025/eva_layout/200_140_1_black.dxf"
    
    try:
        doc = ezdxf.readfile(dxf_path)
        msp = doc.modelspace()
        
        entities = list(msp)
        print(f"📊 Всего элементов: {len(entities)}")
        
        # Группируем по типам
        entity_types = {}
        for entity in entities:
            etype = entity.dxftype()
            if etype not in entity_types:
                entity_types[etype] = []
            entity_types[etype].append(entity)
        
        for etype, elist in entity_types.items():
            print(f"  {etype}: {len(elist)}")
        
        # Анализируем SPLINE элементы детально
        splines = entity_types.get('SPLINE', [])
        print(f"\n🔍 Анализ {len(splines)} SPLINE элементов:")
        
        # Группируем SPLINE по слоям или близости
        spline_groups = {}
        
        for i, spline in enumerate(splines):
            layer = spline.dxf.layer
            color = getattr(spline.dxf, 'color', 'default')
            
            # Получаем контрольные точки
            control_points = spline.control_points
            if control_points and len(control_points) > 0:
                first_point = control_points[0]
                if hasattr(first_point, 'x') and hasattr(first_point, 'y'):
                    x, y = first_point.x, first_point.y
                elif len(first_point) >= 2:
                    x, y = float(first_point[0]), float(first_point[1])
                else:
                    continue
                
                group_key = f"Layer_{layer}_Color_{color}"
                if group_key not in spline_groups:
                    spline_groups[group_key] = []
                
                spline_groups[group_key].append({
                    'index': i,
                    'spline': spline,
                    'first_point': (x, y),
                    'num_points': len(control_points)
                })
        
        print(f"\n📋 Найдено {len(spline_groups)} групп SPLINE:")
        for group_name, group_splines in spline_groups.items():
            print(f"  {group_name}: {len(group_splines)} splines")
            
            # Находим bounds этой группы
            all_x = []
            all_y = []
            
            for spline_info in group_splines:
                spline = spline_info['spline']
                control_points = spline.control_points
                
                for cp in control_points:
                    if hasattr(cp, 'x') and hasattr(cp, 'y'):
                        all_x.append(cp.x)
                        all_y.append(cp.y)
                    elif len(cp) >= 2:
                        all_x.append(float(cp[0]))
                        all_y.append(float(cp[1]))
            
            if all_x and all_y:
                bounds = (min(all_x), min(all_y), max(all_x), max(all_y))
                width = bounds[2] - bounds[0]
                height = bounds[3] - bounds[1]
                print(f"    Bounds: {bounds}")
                print(f"    Size: {width:.1f} x {height:.1f}")
                
                # Проверяем, находится ли группа в пределах листа (2000x1400)
                in_bounds = (bounds[0] >= -50 and bounds[1] >= -50 and 
                           bounds[2] <= 2050 and bounds[3] <= 1450)
                print(f"    В пределах листа: {'✅' if in_bounds else '❌'}")
        
        # Проверяем LWPOLYLINE (границы листа)
        lwpolylines = entity_types.get('LWPOLYLINE', [])
        print(f"\n📐 Анализ {len(lwpolylines)} LWPOLYLINE:")
        
        for i, lwpoly in enumerate(lwpolylines):
            layer = lwpoly.dxf.layer
            points = list(lwpoly.get_points())
            print(f"  LWPOLYLINE {i+1}: layer='{layer}', точек={len(points)}")
            
            if points:
                x_coords = [p[0] for p in points]
                y_coords = [p[1] for p in points]
                bounds = (min(x_coords), min(y_coords), max(x_coords), max(y_coords))
                print(f"    Bounds: {bounds}")
        
        # Создаем визуализацию
        fig, ax = plt.subplots(1, 1, figsize=(12, 8))
        
        # Цвета для разных групп
        colors = ['red', 'blue', 'green', 'orange', 'purple', 'brown', 'pink', 'gray']
        
        # Отображаем SPLINE группы
        for i, (group_name, group_splines) in enumerate(spline_groups.items()):
            color = colors[i % len(colors)]
            
            for spline_info in group_splines:
                spline = spline_info['spline']
                control_points = spline.control_points
                
                x_coords = []
                y_coords = []
                
                for cp in control_points:
                    if hasattr(cp, 'x') and hasattr(cp, 'y'):
                        x_coords.append(cp.x)
                        y_coords.append(cp.y)
                    elif len(cp) >= 2:
                        x_coords.append(float(cp[0]))
                        y_coords.append(float(cp[1]))
                
                if x_coords and y_coords:
                    ax.plot(x_coords, y_coords, color=color, linewidth=1, alpha=0.7)
        
        # Отображаем LWPOLYLINE
        for lwpoly in lwpolylines:
            points = list(lwpoly.get_points())
            if len(points) > 0:
                x_coords = [p[0] for p in points]
                y_coords = [p[1] for p in points]
                
                if lwpoly.dxf.layer == 'SHEET_BOUNDARY' or 'boundary' in lwpoly.dxf.layer.lower():
                    ax.plot(x_coords, y_coords, 'k--', linewidth=2, label='Sheet boundary')
                else:
                    ax.plot(x_coords, y_coords, 'black', linewidth=1)
        
        ax.set_xlim(-100, 2100)
        ax.set_ylim(-100, 1500)
        ax.set_xlabel('X (мм)')
        ax.set_ylabel('Y (мм)')
        ax.set_title('Содержимое DXF файла (200_140_1_black.dxf)')
        ax.grid(True, alpha=0.3)
        ax.legend()
        
        # Добавляем легенду для групп
        legend_text = []
        for i, group_name in enumerate(spline_groups.keys()):
            color = colors[i % len(colors)]
            legend_text.append(f"{group_name}")
        
        if legend_text:
            ax.text(0.02, 0.98, '\\n'.join(legend_text), transform=ax.transAxes, 
                   verticalalignment='top', fontsize=8, bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
        
        plt.tight_layout()
        plt.savefig('/home/sasha/proj/2025/eva_layout/current_dxf_detailed_analysis.png', dpi=150, bbox_inches='tight')
        plt.close()
        
        print(f"\\n✅ Детальная визуализация сохранена: current_dxf_detailed_analysis.png")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка анализа: {e}")
        return False

if __name__ == "__main__":
    print("🔍 Детальный анализ текущего DXF файла")
    print("=" * 50)
    
    success = analyze_current_dxf()
    
    print("\\n" + "=" * 50)
    if success:
        print("✅ АНАЛИЗ ЗАВЕРШЕН")
    else:
        print("❌ АНАЛИЗ НЕУДАЧЕН")