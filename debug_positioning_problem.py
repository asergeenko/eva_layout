#!/usr/bin/env python3
"""Debug the positioning problem by reproducing the layout from visualization.png."""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from layout_optimizer import parse_dxf_complete, save_dxf_layout_complete

def debug_positioning_problem():
    """Debug positioning by manually creating correct layout."""
    print("🔧 Debugging positioning problem")
    print("=" * 60)
    
    # The visualization shows a 140×200cm (1400×2000mm) sheet
    # with elements arranged in a specific pattern
    
    # Load the source file that was used
    source_file = "dxf_samples/TANK 300/4.dxf"
    if not os.path.exists(source_file):
        print(f"❌ Source file {source_file} not found")
        return
    
    print(f"📄 Analyzing source: {source_file}")
    
    # Parse source file  
    with open(source_file, 'rb') as f:
        parsed_data = parse_dxf_complete(f, verbose=False)
    
    if not parsed_data['combined_polygon']:
        print("❌ No combined polygon found")
        return
    
    original_polygon = parsed_data['combined_polygon']
    orig_bounds = original_polygon.bounds
    print(f"📊 Original polygon bounds: {orig_bounds}")
    print(f"📊 Original size: {orig_bounds[2] - orig_bounds[0]:.1f} × {orig_bounds[3] - orig_bounds[1]:.1f}")
    
    # According to visualization.png, this element should be placed
    # in the bottom-right area of the 1400×2000mm sheet
    # Let's manually position it correctly
    
    from shapely import affinity
    
    # Target position based on visualization.png analysis:
    # The element appears to be in roughly coordinates (1200-1400, 250-650) in the visualization
    target_x = 1200  # mm from left edge
    target_y = 250   # mm from bottom edge
    
    # Calculate required offset
    x_offset = target_x - orig_bounds[0]
    y_offset = target_y - orig_bounds[1]
    
    print(f"📊 Target position: ({target_x}, {target_y})")
    print(f"📊 Required offset: ({x_offset:.1f}, {y_offset:.1f})")
    
    # Create correctly positioned polygon
    transformed_polygon = affinity.translate(original_polygon, x_offset, y_offset)
    final_bounds = transformed_polygon.bounds
    
    print(f"📊 Final polygon bounds: {final_bounds}")
    print(f"📊 Final position: X[{final_bounds[0]:.1f}, {final_bounds[2]:.1f}] Y[{final_bounds[1]:.1f}, {final_bounds[3]:.1f}]")
    
    # Create placement data with correct parameters
    placed_polygons = [
        (transformed_polygon, x_offset, y_offset, 0, "tank_part.dxf", 'gray')
    ]
    
    original_dxf_data_map = {"tank_part.dxf": parsed_data}
    
    print(f"\n🔄 Creating DXF with correct positioning...")
    output_file = "debug_correct_positioning.dxf"
    
    # Use sheet size matching visualization: 140×200cm = 1400×2000mm
    sheet_size = (1400, 2000)
    
    save_dxf_layout_complete(
        placed_polygons,
        sheet_size,
        output_file,
        original_dxf_data_map
    )
    
    if os.path.exists(output_file):
        print(f"✅ Test output created: {output_file}")
        
        # Verify the positioning
        with open(output_file, 'rb') as f:
            verify_data = parse_dxf_complete(f, verbose=False)
        
        if verify_data['combined_polygon']:
            actual_bounds = verify_data['combined_polygon'].bounds
            print(f"📊 Verification:")
            print(f"   • Expected bounds: {final_bounds}")
            print(f"   • Actual bounds: {actual_bounds}")
            
            # Check if they match
            max_diff = max(abs(final_bounds[i] - actual_bounds[i]) for i in range(4))
            if max_diff < 10:
                print(f"✅ Perfect positioning! (max diff: {max_diff:.1f}mm)")
            else:
                print(f"❌ Position mismatch (max diff: {max_diff:.1f}mm)")
                print("🔍 This indicates a bug in the save_dxf_layout_complete transformation")
        
        print(f"\n💾 Test file saved as: {output_file}")
        print(f"🔍 Check this file to see if positioning matches visualization")
        
    else:
        print("❌ Failed to create test output")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    debug_positioning_problem()