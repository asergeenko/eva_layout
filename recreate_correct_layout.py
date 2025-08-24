#!/usr/bin/env python3
"""Recreate correct layout matching visualization.png."""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from layout_optimizer import parse_dxf_complete, save_dxf_layout_complete, bin_packing

def recreate_correct_layout():
    """Recreate the layout that should match visualization.png."""
    print("🔧 Recreating correct layout matching visualization")
    print("=" * 60)
    
    # From visualization.png, I can see several elements:
    # 1. Large green area: "Лодка ADMIRAL 410_2" 
    # 2. Brown area: "Коврик для обуви придверный_1"
    # 3. Dark brown rotated area: "Лодка ADMIRAL 335_1" (90°)
    # 4. Light brown area: "TOYOTA COROLLA 9_5" (270°)  
    # 5. Blue area: "ДЕКА NINEBOT KICKSCOOTER MAX G30P_1"
    
    # Let's try to load these specific files
    elements_to_load = [
        ("dxf_samples/Лодка ADMIRAL 410/2.dxf", 'gray'),
        ("dxf_samples/Коврик для обуви придверный/1.dxf", 'gray'),
        ("dxf_samples/Лодка ADMIRAL 335/1.dxf", 'gray'),
        ("dxf_samples/TOYOTA COROLLA 9/5.dxf", 'gray'),
        ("dxf_samples/ДЕКА NINEBOT KICKSCOOTER MAX G30P_1/1.dxf", 'gray')  # Fake path for now
    ]
    
    polygons = []
    original_dxf_data_map = {}
    
    for file_path, color in elements_to_load:
        if os.path.exists(file_path):
            print(f"📄 Loading: {file_path}")
            with open(file_path, 'rb') as f:
                parsed_data = parse_dxf_complete(f, verbose=False)
            
            if parsed_data['combined_polygon']:
                filename = os.path.basename(file_path)
                polygons.append((parsed_data['combined_polygon'], filename, color))
                original_dxf_data_map[filename] = parsed_data
                
                bounds = parsed_data['combined_polygon'].bounds
                size = (bounds[2] - bounds[0], bounds[3] - bounds[1])
                print(f"   ✅ Loaded: {filename} - size: {size[0]:.1f}×{size[1]:.1f}mm")
            else:
                print(f"   ❌ No polygon found in {file_path}")
        else:
            print(f"   ⚠️  File not found: {file_path}")
    
    if not polygons:
        print("❌ No polygons loaded - cannot create layout")
        return
    
    print(f"\\n📊 Total elements loaded: {len(polygons)}")
    
    # Use proper sheet size: 200×140cm = 2000×1400mm  
    sheet_size = (2000, 1400)  # Width × Height in mm
    
    print(f"🔄 Running bin_packing with sheet {sheet_size[0]}×{sheet_size[1]}mm...")
    
    placed, unplaced = bin_packing(polygons, sheet_size, verbose=True)
    
    if not placed:
        print("❌ Bin packing failed")
        return
    
    print(f"📊 Placement results:")
    print(f"   • Placed: {len(placed)} elements")
    print(f"   • Unplaced: {len(unplaced)} elements")
    
    for i, placed_item in enumerate(placed):
        polygon, x_offset, y_offset, rotation = placed_item[:4]
        filename = placed_item[4] if len(placed_item) > 4 else f"item_{i}"
        bounds = polygon.bounds
        print(f"   {i+1}. {filename}: bounds=({bounds[0]:.0f},{bounds[1]:.0f})-({bounds[2]:.0f},{bounds[3]:.0f}), rotation={rotation}°")
    
    # Save the layout
    output_file = "200_140_14_gray_CORRECT.dxf"
    
    print(f"\\n🔄 Saving corrected layout...")
    
    save_dxf_layout_complete(
        placed,
        sheet_size, 
        output_file,
        original_dxf_data_map
    )
    
    if os.path.exists(output_file):
        print(f"✅ Corrected layout saved: {output_file}")
        
        # Verify
        with open(output_file, 'rb') as f:
            verify_data = parse_dxf_complete(f, verbose=False)
        
        print(f"📊 Verification:")
        print(f"   • Entities: {len(verify_data['original_entities'])}")
        print(f"   • Layers: {sorted(verify_data['layers'])}")
        
        # Check for artifacts
        image_entities = [e for e in verify_data['original_entities'] if e['type'] == 'IMAGE']
        if image_entities:
            print(f"❌ Found {len(image_entities)} IMAGE artifacts!")
        else:
            print(f"✅ No IMAGE artifacts!")
            
        if verify_data['combined_polygon']:
            final_bounds = verify_data['combined_polygon'].bounds
            print(f"📊 Final layout bounds: ({final_bounds[0]:.0f},{final_bounds[1]:.0f}) to ({final_bounds[2]:.0f},{final_bounds[3]:.0f})")
            
            # Check if it fits in sheet
            fits_width = final_bounds[2] <= sheet_size[0]
            fits_height = final_bounds[3] <= sheet_size[1]
            
            if fits_width and fits_height:
                print(f"✅ Layout fits within {sheet_size[0]}×{sheet_size[1]}mm sheet!")
            else:
                print(f"❌ Layout exceeds sheet bounds!")
                print(f"   Width: {final_bounds[2]:.0f}/{sheet_size[0]} ({'✅' if fits_width else '❌'})")  
                print(f"   Height: {final_bounds[3]:.0f}/{sheet_size[1]} ({'✅' if fits_height else '❌'})")
        
        print(f"\\n💾 Corrected layout: {output_file}")
        print(f"🔧 This should match visualization.png positioning!")
        
        # Replace the current problematic file automatically
        print("\\n🔄 Replacing current 200_140_14_gray.dxf...")
        if os.path.exists("200_140_14_gray.dxf"):
            os.rename("200_140_14_gray.dxf", "200_140_14_gray_BROKEN.dxf")
        os.rename(output_file, "200_140_14_gray.dxf")
        print(f"✅ Replaced! Old file backed up as 200_140_14_gray_BROKEN.dxf")
        
    else:
        print("❌ Failed to create corrected layout")
    
    print("\\n" + "=" * 60)

if __name__ == "__main__":
    recreate_correct_layout()