#!/usr/bin/env python3
"""
Проверяет реальные названия слоев в DXF файле.
"""

import ezdxf

def check_layer_names():
    """Проверяет названия слоев в DXF файле."""
    print("=== ПРОВЕРКА НАЗВАНИЙ СЛОЕВ ===")
    
    dxf_path = "/home/sasha/proj/2025/eva_layout/200_140_1_black.dxf"
    
    try:
        doc = ezdxf.readfile(dxf_path)
        msp = doc.modelspace()
        
        # Собираем уникальные слои
        layers = set()
        splines = [e for e in msp if e.dxftype() == 'SPLINE']
        
        print(f"📊 Найдено {len(splines)} SPLINE элементов")
        
        for spline in splines:
            layer = spline.dxf.layer
            color = getattr(spline.dxf, 'color', 256)
            layers.add((layer, color))
        
        print(f"\\n📋 Уникальные слои (layer, color):")
        for layer, color in sorted(layers):
            count = len([s for s in splines if s.dxf.layer == layer and getattr(s.dxf, 'color', 256) == color])
            print(f"  '{layer}' color={color}: {count} splines")
        
        # Также проверим первые несколько SPLINE подробно
        print(f"\\n🔍 Детали первых 5 SPLINE:")
        for i, spline in enumerate(splines[:5]):
            layer = spline.dxf.layer
            color = getattr(spline.dxf, 'color', 256)
            
            control_points = spline.control_points
            if control_points:
                first_point = control_points[0]
                if hasattr(first_point, 'x') and hasattr(first_point, 'y'):
                    x, y = first_point.x, first_point.y
                elif len(first_point) >= 2:
                    x, y = float(first_point[0]), float(first_point[1])
                else:
                    x, y = "unknown", "unknown"
                
                print(f"  SPLINE {i+1}: layer='{layer}', color={color}, first_point=({x}, {y})")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

if __name__ == "__main__":
    check_layer_names()