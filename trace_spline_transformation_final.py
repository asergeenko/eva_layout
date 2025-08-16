#!/usr/bin/env python3

import sys
import os
import traceback
from shapely.geometry import Polygon
import matplotlib.pyplot as plt

# Add current directory to path
sys.path.append('.')

def trace_transformation_in_save_function():
    """Trace what happens during SPLINE transformation by adding debug prints"""
    
    print("=== TRACING SPLINE TRANSFORMATION ===")
    
    # Read the layout_optimizer.py file to understand current transformation
    try:
        with open("layout_optimizer.py", "r", encoding="utf-8") as f:
            content = f.read()
        
        # Look for the save_dxf_layout_complete function
        lines = content.split('\n')
        
        in_save_function = False
        in_spline_section = False
        spline_code_lines = []
        
        for i, line in enumerate(lines):
            if "def save_dxf_layout_complete" in line:
                in_save_function = True
                print(f"Found save_dxf_layout_complete function at line {i+1}")
            
            elif in_save_function and "SPECIAL HANDLING FOR SPLINE ELEMENTS" in line:
                in_spline_section = True
                print(f"Found SPLINE special handling at line {i+1}")
            
            elif in_spline_section and line.strip().startswith("if entity_data['type'] =="):
                if "LWPOLYLINE" in line or "def " in line:
                    in_spline_section = False
                    break
            
            if in_spline_section:
                spline_code_lines.append((i+1, line))
        
        if spline_code_lines:
            print(f"\nFound {len(spline_code_lines)} lines of SPLINE transformation code")
            print("Key transformation logic:")
            
            for line_num, line in spline_code_lines[:20]:  # Show first 20 lines
                if any(keyword in line for keyword in ['scale', 'offset', 'transform', 'bounds', 'final_polygon_bounds']):
                    print(f"  Line {line_num}: {line.strip()}")
        
        # Check if there are any debug prints already
        debug_print_count = content.count('print(')
        print(f"\nCurrent debug prints in file: {debug_print_count}")
        
    except Exception as e:
        print(f"Error reading layout_optimizer.py: {e}")
    
    # Let's also check what coordinate ranges we expect vs what we're getting
    print("\n=== COORDINATE RANGE ANALYSIS ===")
    
    # Expected ranges
    sheet_width_mm = 1400  # 140cm
    sheet_height_mm = 2000  # 200cm
    
    print(f"Expected coordinate ranges:")
    print(f"  X: 0 to {sheet_width_mm} mm")
    print(f"  Y: 0 to {sheet_height_mm} mm")
    
    # The AutoDesk viewer shows coordinates around 1000-1900 range
    # This suggests the transformation is placing things way outside the sheet
    
    print(f"\nActual ranges from AutoDesk viewer:")
    print(f"  X: appears to be 1000-1900+ mm (WAY OUTSIDE SHEET)")
    print(f"  Y: appears to be 1000-1900+ mm (WAY OUTSIDE SHEET)")
    
    print(f"\nThis suggests the SPLINE transformation is:")
    print(f"  1. Not properly scaling down to sheet bounds")
    print(f"  2. Not properly translating to origin (0,0)")
    print(f"  3. Possibly using original SPLINE coordinates without polygon normalization")

def create_minimal_spline_test():
    """Create a minimal test to understand the coordinate transformation"""
    
    print("\n=== CREATING MINIMAL SPLINE TEST ===")
    
    # Let's create a simple test with known coordinates
    test_code = '''
import ezdxf
from ezdxf.math import Vec3

# Create a simple DXF with one SPLINE at known coordinates
doc = ezdxf.new('R2010')
msp = doc.modelspace()

# Create a simple SPLINE that should be at 0,0 to 100,100
control_points = [
    Vec3(0, 0, 0),
    Vec3(50, 0, 0),
    Vec3(100, 50, 0),
    Vec3(100, 100, 0)
]

spline = msp.add_spline(control_points)
spline.layer = "test_layer"

# Save it
doc.saveas("test_simple_spline.dxf")
print("Created test_simple_spline.dxf with SPLINE at 0-100 range")
'''
    
    try:
        exec(test_code)
        print("✓ Test SPLINE created successfully")
    except Exception as e:
        print(f"Error creating test SPLINE: {e}")

if __name__ == "__main__":
    trace_transformation_in_save_function()
    create_minimal_spline_test()