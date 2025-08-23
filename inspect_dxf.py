#!/usr/bin/env python3

import sys
import ezdxf

test_files = [
    '/home/sasha/proj/2025/eva_layout/dxf_samples/SSANG YONG REXTON 4/1.dxf',
    '/home/sasha/proj/2025/eva_layout/dxf_samples/SSANG YONG REXTON 4/2.dxf',
    '/home/sasha/proj/2025/eva_layout/dxf_samples/VOLKSWAGEN TOUAREG 1/1.dxf',
    '/home/sasha/proj/2025/eva_layout/dxf_samples/VOLKSWAGEN TOUAREG 1/2.dxf'
]

for test_file in test_files:
    try:
        doc = ezdxf.readfile(test_file)
        msp = doc.modelspace()
        
        entity_types = {}
        lwpolyline_count = 0
        spline_count = 0
        
        for entity in msp:
            entity_type = entity.dxftype()
            entity_types[entity_type] = entity_types.get(entity_type, 0) + 1
            if entity_type == "LWPOLYLINE":
                lwpolyline_count += 1
            elif entity_type == "SPLINE":
                spline_count += 1
        
        print(f"\n{test_file}:")
        print(f"  LWPOLYLINE: {lwpolyline_count}")
        print(f"  SPLINE: {spline_count}")
        print(f"  Total entity types: {entity_types}")
        
        if lwpolyline_count > 0:
            print("  *** This file has LWPOLYLINE - good for boundary! ***")
            
    except Exception as e:
        print(f"Error reading {test_file}: {e}")