#!/usr/bin/env python3
"""Final test of the complete fix."""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from layout_optimizer import parse_dxf_complete, save_dxf_layout_complete

def final_test_fix():
    """Test the final fix with the problematic file."""
    print("🔧 Final test of complete fix")
    print("=" * 50)
    
    source_file = "200_140_14_gray.dxf"
    if not os.path.exists(source_file):
        print(f"❌ Source file {source_file} not found")
        return
    
    print(f"📄 Processing: {source_file}")
    
    # Parse the source file
    with open(source_file, 'rb') as f:
        parsed_data = parse_dxf_complete(f, verbose=False)
    
    if not parsed_data['combined_polygon']:
        print("❌ No combined polygon found")
        return
    
    # Create a small test placement (as if from bin_packing)
    # Simulate moving the polygon from its original position to position (50, 100) on sheet
    original_bounds = parsed_data['combined_polygon'].bounds
    
    # Calculate offset needed to place bottom-left at (50, 100)
    x_offset = 50 - original_bounds[0]  # Move from original_bounds[0] to 50
    y_offset = 100 - original_bounds[1]  # Move from original_bounds[1] to 100
    
    print(f"📊 Original bounds: ({original_bounds[0]:.1f}, {original_bounds[1]:.1f}) to ({original_bounds[2]:.1f}, {original_bounds[3]:.1f})")
    print(f"📊 Applying offset: ({x_offset:.1f}, {y_offset:.1f})")
    
    # Apply transformation to polygon to get expected final position
    from shapely import affinity
    transformed_polygon = affinity.translate(parsed_data['combined_polygon'], x_offset, y_offset)
    expected_bounds = transformed_polygon.bounds
    print(f"📊 Expected final bounds: ({expected_bounds[0]:.1f}, {expected_bounds[1]:.1f}) to ({expected_bounds[2]:.1f}, {expected_bounds[3]:.1f})")
    
    # Create placed_polygons data
    placed_polygons = [
        (transformed_polygon, x_offset, y_offset, 0, os.path.basename(source_file), 'gray')
    ]
    
    # Create original_dxf_data_map
    original_dxf_data_map = {os.path.basename(source_file): parsed_data}
    
    print(f"\n🔄 Saving DXF with corrected transformation...")
    output_file = "200_140_14_gray_FIXED.dxf"
    
    save_dxf_layout_complete(
        placed_polygons,
        (300, 250),  # Large sheet
        output_file,
        original_dxf_data_map
    )
    
    if os.path.exists(output_file):
        print(f"✅ Output created: {output_file}")
        
        # Parse the output to verify
        with open(output_file, 'rb') as f:
            output_data = parse_dxf_complete(f, verbose=False)
        
        print(f"📊 Output verification:")
        print(f"   • Entities: {len(output_data['original_entities'])}")
        print(f"   • Layers: {sorted(output_data['layers'])}")
        
        # Check for artifacts
        artifact_layers = [layer for layer in output_data['layers'] 
                          if any(x in layer for x in ['POLYGON_', 'SHEET_', '_black', '_gray', '_white', '.dxf'])]
        
        if artifact_layers:
            print(f"❌ Found artifacts: {artifact_layers}")
        else:
            print(f"✅ No artifacts found!")
        
        # Check positioning accuracy
        if output_data['combined_polygon']:
            actual_bounds = output_data['combined_polygon'].bounds
            
            print(f"📍 Position accuracy check:")
            print(f"   • Expected: ({expected_bounds[0]:.1f}, {expected_bounds[1]:.1f}) to ({expected_bounds[2]:.1f}, {expected_bounds[3]:.1f})")
            print(f"   • Actual:   ({actual_bounds[0]:.1f}, {actual_bounds[1]:.1f}) to ({actual_bounds[2]:.1f}, {actual_bounds[3]:.1f})")
            
            # Calculate differences
            diffs = [abs(expected_bounds[i] - actual_bounds[i]) for i in range(4)]
            max_diff = max(diffs)
            
            if max_diff < 5:  # 5mm tolerance
                print(f"✅ Perfect positioning! (max diff: {max_diff:.1f}mm)")
            elif max_diff < 50:  # 50mm tolerance
                print(f"✅ Good positioning! (max diff: {max_diff:.1f}mm)")
            else:
                print(f"❌ Position mismatch (max diff: {max_diff:.1f}mm)")
        
        print(f"\n💾 Fixed file saved as: {output_file}")
        print(f"🔍 Please check this file in AutoCAD viewer to verify it's correct")
        
    else:
        print("❌ Failed to create output")
    
    print("\n" + "=" * 50)

if __name__ == "__main__":
    final_test_fix()