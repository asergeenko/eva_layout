#!/usr/bin/env python3
"""
Trace the transformation flow to understand why SPLINEs are not properly positioned
"""

import ezdxf
from ezdxf.math import Vec3
import numpy as np

def analyze_original_source_files():
    """Analyze the original DXF source files to understand what should happen"""
    
    print("=== ANALYZING ORIGINAL SOURCE FILES ===")
    
    # List of source files that should be processed
    source_files = [
        "Лодка Азимут Эверест 385_2.dxf",
        "Лодка АГУЛ 270_2.dxf", 
        "TOYOTA COROLLA VERSO_2.dxf",
        "DEKA KUGOO M4 PRO JILONG_1.dxf"
    ]
    
    for filename in source_files:
        try:
            print(f"\n--- Analyzing {filename} ---")
            
            doc = ezdxf.readfile(f'/home/sasha/proj/2025/eva_layout/{filename}')
            msp = doc.modelspace()
            
            entity_counts = {}
            spline_bounds = []
            
            for entity in msp:
                entity_type = entity.dxftype()
                entity_counts[entity_type] = entity_counts.get(entity_type, 0) + 1
                
                if entity_type == 'SPLINE':
                    control_points = entity.control_points
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
                        
                        if x_coords and y_coords:
                            bounds = (min(x_coords), min(y_coords), max(x_coords), max(y_coords))
                            spline_bounds.append(bounds)
            
            print(f"   Entity counts: {entity_counts}")
            
            if spline_bounds:
                overall_bounds = (
                    min(b[0] for b in spline_bounds),
                    min(b[1] for b in spline_bounds), 
                    max(b[2] for b in spline_bounds),
                    max(b[3] for b in spline_bounds)
                )
                print(f"   SPLINE overall bounds: {overall_bounds}")
                print(f"   SPLINE bounds count: {len(spline_bounds)}")
            else:
                print("   No SPLINEs with valid control points found")
                
        except Exception as e:
            print(f"   Error reading {filename}: {e}")

def test_transformation_manually():
    """Test what the transformation should do manually"""
    
    print("\n=== TESTING TRANSFORMATION MANUALLY ===")
    
    # Simulate the transformation process
    print("1. Original SPLINE bounds (from source file): (1000, 1500, 1200, 1700)")
    print("2. Target polygon bounds (after layout): (100, 300, 500, 800)")
    
    # This is what our transformation function should calculate
    orig_bounds = (1000, 1500, 1200, 1700)
    target_bounds = (100, 300, 500, 800)
    
    orig_width = orig_bounds[2] - orig_bounds[0]  # 200
    orig_height = orig_bounds[3] - orig_bounds[1]  # 200
    target_width = target_bounds[2] - target_bounds[0]  # 400  
    target_height = target_bounds[3] - target_bounds[1]  # 500
    
    scale_x = target_width / orig_width   # 2.0
    scale_y = target_height / orig_height  # 2.5
    
    offset_x = target_bounds[0] - orig_bounds[0] * scale_x  # 100 - 1000*2.0 = -1900
    offset_y = target_bounds[1] - orig_bounds[1] * scale_y  # 300 - 1500*2.5 = -3450
    
    print(f"3. Calculated scale: ({scale_x:.2f}, {scale_y:.2f})")
    print(f"4. Calculated offset: ({offset_x:.2f}, {offset_y:.2f})")
    
    # Test transformation on corner points
    test_points = [
        (1000, 1500),  # bottom-left of original
        (1200, 1700),  # top-right of original
        (1100, 1600),  # center of original
    ]
    
    print("5. Testing transformation on sample points:")
    for x, y in test_points:
        new_x = x * scale_x + offset_x
        new_y = y * scale_y + offset_y
        print(f"   ({x}, {y}) -> ({new_x:.2f}, {new_y:.2f})")

def check_if_transformation_code_is_called():
    """Create a test script to see if our transformation code is actually being executed"""
    
    print("\n=== CREATING TEST SCRIPT TO TRACE EXECUTION ===")
    
    # Create a modified version of save_dxf_layout_complete with debug prints
    debug_code = '''
def save_dxf_layout_complete_debug(placed_polygons, original_dxf_data_map, output_filename, sheet_width=1400, sheet_height=2000):
    """Debug version with extensive logging"""
    
    print("🔍 DEBUG: save_dxf_layout_complete_debug called")
    print(f"🔍 DEBUG: placed_polygons count: {len(placed_polygons)}")
    print(f"🔍 DEBUG: original_dxf_data_map keys: {list(original_dxf_data_map.keys())}")
    print(f"🔍 DEBUG: output_filename: {output_filename}")
    
    doc = ezdxf.new(dxfversion='R2010')
    msp = doc.modelspace()
    
    # Add sheet boundary
    sheet_boundary = [(0, 0), (sheet_width, 0), (sheet_width, sheet_height), (0, sheet_height), (0, 0)]
    msp.add_lwpolyline(sheet_boundary)
    
    spline_count = 0
    transformation_count = 0
    
    for i, (transformed_polygon, original_filename, rotation_angle) in enumerate(placed_polygons):
        print(f"🔍 DEBUG: Processing polygon {i+1}: {original_filename}")
        
        if original_filename in original_dxf_data_map:
            original_data = original_dxf_data_map[original_filename]
            entities = original_data['entities']
            
            print(f"🔍 DEBUG: Found {len(entities)} entities for {original_filename}")
            
            for entity_data in entities:
                print(f"🔍 DEBUG: Processing entity type: {entity_data['type']}")
                
                if entity_data['type'] == 'SPLINE':
                    spline_count += 1
                    print(f"🔍 DEBUG: Processing SPLINE #{spline_count}")
                    
                    # Copy original SPLINE
                    new_entity = msp.add_spline()
                    
                    # Apply transformation
                    print(f"🔍 DEBUG: Applying transformation to SPLINE")
                    transformation_count += 1
                    
                    control_points = entity_data.get('control_points', [])
                    if control_points:
                        print(f"🔍 DEBUG: SPLINE has {len(control_points)} control points")
                        
                        # Simple transformation for testing
                        transformed_points = []
                        for cp in control_points:
                            if isinstance(cp, (list, tuple)) and len(cp) >= 2:
                                # Move all points to center of sheet for testing
                                new_x = 700 + (cp[0] - 1000) * 0.1  # Center X + small offset
                                new_y = 1000 + (cp[1] - 1500) * 0.1  # Center Y + small offset
                                transformed_points.append((new_x, new_y, 0))
                        
                        if transformed_points:
                            from ezdxf.math import Vec3
                            new_control_points = [Vec3(x, y, z) for x, y, z in transformed_points]
                            new_entity.control_points = new_control_points
                            print(f"🔍 DEBUG: Transformed {len(new_control_points)} control points")
    
    print(f"🔍 DEBUG: Total SPLINEs processed: {spline_count}")
    print(f"🔍 DEBUG: Total transformations applied: {transformation_count}")
    
    doc.saveas(output_filename)
    print(f"🔍 DEBUG: Saved file: {output_filename}")
'''
    
    print("Debug code created. This would help trace if transformation is being called.")

def main():
    """Main analysis routine"""
    
    print("SPLINE TRANSFORMATION FLOW TRACER")
    print("=" * 50)
    
    # Step 1: Analyze original source files
    analyze_original_source_files()
    
    # Step 2: Test transformation logic manually
    test_transformation_manually()
    
    # Step 3: Create debug version
    check_if_transformation_code_is_called()
    
    print("\n=== CONCLUSIONS ===")
    print("The SPLINEs in the output file are concentrated in a small area because:")
    print("1. Either the transformation is not being applied at all")
    print("2. Or the transformation is being applied incorrectly")
    print("3. The SPLINE bounds calculation might be wrong")
    print("4. The polygon bounds for comparison might be wrong")
    print("\nNext step: Add debug prints to layout_optimizer.py to trace execution")

if __name__ == "__main__":
    main()