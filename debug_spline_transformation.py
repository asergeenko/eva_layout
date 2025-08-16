#!/usr/bin/env python3
"""
Отладка трансформации SPLINE элементов.
"""

import tempfile
import os
import ezdxf
import numpy as np
from layout_optimizer import parse_dxf_complete, apply_placement_transform
from shapely.geometry import Polygon

def debug_spline_transformation():
    """Отладка трансформации SPLINE элементов."""
    print("=== ОТЛАДКА ТРАНСФОРМАЦИИ SPLINE ЭЛЕМЕНТОВ ===")
    
    # Берем реальный DXF файл с SPLINE'ами
    source_dxf = "/home/sasha/proj/2025/eva_layout/200_140_1_black.dxf"
    
    print(f"📁 Читаем исходный файл: {source_dxf}")
    
    # Парсим исходный DXF
    with open(source_dxf, 'rb') as f:
        parsed_data = parse_dxf_complete(f, verbose=False)
    
    print(f"📊 Исходные данные:")
    print(f"  Combined polygon bounds: {parsed_data['combined_polygon'].bounds}")
    
    # Анализируем первые несколько SPLINE'ов
    spline_entities = [e for e in parsed_data['original_entities'] if e['type'] == 'SPLINE']
    print(f"  SPLINE'ов: {len(spline_entities)}")
    
    if len(spline_entities) > 0:
        print(f"\n🔍 Анализ первого SPLINE:")
        first_spline = spline_entities[0]
        entity = first_spline['entity']
        
        control_points = entity.control_points
        print(f"  Контрольных точек: {len(control_points)}")
        
        # Извлекаем координаты
        points = []
        for i, cp in enumerate(control_points[:5]):  # Первые 5
            if hasattr(cp, 'x') and hasattr(cp, 'y'):
                x, y = cp.x, cp.y
            elif len(cp) >= 2:
                x, y = float(cp[0]), float(cp[1])
            else:
                continue
            points.append((x, y))
            print(f"    Точка {i+1}: ({x:.2f}, {y:.2f})")
        
        if points:
            xs = [p[0] for p in points]
            ys = [p[1] for p in points]
            spline_bounds = (min(xs), min(ys), max(xs), max(ys))
            print(f"  Bounds SPLINE: {spline_bounds}")
    
    # Трансформация
    original_polygon = parsed_data['combined_polygon']
    x_offset = -1000
    y_offset = 100
    rotation_angle = 0
    
    print(f"\n🎯 Планируемая трансформация:")
    print(f"  Исходный bounds: {original_polygon.bounds}")
    print(f"  x_offset={x_offset}, y_offset={y_offset}, rotation={rotation_angle}°")
    
    # Применяем трансформацию к полигону для сравнения
    expected_polygon = apply_placement_transform(original_polygon, x_offset, y_offset, rotation_angle)
    print(f"  Ожидаемый bounds: {expected_polygon.bounds}")
    
    print(f"\n🧮 Имитация трансформации SPLINE:")
    
    if len(spline_entities) > 0:
        first_spline = spline_entities[0]
        entity = first_spline['entity']
        control_points = entity.control_points
        
        if control_points and len(control_points) > 0:
            cp = control_points[0]
            if hasattr(cp, 'x') and hasattr(cp, 'y'):
                x, y = cp.x, cp.y
            elif len(cp) >= 2:
                x, y = float(cp[0]), float(cp[1])
            else:
                return
            
            print(f"  Исходная точка: ({x:.2f}, {y:.2f})")
            
            # Применяем ту же трансформацию, что и в коде
            orig_bounds = original_polygon.bounds
            print(f"  Original bounds: {orig_bounds}")
            
            # Step 1: Normalize to origin
            x_norm = x - orig_bounds[0]
            y_norm = y - orig_bounds[1]
            print(f"  После нормализации: ({x_norm:.2f}, {y_norm:.2f})")
            
            # Step 2: Apply rotation (skip for now since rotation_angle = 0)
            
            # Step 3: Apply final position (исправленная версия)
            x_final = x_norm + x_offset
            y_final = y_norm + y_offset
            print(f"  После трансформации: ({x_final:.2f}, {y_final:.2f})")
            
            # Проверим также, что было бы со старой версией
            x_final_old = x_norm + x_offset + orig_bounds[0]
            y_final_old = y_norm + y_offset + orig_bounds[1]
            print(f"  Старая версия давала: ({x_final_old:.2f}, {y_final_old:.2f})")

if __name__ == "__main__":
    debug_spline_transformation()