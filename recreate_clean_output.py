#!/usr/bin/env python3
"""Recreate the 200_140_14_gray.dxf file with the fixed code."""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from layout_optimizer import parse_dxf_complete, save_dxf_layout_complete, bin_packing

def recreate_clean_output():
    """Recreate clean output matching the visualization."""
    print("🔧 Recreating 200_140_14_gray.dxf with fixed code")
    print("=" * 60)
    
    # Find the source that was used for 200_140_14_gray.dxf
    # Looking at the pattern, it's likely from TANK 300 samples
    possible_sources = [
        "dxf_samples/TANK 300/4.dxf",
        "dxf_samples/TANK 300/3.dxf", 
        "dxf_samples/TANK 300/2.dxf",
        "dxf_samples/TANK 300/1.dxf"
    ]
    
    source_file = None
    for candidate in possible_sources:
        if os.path.exists(candidate):
            source_file = candidate
            break
    
    if not source_file:
        print("❌ No source file found")
        return
    
    print(f"📄 Using source: {source_file}")
    
    # Parse source file  
    with open(source_file, 'rb') as f:
        parsed_data = parse_dxf_complete(f, verbose=False)
    
    if not parsed_data['combined_polygon']:
        print("❌ No combined polygon found")
        return
    
    original_polygon = parsed_data['combined_polygon']
    print(f"📊 Source polygon bounds: {original_polygon.bounds}")
    
    # Use bin_packing with sheet size matching the layout (200x140)
    polygons = [(original_polygon, "tank_part.dxf", 'gray')]
    sheet_size = (200, 140)  # Match the intended layout size
    
    print(f"🔄 Running bin_packing with sheet size {sheet_size}...")
    placed, unplaced = bin_packing(polygons, sheet_size, verbose=True)
    
    if not placed:
        print("❌ Bin packing failed - trying larger sheet")
        sheet_size = (300, 250)
        placed, unplaced = bin_packing(polygons, sheet_size, verbose=False)
        
    if not placed:
        print("❌ Bin packing still failed")
        return
    
    real_placed = placed[0]
    transformed_polygon, x_offset, y_offset, rotation = real_placed[:4]
    
    print(f"📊 Placement result:")
    print(f"   • Sheet size: {sheet_size}")
    print(f"   • Final bounds: {transformed_polygon.bounds}")
    print(f"   • Offset: ({x_offset:.1f}, {y_offset:.1f})")
    print(f"   • Rotation: {rotation}°")
    
    # Create placement data
    placed_polygons = [
        (transformed_polygon, x_offset, y_offset, rotation, "tank_part.dxf", 'gray')
    ]
    
    original_dxf_data_map = {"tank_part.dxf": parsed_data}
    
    print(f"\\n🔄 Recreating clean 200_140_14_gray.dxf...")
    output_file = "200_140_14_gray_CLEAN.dxf"
    
    save_dxf_layout_complete(
        placed_polygons,
        sheet_size,
        output_file,
        original_dxf_data_map
    )
    
    if os.path.exists(output_file):
        print(f"✅ Clean output created: {output_file}")
        
        # Verification
        with open(output_file, 'rb') as f:
            verify_data = parse_dxf_complete(f, verbose=False)
        
        print(f"📊 Verification:")
        print(f"   • Entities: {len(verify_data['original_entities'])}")
        print(f"   • Layers: {sorted(verify_data['layers'])}")
        
        # Check for artifacts
        image_entities = [e for e in verify_data['original_entities'] if e['type'] == 'IMAGE']
        if image_entities:
            print(f"❌ Still has {len(image_entities)} IMAGE entities!")
        else:
            print(f"✅ No IMAGE artifacts!")
            
        artifact_layers = [layer for layer in verify_data['layers'] 
                          if any(x in layer for x in ['POLYGON_', 'SHEET_', '_black', '_gray', '_white', '.dxf'])]
        
        if artifact_layers:
            print(f"❌ Artifact layers: {artifact_layers}")
        else:
            print(f"✅ No artifact layers!")
        
        # Compare with old problematic file
        if os.path.exists("200_140_14_gray.dxf"):
            with open("200_140_14_gray.dxf", 'rb') as f:
                old_data = parse_dxf_complete(f, verbose=False)
            
            old_images = [e for e in old_data['original_entities'] if e['type'] == 'IMAGE']
            print(f"\\n📊 Comparison with old file:")
            print(f"   • Old file had {len(old_images)} IMAGE entities")
            print(f"   • New file has {len(image_entities)} IMAGE entities")
            print(f"   • Improvement: {len(old_images) - len(image_entities)} fewer artifacts")
        
        print(f"\\n💾 Clean file saved as: {output_file}")
        print(f"🔧 This should match the visualization without artifacts!")
        
        # Replace the problematic file
        print(f"\\n🔄 Replacing problematic file...")
        os.rename("200_140_14_gray.dxf", "200_140_14_gray_OLD.dxf") 
        os.rename(output_file, "200_140_14_gray.dxf")
        print(f"✅ Replaced! Old file backed up as 200_140_14_gray_OLD.dxf")
        
    else:
        print("❌ Failed to create clean output")
    
    print("\\n" + "=" * 60)

if __name__ == "__main__":
    recreate_clean_output()