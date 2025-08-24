#!/usr/bin/env python3
"""Test the complete fix with real transformation parameters."""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from layout_optimizer import parse_dxf_complete, save_dxf_layout_complete, bin_packing

def test_real_fix_complete():
    """Test the complete fix with real bin_packing parameters."""
    print("🔧 Testing complete fix with real bin_packing parameters")
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
    
    original_polygon = parsed_data['combined_polygon']
    print(f"📊 Original polygon bounds: {original_polygon.bounds}")
    print(f"📊 Original polygon centroid: {original_polygon.centroid}")
    
    # Use bin_packing to get REAL transformation parameters
    polygons = [(original_polygon, os.path.basename(source_file), 'gray')]
    sheet_size = (300, 250)  # Large enough sheet
    
    print(f"\n🔄 Running bin_packing to get real parameters...")
    placed, unplaced = bin_packing(polygons, sheet_size, verbose=False)
    
    if not placed:
        print("❌ Bin packing failed")
        return
    
    real_placed = placed[0]
    real_polygon, real_x_offset, real_y_offset, real_rotation = real_placed[:4]
    
    print(f"📊 Real bin_packing result:")
    print(f"   • Transformed bounds: {real_polygon.bounds}")
    print(f"   • x_offset: {real_x_offset}")
    print(f"   • y_offset: {real_y_offset}")  
    print(f"   • rotation: {real_rotation}°")
    
    # Now use these REAL parameters for DXF saving
    placed_polygons = [
        (real_polygon, real_x_offset, real_y_offset, real_rotation, os.path.basename(source_file), 'gray')
    ]
    
    # Create original_dxf_data_map
    original_dxf_data_map = {os.path.basename(source_file): parsed_data}
    
    print(f"\n🔄 Testing save with REAL bin_packing parameters...")
    output_file = "test_real_fix_complete.dxf"
    
    save_dxf_layout_complete(
        placed_polygons,
        sheet_size,
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
        
        # Check positioning
        if output_data['combined_polygon']:
            output_bounds = output_data['combined_polygon'].bounds
            expected_bounds = real_polygon.bounds
            
            print(f"📍 Position verification:")
            print(f"   • Expected bounds: ({expected_bounds[0]:.1f}, {expected_bounds[1]:.1f}) to ({expected_bounds[2]:.1f}, {expected_bounds[3]:.1f})")
            print(f"   • Actual bounds: ({output_bounds[0]:.1f}, {output_bounds[1]:.1f}) to ({output_bounds[2]:.1f}, {output_bounds[3]:.1f})")
            
            bounds_match = all(abs(expected_bounds[i] - output_bounds[i]) < 50 for i in range(4))  # 50mm tolerance
            if bounds_match:
                print(f"✅ Position matches expected!")
            else:
                max_diff = max(abs(expected_bounds[i] - output_bounds[i]) for i in range(4))
                print(f"❌ Position mismatch (max diff: {max_diff:.1f}mm)")
    else:
        print("❌ Failed to create output")
    
    print("\n" + "=" * 50)

if __name__ == "__main__":
    test_real_fix_complete()