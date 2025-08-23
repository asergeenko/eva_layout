#!/usr/bin/env python3
"""
Проверяем исходные координаты в DXF файле - может объекты на самом деле большие?
"""

import sys
sys.path.insert(0, '.')

import ezdxf
import os

def examine_raw_dxf():
    """Проверяем сырые координаты в DXF"""
    print("🔍 АНАЛИЗ СЫРЫХ КООРДИНАТ В DXF")
    print("=" * 50)
    
    tank_file = "dxf_samples/TANK 300/1.dxf"
    if not os.path.exists(tank_file):
        print(f"❌ Файл {tank_file} не найден!")
        return
    
    try:
        doc = ezdxf.readfile(tank_file)
        modelspace = doc.modelspace()
        
        print(f"📐 HEADER ИНФОРМАЦИЯ:")
        if '$INSUNITS' in doc.header:
            units = doc.header['$INSUNITS']
            units_map = {0: 'Unitless', 1: 'Inches', 2: 'Feet', 4: 'Millimeters', 5: 'Centimeters', 6: 'Meters'}
            print(f"  Единицы измерения: {units_map.get(units, f'Unknown ({units})')}")
        
        print(f"\n📍 СЫРЫЕ КООРДИНАТЫ:")
        
        for i, entity in enumerate(modelspace):
            if i > 5:  # только первые 5 объектов
                break
                
            print(f"\n  Объект {i+1}: {entity.dxftype()}")
            
            if entity.dxftype() == 'LINE':
                start = entity.dxf.start
                end = entity.dxf.end
                print(f"    Линия: ({start.x:.3f}, {start.y:.3f}) → ({end.x:.3f}, {end.y:.3f})")
                length = ((end.x - start.x)**2 + (end.y - start.y)**2)**0.5
                print(f"    Длина: {length:.3f} единиц")
                
            elif entity.dxftype() == 'CIRCLE':
                center = entity.dxf.center
                radius = entity.dxf.radius
                print(f"    Центр: ({center.x:.3f}, {center.y:.3f})")
                print(f"    Радиус: {radius:.3f} единиц")
                print(f"    Диаметр: {radius*2:.3f} единиц")
                
            elif entity.dxftype() == 'ARC':
                center = entity.dxf.center
                radius = entity.dxf.radius
                start_angle = entity.dxf.start_angle
                end_angle = entity.dxf.end_angle
                print(f"    Центр: ({center.x:.3f}, {center.y:.3f})")
                print(f"    Радиус: {radius:.3f} единиц")
                print(f"    Углы: {start_angle:.1f}° - {end_angle:.1f}°")
                
            elif entity.dxftype() == 'LWPOLYLINE':
                points = list(entity.get_points())
                if points:
                    print(f"    Первая точка: ({points[0][0]:.3f}, {points[0][1]:.3f})")
                    print(f"    Последняя точка: ({points[-1][0]:.3f}, {points[-1][1]:.3f})")
                    print(f"    Всего точек: {len(points)}")
                    
                    # Находим габариты полилинии
                    x_coords = [p[0] for p in points]
                    y_coords = [p[1] for p in points]
                    width = max(x_coords) - min(x_coords)
                    height = max(y_coords) - min(y_coords)
                    print(f"    Габариты полилинии: {width:.3f}×{height:.3f} единиц")
                    
            elif entity.dxftype() == 'SPLINE':
                if hasattr(entity, 'control_points'):
                    control_points = entity.control_points
                    if control_points:
                        print(f"    Контрольные точки: {len(control_points)}")
                        # control_points может быть массивом numpy
                        if len(control_points) > 0:
                            first_point = control_points[0]
                            last_point = control_points[-1]
                            if hasattr(first_point, 'x'):
                                print(f"    Первая: ({first_point.x:.3f}, {first_point.y:.3f})")
                                print(f"    Последняя: ({last_point.x:.3f}, {last_point.y:.3f})")
                                x_coords = [p.x for p in control_points]
                                y_coords = [p.y for p in control_points]
                            else:
                                print(f"    Первая: ({first_point[0]:.3f}, {first_point[1]:.3f})")
                                print(f"    Последняя: ({last_point[0]:.3f}, {last_point[1]:.3f})")
                                x_coords = [p[0] for p in control_points]
                                y_coords = [p[1] for p in control_points]
                            
                            width = max(x_coords) - min(x_coords)
                            height = max(y_coords) - min(y_coords)
                            print(f"    Габариты сплайна: {width:.3f}×{height:.3f} единиц")
        
        # Общие габариты файла
        print(f"\n🗂️ ОБЩИЕ ГАБАРИТЫ ФАЙЛА:")
        all_x, all_y = [], []
        
        for entity in modelspace:
            try:
                bbox = entity.bbox()
                if bbox:
                    all_x.extend([bbox.extmin.x, bbox.extmax.x])
                    all_y.extend([bbox.extmin.y, bbox.extmax.y])
            except:
                pass
        
        if all_x and all_y:
            total_width = max(all_x) - min(all_x)
            total_height = max(all_y) - min(all_y)
            print(f"  Общая ширина: {total_width:.3f} единиц")
            print(f"  Общая высота: {total_height:.3f} единиц")
            print(f"  Минимальная X: {min(all_x):.3f}")
            print(f"  Максимальная X: {max(all_x):.3f}")
            print(f"  Минимальная Y: {min(all_y):.3f}")  
            print(f"  Максимальная Y: {max(all_y):.3f}")
            
            # Анализ единиц
            print(f"\n🤔 АНАЛИЗ ЕДИНИЦ:")
            print(f"  Если единицы = мм: {total_width:.1f}×{total_height:.1f}мм")
            print(f"  Если единицы = см: {total_width:.1f}×{total_height:.1f}см = {total_width*10:.1f}×{total_height*10:.1f}мм")
            print(f"  Если единицы = дюймы: {total_width:.1f}×{total_height:.1f}\" = {total_width*25.4:.1f}×{total_height*25.4:.1f}мм")
            
            if total_width * 25.4 > 250:  # если в дюймах больше 25см
                print(f"  💡 ВОЗМОЖНО ЕДИНИЦЫ В ДЮЙМАХ! {total_width:.2f}\" = {total_width*25.4:.1f}мм")
                
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    examine_raw_dxf()