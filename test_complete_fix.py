#!/usr/bin/env python3
"""Test the complete fix with clean source file."""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from layout_optimizer import parse_dxf_complete, save_dxf_layout_complete, bin_packing

def test_complete_fix():
    """Test the complete fix with clean source file."""
    print("🔧 Testing complete fix with clean source file")
    print("=" * 60)
    
    # Use clean source file
    source_file = "dxf_samples/TANK 300/4.dxf"
    if not os.path.exists(source_file):
        print(f"❌ Source file {source_file} not found")
        return
    
    print(f"📄 Processing: {source_file}")
    
    # Parse the source file
    with open(source_file, 'rb') as f:
        parsed_data = parse_dxf_complete(f, verbose=True)
    
    if not parsed_data['combined_polygon']:
        print("❌ No combined polygon found")
        return
    
    print(f"📊 Source file analysis:")
    print(f"   • Original entities: {len(parsed_data['original_entities'])}")
    print(f"   • Layers found: {sorted(parsed_data['layers'])}")
    print(f"   • Combined polygon bounds: {parsed_data['combined_polygon'].bounds}")
    
    # Check for artifacts in source
    image_entities = [e for e in parsed_data['original_entities'] if e['type'] == 'IMAGE']
    print(f"   • IMAGE entities in parsed data: {len(image_entities)}")
    
    # Use bin_packing for realistic placement
    polygons = [(parsed_data['combined_polygon'], os.path.basename(source_file), 'black')]
    sheet_size = (300, 250)
    
    print(f"\n🔄 Running bin_packing...")
    placed, unplaced = bin_packing(polygons, sheet_size, verbose=True)
    
    if not placed:
        print("❌ Bin packing failed")
        return
    
    real_placed = placed[0]
    real_polygon, real_x_offset, real_y_offset, real_rotation = real_placed[:4]
    
    print(f"📊 Bin packing result:")
    print(f"   • Final bounds: {real_polygon.bounds}")
    print(f"   • Transformation: offset=({real_x_offset:.1f}, {real_y_offset:.1f}), rotation={real_rotation}°")
    
    # Create placement data
    placed_polygons = [
        (real_polygon, real_x_offset, real_y_offset, real_rotation, os.path.basename(source_file), 'black')
    ]
    
    original_dxf_data_map = {os.path.basename(source_file): parsed_data}
    
    print(f"\n🔄 Saving DXF with complete fix...")
    output_file = "test_complete_fix.dxf"
    
    save_dxf_layout_complete(
        placed_polygons,
        sheet_size,
        output_file,
        original_dxf_data_map
    )
    
    if os.path.exists(output_file):
        print(f"✅ Output created: {output_file}")
        
        # Verify output
        with open(output_file, 'rb') as f:
            output_data = parse_dxf_complete(f, verbose=False)
        
        print(f"📊 Output verification:")
        print(f"   • Entities: {len(output_data['original_entities'])}")
        print(f"   • Layers: {sorted(output_data['layers'])}")
        
        # Check for IMAGE artifacts
        output_images = [e for e in output_data['original_entities'] if e['type'] == 'IMAGE']
        if output_images:
            print(f"❌ Found {len(output_images)} IMAGE artifacts in output!")
        else:
            print(f"✅ No IMAGE artifacts in output!")
        
        # Check layer artifacts
        artifact_layers = [layer for layer in output_data['layers'] 
                          if any(x in layer for x in ['POLYGON_', 'SHEET_', '_black', '_gray', '_white', '.dxf'])]
        
        if artifact_layers:
            print(f"❌ Found layer artifacts: {artifact_layers}")
        else:
            print(f"✅ No layer artifacts!")
        
        # Position verification
        if output_data['combined_polygon']:
            output_bounds = output_data['combined_polygon'].bounds
            expected_bounds = real_polygon.bounds
            
            print(f"📍 Position check:")
            print(f"   • Expected: ({expected_bounds[0]:.1f}, {expected_bounds[1]:.1f}) to ({expected_bounds[2]:.1f}, {expected_bounds[3]:.1f})")
            print(f"   • Actual:   ({output_bounds[0]:.1f}, {output_bounds[1]:.1f}) to ({output_bounds[2]:.1f}, {output_bounds[3]:.1f})")
            
            max_diff = max(abs(expected_bounds[i] - output_bounds[i]) for i in range(4))
            if max_diff < 5:
                print(f"✅ Perfect positioning! (max diff: {max_diff:.1f}mm)")
            else:
                print(f"❌ Position mismatch (max diff: {max_diff:.1f}mm)")
        
        print(f"\n💾 Test file saved as: {output_file}")
        print(f"🔍 Compare this with the visualization to verify correctness")
    else:
        print("❌ Failed to create output")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    test_complete_fix()