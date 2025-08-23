#!/usr/bin/env python3
"""
Тестируем только convert_entity_to_polygon_improved - без других функций
"""

import sys
sys.path.insert(0, '.')

import ezdxf
from layout_optimizer import convert_entity_to_polygon_improved
import os

def test_convert_entity_only():
    """Тестируем только convert_entity_to_polygon_improved"""
    print("🔍 ТЕСТ ТОЛЬКО convert_entity_to_polygon_improved")
    print("=" * 60)
    
    tank_file = "dxf_samples/TANK 300/1.dxf"
    if not os.path.exists(tank_file):
        print(f"❌ Файл {tank_file} не найден!")
        return
    
    try:
        doc = ezdxf.readfile(tank_file)
        modelspace = doc.modelspace()
        
        print(f"📋 ИСХОДНЫЕ КООРДИНАТЫ VS convert_entity_to_polygon_improved")
        
        for i, entity in enumerate(modelspace):
            if i >= 3:  # только первые 3
                break
                
            entity_type = entity.dxftype()
            print(f"\n  === ОБЪЕКТ {i+1}: {entity_type} ===")
            
            # ИСХОДНЫЕ КООРДИНАТЫ
            if entity_type == 'SPLINE':
                if hasattr(entity, 'control_points') and entity.control_points:
                    cp = entity.control_points[0]
                    if hasattr(cp, 'x'):
                        print(f"    Исходная первая контрольная точка: ({cp.x:.3f}, {cp.y:.3f})")
                    else:
                        print(f"    Исходная первая контрольная точка: ({cp[0]:.3f}, {cp[1]:.3f})")
            
            # ЧЕРЕЗ convert_entity_to_polygon_improved
            polygon = convert_entity_to_polygon_improved(entity)
            if polygon and not polygon.is_empty:
                bounds = polygon.bounds
                width = bounds[2] - bounds[0]
                height = bounds[3] - bounds[1]
                print(f"    После convert_entity_to_polygon_improved: {width:.3f}×{height:.3f}")
                print(f"    Bounds: ({bounds[0]:.3f}, {bounds[1]:.3f}, {bounds[2]:.3f}, {bounds[3]:.3f})")
                
                # Координаты первой точки полигона
                coords = list(polygon.exterior.coords)
                if coords:
                    print(f"    Первая точка полигона: ({coords[0][0]:.3f}, {coords[0][1]:.3f})")
                    
                    # ПРОВЕРЯЕМ НА МАСШТАБИРОВАНИЕ
                    if entity_type == 'SPLINE' and hasattr(entity, 'control_points'):
                        orig_cp = entity.control_points[0]
                        if hasattr(orig_cp, 'x'):
                            orig_x, orig_y = orig_cp.x, orig_cp.y
                        else:
                            orig_x, orig_y = orig_cp[0], orig_cp[1]
                        
                        poly_x, poly_y = coords[0][0], coords[0][1]
                        
                        if abs(orig_x - poly_x) > 0.001 or abs(orig_y - poly_y) > 0.001:
                            print(f"    ⚠️ КООРДИНАТЫ ИЗМЕНИЛИСЬ!")
                            print(f"      Исходные: ({orig_x:.3f}, {orig_y:.3f})")  
                            print(f"      В полигоне: ({poly_x:.3f}, {poly_y:.3f})")
                            
                            scale_x = poly_x / orig_x if orig_x != 0 else 1
                            scale_y = poly_y / orig_y if orig_y != 0 else 1
                            print(f"      Коэффициент изменения: X={scale_x:.6f}, Y={scale_y:.6f}")
                        else:
                            print(f"    ✅ Координаты сохранились")
            else:
                print(f"    ❌ convert_entity_to_polygon_improved вернул None или пустой полигон")
                
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_convert_entity_only()