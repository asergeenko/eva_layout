#!/usr/bin/env python3
import ezdxf
import matplotlib.pyplot as plt
from shapely.geometry import Polygon
from shapely.ops import transform
import numpy as np

def check_dxf_overlaps(dxf_path):
    """Проверить наличие наложений в DXF файле."""
    
    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()
    
    # Извлечь все полигоны
    polygons = []
    carpet_names = []
    
    print(f"Анализ файла: {dxf_path}")
    print("="*50)
    
    # Группировка объектов по слоям
    layer_objects = {}
    for entity in msp:
        if hasattr(entity, 'dxf') and hasattr(entity.dxf, 'layer'):
            layer_name = entity.dxf.layer
            if layer_name != 'SHEET_BOUNDARY' and not layer_name.startswith('Defpoints'):
                if layer_name not in layer_objects:
                    layer_objects[layer_name] = []
                layer_objects[layer_name].append(entity)
    
    # Обработка каждого слоя как отдельного ковра
    for layer_name, entities in layer_objects.items():
        try:
            # Извлечь все точки из всех объектов слоя
            all_points = []
            
            for entity in entities:
                points = []
                if entity.dxftype() == 'SPLINE':
                    # Аппроксимировать сплайн полилинией
                    try:
                        spline_points = list(entity.flattening(0.1))  # Точность аппроксимации
                        points = [(p.x, p.y) for p in spline_points]
                    except:
                        # Использовать контрольные точки если flattening не работает
                        try:
                            points = [(p.x, p.y) for p in entity.control_points]
                        except:
                            continue
                elif entity.dxftype() == 'POLYLINE':
                    points = [(v.dxf.location.x, v.dxf.location.y) for v in entity.vertices]
                elif entity.dxftype() == 'LWPOLYLINE':
                    points = [(p[0], p[1]) for p in entity.get_points()]
                
                all_points.extend(points)
            
            if len(all_points) >= 3:
                # Создать выпуклую оболочку из всех точек слоя
                from shapely.geometry import MultiPoint
                if len(all_points) > 2:
                    multi_point = MultiPoint(all_points)
                    polygon = multi_point.convex_hull
                    
                    if polygon.geom_type == 'Polygon' and polygon.is_valid and polygon.area > 100:  # Минимальная площадь
                        polygons.append(polygon)
                        carpet_names.append(layer_name)
                        print(f"Найден ковер {layer_name}: площадь {polygon.area:.2f}, точек {len(all_points)}")
        
        except Exception as e:
            print(f"Ошибка при обработке {layer_name}: {e}")
    
    print(f"\nВсего найдено ковров: {len(polygons)}")
    print("\nПроверка наложений:")
    print("-"*30)
    
    overlaps = []
    for i in range(len(polygons)):
        for j in range(i + 1, len(polygons)):
            poly1, poly2 = polygons[i], polygons[j]
            name1, name2 = carpet_names[i], carpet_names[j]
            
            # Проверить пересечение (но не касание)
            if poly1.intersects(poly2) and not poly1.touches(poly2):
                intersection = poly1.intersection(poly2)
                overlap_area = intersection.area
                overlaps.append({
                    'carpet1': name1,
                    'carpet2': name2,
                    'area': overlap_area,
                    'poly1': poly1,
                    'poly2': poly2,
                    'intersection': intersection
                })
                print(f"❌ НАЛОЖЕНИЕ: {name1} ↔ {name2} (площадь: {overlap_area:.2f})")
    
    if not overlaps:
        print("✅ Наложений не обнаружено!")
    else:
        print(f"\n🚨 НАЙДЕНО {len(overlaps)} НАЛОЖЕНИЙ!")
        
        # Создать визуализацию наложений
        fig, ax = plt.subplots(figsize=(12, 8))
        
        # Нарисовать все ковры
        colors = plt.cm.Set3(np.linspace(0, 1, len(polygons)))
        for i, (poly, name) in enumerate(zip(polygons, carpet_names)):
            if poly.geom_type == 'Polygon':
                x, y = poly.exterior.xy
                ax.fill(x, y, color=colors[i], alpha=0.7, label=name)
                ax.plot(x, y, 'k-', linewidth=0.5)
                
                # Подпись по центру
                centroid = poly.centroid
                ax.text(centroid.x, centroid.y, name, ha='center', va='center', 
                       fontsize=8, fontweight='bold')
        
        # Выделить наложения красным
        for overlap in overlaps:
            if overlap['intersection'].geom_type == 'Polygon':
                x, y = overlap['intersection'].exterior.xy
                ax.fill(x, y, color='red', alpha=0.8)
                ax.plot(x, y, 'r-', linewidth=2)
        
        ax.set_aspect('equal')
        ax.grid(True, alpha=0.3)
        ax.set_title(f'Наложения ковров в {dxf_path}')
        plt.tight_layout()
        
        # Сохранить изображение
        overlap_image = dxf_path.replace('.dxf', '_overlaps.png')
        plt.savefig(overlap_image, dpi=150, bbox_inches='tight')
        print(f"Изображение с наложениями сохранено: {overlap_image}")
        
    return overlaps

if __name__ == "__main__":
    # Проверить файл 200_140_1_black.dxf
    overlaps = check_dxf_overlaps("/home/sasha/proj/2025/eva_layout/200_140_1_black.dxf")