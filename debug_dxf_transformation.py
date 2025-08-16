#!/usr/bin/env python3
"""
Отладка точных координат SPLINE элементов в DXF файле.
"""

import ezdxf
import os

def debug_dxf_coordinates():
    """Проверяет точные координаты SPLINE элементов."""
    print("=== ОТЛАДКА КООРДИНАТ DXF ===")
    
    dxf_path = "/home/sasha/proj/2025/eva_layout/200_140_1_black.dxf"
    
    try:
        doc = ezdxf.readfile(dxf_path)
        msp = doc.modelspace()
        
        splines = [e for e in msp if e.dxftype() == 'SPLINE']
        print(f"📊 Найдено {len(splines)} SPLINE элементов")
        
        # Анализируем координаты первых нескольких SPLINE
        for i, spline in enumerate(splines[:10]):
            layer = spline.dxf.layer
            color = getattr(spline.dxf, 'color', 256)
            
            control_points = spline.control_points
            if control_points and len(control_points) > 0:
                first_point = control_points[0]
                last_point = control_points[-1]
                
                if hasattr(first_point, 'x') and hasattr(first_point, 'y'):
                    first_x, first_y = first_point.x, first_point.y
                    last_x, last_y = last_point.x, last_point.y
                elif len(first_point) >= 2:
                    first_x, first_y = float(first_point[0]), float(first_point[1])
                    last_x, last_y = float(last_point[0]), float(last_point[1])
                else:
                    continue
                
                print(f"  SPLINE {i+1}: layer='{layer}', color={color}")
                print(f"    First point: ({first_x:.2f}, {first_y:.2f})")
                print(f"    Last point:  ({last_x:.2f}, {last_y:.2f})")
                
                # Проверяем, в каких bounds находится этот SPLINE
                all_x = []
                all_y = []
                for cp in control_points:
                    if hasattr(cp, 'x') and hasattr(cp, 'y'):
                        all_x.append(cp.x)
                        all_y.append(cp.y)
                    elif len(cp) >= 2:
                        all_x.append(float(cp[0]))
                        all_y.append(float(cp[1]))
                
                if all_x and all_y:
                    bounds = (min(all_x), min(all_y), max(all_x), max(all_y))
                    print(f"    Bounds: ({bounds[0]:.2f}, {bounds[1]:.2f}, {bounds[2]:.2f}, {bounds[3]:.2f})")
                    
                    # Проверяем, в пределах ли листа
                    in_bounds = (bounds[0] >= 0 and bounds[1] >= 0 and 
                               bounds[2] <= 2000 and bounds[3] <= 1400)
                    print(f"    В пределах листа (0-2000, 0-1400): {'✅' if in_bounds else '❌'}")
                
                print()
        
        # Проверяем boundaries листа
        lwpolylines = [e for e in msp if e.dxftype() == 'LWPOLYLINE']
        for lwpoly in lwpolylines:
            if lwpoly.dxf.layer == 'SHEET_BOUNDARY':
                points = list(lwpoly.get_points())
                if points:
                    x_coords = [p[0] for p in points]
                    y_coords = [p[1] for p in points]
                    print(f"📐 SHEET_BOUNDARY: X=({min(x_coords):.1f}-{max(x_coords):.1f}), Y=({min(y_coords):.1f}-{max(y_coords):.1f})")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

def create_minimal_test_dxf():
    """Создает минимальный тестовый DXF файл для проверки."""
    print("\\n=== СОЗДАНИЕ ТЕСТОВОГО DXF ===")
    
    # Создаем новый DXF документ
    doc = ezdxf.new('R2010')
    doc.header['$INSUNITS'] = 4  # миллиметры
    doc.header['$LUNITS'] = 2    # десятичные единицы
    
    msp = doc.modelspace()
    
    # Добавляем границы листа
    sheet_corners = [(0, 0), (2000, 0), (2000, 1400), (0, 1400), (0, 0)]
    msp.add_lwpolyline(sheet_corners, dxfattribs={"layer": "SHEET_BOUNDARY", "color": 1})
    
    # Добавляем простые тестовые элементы в известных позициях
    # Прямоугольник в левой части (как "Лодка Азимут Эверест 385")
    rect1_corners = [(50, 50), (450, 50), (450, 1350), (50, 1350), (50, 50)]
    msp.add_lwpolyline(rect1_corners, dxfattribs={"layer": "TEST_AZIMUT", "color": 250})
    
    # Прямоугольник в правой нижней части (как "Лодка АГУЛ 270")
    rect2_corners = [(700, 50), (1300, 50), (1300, 800), (700, 800), (700, 50)]
    msp.add_lwpolyline(rect2_corners, dxfattribs={"layer": "TEST_AGUL", "color": 250})
    
    # Прямоугольник в правой верхней части (как "TOYOTA COROLLA VERSO")
    rect3_corners = [(700, 850), (1300, 850), (1300, 1350), (700, 1350), (700, 850)]
    msp.add_lwpolyline(rect3_corners, dxfattribs={"layer": "TEST_TOYOTA", "color": 250})
    
    # Сохраняем тестовый файл
    test_path = "/home/sasha/proj/2025/eva_layout/test_minimal.dxf"
    doc.saveas(test_path)
    
    print(f"✅ Тестовый файл создан: {test_path}")
    print("🎯 Загрузите этот файл в AutoDesk Viewer для проверки")
    print("   Ожидаемый результат: 3 прямоугольника в позициях, соответствующих visualization.png")
    
    return test_path

if __name__ == "__main__":
    print("🔍 Отладка координат DXF файла")
    print("=" * 50)
    
    debug_dxf_coordinates()
    
    print("\\n" + "=" * 50)
    create_minimal_test_dxf()
    
    print("\\n" + "=" * 50)
    print("✅ ОТЛАДКА ЗАВЕРШЕНА")