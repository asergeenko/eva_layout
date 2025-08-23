#!/usr/bin/env python3

import sys
import os
sys.path.append('/home/sasha/proj/2025/eva_layout')

def calculate_entities_centroid(original_entities):
    """Вычисляем центроид всех DXF элементов по их control points"""
    all_points = []
    
    for entity_data in original_entities:
        entity = entity_data['entity']
        entity_type = entity_data['type']
        
        if entity_type == 'SPLINE':
            if hasattr(entity, 'control_points') and entity.control_points:
                for cp in entity.control_points:
                    if hasattr(cp, 'x') and hasattr(cp, 'y'):
                        all_points.append((cp.x, cp.y))
                    elif len(cp) >= 2:
                        all_points.append((float(cp[0]), float(cp[1])))
        
        elif entity_type == 'LWPOLYLINE':
            try:
                points = list(entity.get_points())
                for p in points:
                    all_points.append((p[0], p[1]))
            except:
                pass
                
        elif entity_type == 'CIRCLE':
            if hasattr(entity.dxf, 'center'):
                center = entity.dxf.center
                all_points.append((center[0], center[1]))
        
        # Добавим поддержку других типов по необходимости
    
    if not all_points:
        return 0, 0
        
    center_x = sum(p[0] for p in all_points) / len(all_points)
    center_y = sum(p[1] for p in all_points) / len(all_points)
    
    return center_x, center_y

# Теперь нужно создать патч для save_dxf_layout_complete
patch_code = '''
# ИСПРАВЛЕНИЕ ТРАНСФОРМАЦИИ SPLINE
# Вместо использования центра polygon, используем центроид всех DXF элементов

# В начале функции save_dxf_layout_complete, после получения original_data:
if original_data['original_entities']:
    # Вычисляем центроид всех оригинальных элементов
    entities_center_x, entities_center_y = calculate_entities_centroid(original_data['original_entities'])
    
    for j, entity_data in enumerate(original_data['original_entities']):
        # ... существующий код ...
        
        # ЗАМЕНИТЬ БЛОК ТРАНСФОРМАЦИИ SPLINE:
        if entity_data['type'] == 'SPLINE':
            # Используем entities_center вместо orig_center из polygon bounds
            if hasattr(new_entity, 'control_points') and new_entity.control_points:
                from ezdxf.math import Vec3
                new_control_points = []
                for cp in new_entity.control_points:
                    if hasattr(cp, 'x') and hasattr(cp, 'y'):
                        x, y = cp.x, cp.y
                        z = getattr(cp, 'z', 0.0)
                    elif len(cp) >= 2:
                        x, y = float(cp[0]), float(cp[1])
                        z = float(cp[2]) if len(cp) > 2 else 0.0
                    else:
                        continue
                    
                    # Поворот относительно entities_center (не polygon center!)
                    if rotation_angle != 0:
                        import math
                        angle_rad = math.radians(rotation_angle)
                        cos_angle = math.cos(angle_rad)
                        sin_angle = math.sin(angle_rad)
                        
                        dx = x - entities_center_x
                        dy = y - entities_center_y
                        
                        rotated_x = dx * cos_angle - dy * sin_angle + entities_center_x
                        rotated_y = dx * sin_angle + dy * cos_angle + entities_center_y
                        
                        final_x = rotated_x + translate_x
                        final_y = rotated_y + translate_y
                    else:
                        final_x = x + translate_x
                        final_y = y + translate_y
                    
                    new_control_points.append(Vec3(final_x, final_y, z))
                
                new_entity.control_points = new_control_points
'''

print("=== ПАТЧ ДЛЯ ИСПРАВЛЕНИЯ НАЛОЖЕНИЙ ===")
print("Нужно применить следующие изменения к layout_optimizer.py:")
print("1. Добавить функцию calculate_entities_centroid()")
print("2. Заменить логику трансформации SPLINE в save_dxf_layout_complete")
print("3. Использовать центроид DXF элементов вместо центра polygon")
print("\nЭто исправит проблему наложений, так как SPLINE будут трансформироваться")
print("относительно того же центра, что и использовался при создании polygon boundaries.")

if __name__ == "__main__":
    pass