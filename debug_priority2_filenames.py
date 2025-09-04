#!/usr/bin/env python3
"""
Debug script to examine priority 2 polygon filenames
"""

import sys
import os
import pandas as pd
import logging
from shapely.geometry import Polygon

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from layout_optimizer import (
    parse_dxf_complete
)

def create_real_priority2_polygons():
    """Creates REAL priority 2 polygons as in Streamlit"""
    priority2_polygons = []
    dxf_file = "dxf_samples/ДЕКА KUGOO M4 PRO JILONG/1.dxf"
    
    # Try to load real polygon
    base_polygon = None
    if os.path.exists(dxf_file):
        try:
            polygon_data = parse_dxf_complete(dxf_file)
            if polygon_data and polygon_data[0] and polygon_data[0] != 0:
                base_polygon = polygon_data[0]
                print(f"✓ Loaded real priority 2 polygon from {dxf_file}")
        except Exception as e:
            print(f"⚠️ Error loading {dxf_file}: {e}")
    
    # Fallback to synthetic polygon
    if base_polygon is None:
        base_polygon = Polygon([(0, 0), (60, 0), (60, 40), (0, 40)])
        print(f"✓ Using synthetic priority 2 polygon")
    
    # 20 black polygons priority 2
    for i in range(20):
        filename = f"ДЕКА_KUGOO_M4_PRO_JILONG_черный_{i+1}.dxf"
        priority2_polygons.append((base_polygon, filename, "чёрный", f"PRIORITY2_BLACK_{i+1}", 2))
    
    # 20 gray polygons priority 2  
    for i in range(20):
        filename = f"ДЕКА_KUGOO_M4_PRO_JILONG_серый_{i+1}.dxf"
        priority2_polygons.append((base_polygon, filename, "серый", f"PRIORITY2_GRAY_{i+1}", 2))
    
    return priority2_polygons

def analyze_priority2_filenames():
    """Analyzes priority 2 filenames to find potential conflicts"""
    
    print("=== АНАЛИЗ ИМЕН ФАЙЛОВ ПРИОРИТЕТА 2 ===")
    
    priority2_polygons = create_real_priority2_polygons()
    
    print(f"Создано {len(priority2_polygons)} полигонов приоритета 2")
    
    # Separate by color
    black_p2 = [p for p in priority2_polygons if p[2] == "чёрный"]
    gray_p2 = [p for p in priority2_polygons if p[2] == "серый"]
    
    print(f"Черных: {len(black_p2)}")
    print(f"Серых: {len(gray_p2)}")
    
    print("\nПервые 5 черных файлов:")
    for i, poly in enumerate(black_p2[:5]):
        filename = poly[1]
        order_id = poly[3]
        print(f"  {i+1}. {filename} -> {order_id}")
    
    print("\nПервые 5 серых файлов:")
    for i, poly in enumerate(gray_p2[:5]):
        filename = poly[1]
        order_id = poly[3]
        print(f"  {i+1}. {filename} -> {order_id}")
    
    # Check for filename similarities that could cause conflicts
    black_filenames = [p[1] for p in black_p2]
    gray_filenames = [p[1] for p in gray_p2]
    
    print("\nПоиск похожих имен файлов:")
    conflicts = []
    for black_name in black_filenames:
        for gray_name in gray_filenames:
            # Check if they are similar enough to be confused
            black_base = black_name.replace("черный", "").replace("_черный", "")
            gray_base = gray_name.replace("серый", "").replace("_серый", "")
            
            if black_base == gray_base:
                conflicts.append((black_name, gray_name))
                print(f"  КОНФЛИКТ: {black_name} <-> {gray_name}")
    
    if not conflicts:
        print("  Конфликтов не найдено")
    else:
        print(f"  Найдено {len(conflicts)} потенциальных конфликтов")
    
    return len(conflicts) == 0

if __name__ == "__main__":
    success = analyze_priority2_filenames()
    sys.exit(0 if success else 1)