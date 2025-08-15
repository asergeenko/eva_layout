#!/usr/bin/env python3
import ezdxf

def debug_splines(dxf_path):
    """Отладка извлечения точек из сплайнов."""
    
    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()
    
    print(f"Отладка извлечения точек из: {dxf_path}")
    print("="*60)
    
    spline_count = 0
    for entity in msp:
        if entity.dxftype() == 'SPLINE':
            spline_count += 1
            layer_name = entity.dxf.layer
            
            print(f"\nСплайн #{spline_count} на слое '{layer_name}':")
            
            # Метод 1: flattening
            try:
                points = list(entity.flattening(0.1))
                print(f"  flattening: {len(points)} точек")
                if points:
                    print(f"    первая: ({points[0].x:.2f}, {points[0].y:.2f})")
                    print(f"    последняя: ({points[-1].x:.2f}, {points[-1].y:.2f})")
            except Exception as e:
                print(f"  flattening ошибка: {e}")
            
            # Метод 2: control_points
            try:
                control_points = entity.control_points
                print(f"  control_points: {len(control_points)} точек")
                if control_points:
                    print(f"    первая: ({control_points[0].x:.2f}, {control_points[0].y:.2f})")
                    print(f"    последняя: ({control_points[-1].x:.2f}, {control_points[-1].y:.2f})")
            except Exception as e:
                print(f"  control_points ошибка: {e}")
            
            # Метод 3: knots
            try:
                knots = entity.knots
                print(f"  knots: {len(knots)} значений")
            except Exception as e:
                print(f"  knots ошибка: {e}")
            
            if spline_count > 5:  # Ограничить вывод
                break
    
    print(f"\nВсего сплайнов: {spline_count}")

if __name__ == "__main__":
    debug_splines("/home/sasha/proj/2025/eva_layout/200_140_1_black.dxf")