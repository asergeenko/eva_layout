#!/usr/bin/env python3
"""
Comprehensive diagnostic script to analyze SPLINE transformation issue
in the actual output file 200_140_1_black.dxf
"""

import ezdxf
import numpy as np
from shapely.geometry import Polygon
import matplotlib.pyplot as plt
import matplotlib.patches as patches

def analyze_actual_output():
    """Analyze the actual 200_140_1_black.dxf file"""
    
    print("=== ANALYZING ACTUAL OUTPUT FILE ===")
    
    try:
        doc = ezdxf.readfile('/home/sasha/proj/2025/eva_layout/200_140_1_black.dxf')
        msp = doc.modelspace()
        
        # Count different entity types
        entity_counts = {}
        splines = []
        lwpolylines = []
        
        for entity in msp:
            entity_type = entity.dxftype()
            entity_counts[entity_type] = entity_counts.get(entity_type, 0) + 1
            
            if entity_type == 'SPLINE':
                splines.append(entity)
            elif entity_type == 'LWPOLYLINE':
                lwpolylines.append(entity)
        
        print(f"Entity counts: {entity_counts}")
        print(f"Found {len(splines)} SPLINE entities")
        print(f"Found {len(lwpolylines)} LWPOLYLINE entities")
        
        # Analyze SPLINE positions
        if splines:
            print("\n=== SPLINE ANALYSIS ===")
            for i, spline in enumerate(splines[:5]):  # Analyze first 5 splines
                print(f"\nSPLINE {i+1}:")
                
                # Get control points
                control_points = spline.control_points
                if control_points is not None and len(control_points) > 0:
                    x_coords = []
                    y_coords = []
                    for cp in control_points:
                        if hasattr(cp, 'x') and hasattr(cp, 'y'):
                            x_coords.append(cp.x)
                            y_coords.append(cp.y)
                        elif len(cp) >= 2:
                            x_coords.append(float(cp[0]))
                            y_coords.append(float(cp[1]))
                    
                    print(f"  Control points count: {len(control_points)}")
                    print(f"  X range: {min(x_coords):.2f} to {max(x_coords):.2f}")
                    print(f"  Y range: {min(y_coords):.2f} to {max(y_coords):.2f}")
                    print(f"  Sample points: {[(x_coords[j], y_coords[j]) for j in range(min(3, len(x_coords)))]}")
                
                # Check if SPLINE has been transformed
                if x_coords and y_coords:
                    if x_coords[0] > 1000 or y_coords[0] > 1000:
                        print(f"  WARNING: SPLINE appears to be in wrong coordinate system!")
                        print(f"  First point: ({x_coords[0]:.2f}, {y_coords[0]:.2f})")
        
        # Analyze LWPOLYLINE positions if any
        if lwpolylines:
            print("\n=== LWPOLYLINE ANALYSIS ===")
            for i, poly in enumerate(lwpolylines[:3]):
                print(f"\nLWPOLYLINE {i+1}:")
                
                points = list(poly.get_points())
                if points:
                    x_coords = [p[0] for p in points]
                    y_coords = [p[1] for p in points]
                    
                    print(f"  Points count: {len(points)}")
                    print(f"  X range: {min(x_coords):.2f} to {max(x_coords):.2f}")
                    print(f"  Y range: {min(y_coords):.2f} to {max(y_coords):.2f}")
        
        return splines, lwpolylines
        
    except Exception as e:
        print(f"Error reading DXF file: {e}")
        return [], []

def compare_with_visualization_bounds():
    """Compare expected bounds from visualization with actual DXF"""
    
    print("\n=== COMPARING WITH EXPECTED LAYOUT ===")
    
    # From visualization.png, we can see the layout should be:
    # - Sheet size: 1400mm x 2000mm (140cm x 200cm)
    # - Parts positioned from 0 to ~1400 in X, 0 to ~2000 in Y
    expected_bounds = {
        'sheet_width': 1400,
        'sheet_height': 2000,
        'x_min': 0,
        'x_max': 1400,
        'y_min': 0,
        'y_max': 2000
    }
    
    print(f"Expected layout bounds:")
    print(f"  X: {expected_bounds['x_min']} to {expected_bounds['x_max']}")
    print(f"  Y: {expected_bounds['y_min']} to {expected_bounds['y_max']}")
    
    return expected_bounds

def check_transformation_function():
    """Check what our transformation function should do vs what it actually does"""
    
    print("\n=== CHECKING TRANSFORMATION LOGIC ===")
    
    # Test case: simulate what happens to a SPLINE
    # Let's say we have a SPLINE with bounds (1000, 1500, 1200, 1700)
    # And it should be placed at (100, 200, 300, 400) after transformation
    
    orig_spline_bounds = (1000, 1500, 1200, 1700)  # min_x, min_y, max_x, max_y
    final_polygon_bounds = (100, 200, 300, 400)    # where it should be
    
    print(f"Test transformation:")
    print(f"  Original SPLINE bounds: {orig_spline_bounds}")
    print(f"  Target polygon bounds: {final_polygon_bounds}")
    
    # Calculate what our transformation should do
    orig_width = orig_spline_bounds[2] - orig_spline_bounds[0]
    orig_height = orig_spline_bounds[3] - orig_spline_bounds[1]
    final_width = final_polygon_bounds[2] - final_polygon_bounds[0]
    final_height = final_polygon_bounds[3] - final_polygon_bounds[1]
    
    scale_x = final_width / orig_width if orig_width > 0 else 1.0
    scale_y = final_height / orig_height if orig_height > 0 else 1.0
    
    offset_x = final_polygon_bounds[0] - orig_spline_bounds[0] * scale_x
    offset_y = final_polygon_bounds[1] - orig_spline_bounds[1] * scale_y
    
    print(f"  Calculated scale: ({scale_x:.4f}, {scale_y:.4f})")
    print(f"  Calculated offset: ({offset_x:.2f}, {offset_y:.2f})")
    
    # Test transformation on a sample point
    test_point = (1100, 1600)  # Point within original bounds
    transformed_x = test_point[0] * scale_x + offset_x
    transformed_y = test_point[1] * scale_y + offset_y
    
    print(f"  Test point {test_point} -> ({transformed_x:.2f}, {transformed_y:.2f})")
    
    # Check if the transformed point is within target bounds
    within_target = (final_polygon_bounds[0] <= transformed_x <= final_polygon_bounds[2] and
                    final_polygon_bounds[1] <= transformed_y <= final_polygon_bounds[3])
    print(f"  Point within target bounds: {within_target}")

def create_visual_comparison():
    """Create a visual comparison of what we see vs what should be"""
    
    print("\n=== CREATING VISUAL COMPARISON ===")
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 8))
    
    # Left plot: What we expect (from visualization.png)
    ax1.set_title("Expected Layout (from visualization.png)")
    ax1.set_xlim(0, 1400)
    ax1.set_ylim(0, 2000)
    ax1.set_aspect('equal')
    
    # Approximate positions from visualization
    expected_parts = [
        {'name': 'AZIMUT EVEREST 385', 'bounds': (50, 400, 450, 1800), 'color': 'lightcoral'},
        {'name': 'AGUL 270', 'bounds': (500, 0, 1000, 1250), 'color': 'orange'},
        {'name': 'TOYOTA COROLLA VERSO', 'bounds': (800, 1250, 1350, 2000), 'color': 'lightblue'},
        {'name': 'DEKA KUGOO M4 PRO', 'bounds': (50, 1800, 450, 1950), 'color': 'plum'},
    ]
    
    for part in expected_parts:
        rect = patches.Rectangle(
            (part['bounds'][0], part['bounds'][1]),
            part['bounds'][2] - part['bounds'][0],
            part['bounds'][3] - part['bounds'][1],
            linewidth=2, edgecolor='black', facecolor=part['color'], alpha=0.7
        )
        ax1.add_patch(rect)
        ax1.text(
            (part['bounds'][0] + part['bounds'][2]) / 2,
            (part['bounds'][1] + part['bounds'][3]) / 2,
            part['name'], ha='center', va='center', fontsize=8
        )
    
    # Right plot: What we actually get (from DXF analysis)
    ax2.set_title("Actual DXF Output (from AutoDesk Viewer)")
    ax2.set_xlim(0, 1400)
    ax2.set_ylim(0, 2000)
    ax2.set_aspect('equal')
    
    # Try to read and plot actual DXF content
    try:
        doc = ezdxf.readfile('/home/sasha/proj/2025/eva_layout/200_140_1_black.dxf')
        msp = doc.modelspace()
        
        for entity in msp:
            if entity.dxftype() == 'SPLINE':
                control_points = entity.control_points
                if control_points and len(control_points) > 0:
                    x_coords = [cp.x for cp in control_points]
                    y_coords = [cp.y for cp in control_points]
                    
                    # Only plot if coordinates are reasonable (within expected range)
                    if all(0 <= x <= 2000 for x in x_coords) and all(0 <= y <= 2000 for y in y_coords):
                        ax2.plot(x_coords, y_coords, 'r-', linewidth=1, alpha=0.7)
                    else:
                        # Plot scaled down if coordinates are too large
                        scale_factor = 0.1 if max(max(x_coords), max(y_coords)) > 10000 else 1.0
                        scaled_x = [x * scale_factor for x in x_coords]
                        scaled_y = [y * scale_factor for y in y_coords]
                        ax2.plot(scaled_x, scaled_y, 'b-', linewidth=1, alpha=0.7, 
                               label=f'Scaled by {scale_factor}')
    except Exception as e:
        ax2.text(700, 1000, f"Error reading DXF: {str(e)}", ha='center', va='center')
    
    ax1.grid(True, alpha=0.3)
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('/home/sasha/proj/2025/eva_layout/diagnostic_comparison.png', dpi=150, bbox_inches='tight')
    print("Saved diagnostic comparison to: diagnostic_comparison.png")

def main():
    """Main diagnostic routine"""
    
    print("COMPREHENSIVE SPLINE TRANSFORMATION DIAGNOSTIC")
    print("=" * 50)
    
    # Step 1: Analyze actual output file
    splines, lwpolylines = analyze_actual_output()
    
    # Step 2: Compare with expected bounds
    expected_bounds = compare_with_visualization_bounds()
    
    # Step 3: Check transformation logic
    check_transformation_function()
    
    # Step 4: Create visual comparison
    create_visual_comparison()
    
    print("\n=== SUMMARY AND RECOMMENDATIONS ===")
    
    if splines:
        # Check if SPLINEs are in wrong coordinate system
        sample_spline = splines[0]
        control_points = sample_spline.control_points
        if control_points is not None and len(control_points) > 0:
            # Handle different control point formats
            first_x, first_y = None, None
            first_cp = control_points[0]
            
            if hasattr(first_cp, 'x') and hasattr(first_cp, 'y'):
                first_x, first_y = first_cp.x, first_cp.y
            elif len(first_cp) >= 2:
                first_x, first_y = float(first_cp[0]), float(first_cp[1])
            
            if first_x is not None and first_y is not None:
                if first_x > 2000 or first_y > 2000:
                    print("❌ PROBLEM IDENTIFIED: SPLINEs are in wrong coordinate system")
                    print(f"   First SPLINE point: ({first_x:.2f}, {first_y:.2f})")
                    print("   Expected range: 0-1400 for X, 0-2000 for Y")
                    print("\n🔧 RECOMMENDED FIX:")
                    print("   1. The SPLINE transformation is not being applied correctly")
                    print("   2. Check if save_dxf_layout_complete() is being called")
                    print("   3. Verify that SPLINE transformation code is actually executing")
                    print("   4. Add debug prints to trace transformation flow")
                else:
                    print("✅ SPLINEs appear to be in correct coordinate system")
                    print("   Need to investigate other causes of positioning issues")
    else:
        print("ℹ️  No SPLINEs found in output file")
    
    print(f"\nFor detailed analysis, check: diagnostic_comparison.png")

if __name__ == "__main__":
    main()