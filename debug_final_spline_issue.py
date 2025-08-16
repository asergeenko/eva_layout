#!/usr/bin/env python3

import ezdxf
from shapely.geometry import Polygon
import matplotlib.pyplot as plt
import numpy as np

def analyze_spline_transformation_issue():
    """Final analysis of SPLINE transformation issue"""
    
    print("=== ANALYZING FINAL SPLINE TRANSFORMATION ISSUE ===")
    
    # Read the generated DXF file
    dxf_file = "200_140_1_black.dxf"
    
    try:
        doc = ezdxf.readfile(dxf_file)
        msp = doc.modelspace()
        
        # Count different entity types
        splines = []
        lwpolylines = []
        other_entities = []
        
        for entity in msp:
            if entity.dxftype() == 'SPLINE':
                splines.append(entity)
            elif entity.dxftype() == 'LWPOLYLINE':
                lwpolylines.append(entity)
            else:
                other_entities.append(entity)
        
        print(f"Found {len(splines)} SPLINE entities")
        print(f"Found {len(lwpolylines)} LWPOLYLINE entities")
        print(f"Found {len(other_entities)} other entities")
        
        # Analyze SPLINE bounds
        if splines:
            print("\n=== SPLINE ANALYSIS ===")
            
            for i, spline in enumerate(splines[:5]):  # Analyze first 5 splines
                print(f"\nSPLINE {i+1}:")
                
                # Get control points
                control_points = spline.control_points
                if control_points and len(control_points) > 0:
                    x_coords = []
                    y_coords = []
                    
                    for cp in control_points:
                        if hasattr(cp, 'x') and hasattr(cp, 'y'):
                            x_coords.append(cp.x)
                            y_coords.append(cp.y)
                        elif len(cp) >= 2:
                            x_coords.append(float(cp[0]))
                            y_coords.append(float(cp[1]))
                    
                    if x_coords and y_coords:
                        min_x, max_x = min(x_coords), max(x_coords)
                        min_y, max_y = min(y_coords), max(y_coords)
                        
                        print(f"  Control Points Bounds: X[{min_x:.1f}, {max_x:.1f}] Y[{min_y:.1f}, {max_y:.1f}]")
                        print(f"  Width: {max_x - min_x:.1f}, Height: {max_y - min_y:.1f}")
                        
                        # Check if coordinates are within expected range
                        expected_max_x = 1400  # 140cm sheet width
                        expected_max_y = 2000  # 200cm sheet height
                        
                        if max_x > expected_max_x or max_y > expected_max_y:
                            print(f"  ⚠️  COORDINATES OUT OF BOUNDS!")
                            print(f"     Expected max X: {expected_max_x}, got: {max_x:.1f}")
                            print(f"     Expected max Y: {expected_max_y}, got: {max_y:.1f}")
                
                # Check if spline has any layer info
                if hasattr(spline, 'layer'):
                    print(f"  Layer: {spline.layer}")
                
                # Check if spline has color info
                if hasattr(spline, 'color'):
                    print(f"  Color: {spline.color}")
        
        # Check overall bounds of all entities
        print("\n=== OVERALL BOUNDS ANALYSIS ===")
        
        all_x_coords = []
        all_y_coords = []
        
        # Collect all coordinates from SPLINES
        for spline in splines:
            control_points = spline.control_points
            if control_points:
                for cp in control_points:
                    if hasattr(cp, 'x') and hasattr(cp, 'y'):
                        all_x_coords.append(cp.x)
                        all_y_coords.append(cp.y)
                    elif len(cp) >= 2:
                        all_x_coords.append(float(cp[0]))
                        all_y_coords.append(float(cp[1]))
        
        # Collect all coordinates from LWPOLYLINES
        for lwpoly in lwpolylines:
            for point in lwpoly.get_points():
                all_x_coords.append(point[0])
                all_y_coords.append(point[1])
        
        if all_x_coords and all_y_coords:
            overall_min_x, overall_max_x = min(all_x_coords), max(all_x_coords)
            overall_min_y, overall_max_y = min(all_y_coords), max(all_y_coords)
            
            print(f"Overall bounds: X[{overall_min_x:.1f}, {overall_max_x:.1f}] Y[{overall_min_y:.1f}, {overall_max_y:.1f}]")
            print(f"Overall size: {overall_max_x - overall_min_x:.1f} x {overall_max_y - overall_min_y:.1f}")
            
            # Expected bounds should be within sheet size
            sheet_width = 1400  # 140cm
            sheet_height = 2000  # 200cm
            
            if overall_max_x > sheet_width or overall_max_y > sheet_height:
                print(f"⚠️  ENTITIES EXTEND BEYOND SHEET BOUNDS!")
                print(f"   Sheet size: {sheet_width} x {sheet_height}")
                print(f"   Actual size: {overall_max_x:.1f} x {overall_max_y:.1f}")
                
                # Calculate how much they exceed
                excess_x = max(0, overall_max_x - sheet_width)
                excess_y = max(0, overall_max_y - sheet_height)
                print(f"   Excess: X+{excess_x:.1f}, Y+{excess_y:.1f}")
        
        print("\n=== TRANSFORMATION VERIFICATION ===")
        
        # Read layout_optimizer.py to check current transformation logic
        try:
            with open("layout_optimizer.py", "r", encoding="utf-8") as f:
                content = f.read()
                
                # Look for SPLINE transformation section
                if "SPECIAL HANDLING FOR SPLINE ELEMENTS" in content:
                    print("✓ SPLINE special handling found in code")
                    
                    # Check if the simple linear transformation is being used
                    if "simple and reliable SPLINE transformation" in content:
                        print("✓ Simple linear transformation approach is active")
                    else:
                        print("⚠️  Complex transformation approach might still be active")
                else:
                    print("⚠️  No SPLINE special handling found in code")
        
        except Exception as e:
            print(f"Could not analyze layout_optimizer.py: {e}")
        
        return {
            'splines_count': len(splines),
            'lwpolylines_count': len(lwpolylines),
            'overall_bounds': (overall_min_x, overall_min_y, overall_max_x, overall_max_y) if all_x_coords else None,
            'sheet_size': (sheet_width, sheet_height),
            'bounds_exceeded': overall_max_x > sheet_width or overall_max_y > sheet_height if all_x_coords else False
        }
        
    except Exception as e:
        print(f"Error analyzing DXF file: {e}")
        return None

if __name__ == "__main__":
    result = analyze_spline_transformation_issue()
    print(f"\nAnalysis result: {result}")