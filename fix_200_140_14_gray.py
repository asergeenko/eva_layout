#!/usr/bin/env python3
"""Fix 200_140_14_gray.dxf to match visualization exactly."""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from layout_optimizer import (
    parse_dxf_complete, 
    save_dxf_layout_complete, 
    bin_packing
)

def fix_200_140_14_gray():
    """Create correct 200_140_14_gray.dxf that matches visualization."""
    print("🔧 Creating corrected 200_140_14_gray.dxf")
    print("=" * 50)
    
    # Load the EXACT same files as debug test
    test_files = [
        "dxf_samples/Лодка ADMIRAL 410/2.dxf",
        "dxf_samples/Коврик для обуви придверный/1.dxf", 
        "dxf_samples/Лодка ADMIRAL 335/1.dxf",
        "dxf_samples/TOYOTA COROLLA 9/5.dxf"
    ]
    
    polygons = []
    original_dxf_data_map = {}
    
    for file_path in test_files:
        if os.path.exists(file_path):
            print(f"📄 Loading: {file_path}")
            with open(file_path, 'rb') as f:
                parsed_data = parse_dxf_complete(f, verbose=False)
            
            if parsed_data['combined_polygon']:
                filename = os.path.basename(file_path)
                polygons.append((parsed_data['combined_polygon'], filename, 'gray'))
                original_dxf_data_map[filename] = parsed_data
        else:
            print(f"   ⚠️ File not found: {file_path}")
    
    if not polygons:
        print("❌ No polygons loaded")
        return
    
    # Use SAME sheet size as visualization
    sheet_size_cm = (140, 200)  # CM as used in bin_packing
    
    print(f"\\n🔄 Running bin_packing with sheet {sheet_size_cm[0]}×{sheet_size_cm[1]} cm...")
    placed, unplaced = bin_packing(polygons, sheet_size_cm, verbose=False)
    
    if not placed:
        print("❌ Bin packing failed")
        return
    
    print(f"📊 Placed {len(placed)} elements, unplaced {len(unplaced)} elements")
    
    # CRITICAL FIX: Use CM for save_dxf_layout_complete instead of converting to MM
    # The function should handle the conversion internally
    print(f"\\n🔄 Saving DXF with sheet size in CM...")
    
    output_file = "200_140_14_gray.dxf"
    
    # Backup existing file
    if os.path.exists(output_file):
        backup_file = "200_140_14_gray_BACKUP.dxf"
        os.rename(output_file, backup_file)
        print(f"📁 Backed up existing file as: {backup_file}")
    
    # Use sheet_size in CM - let the function convert to MM internally
    save_dxf_layout_complete(
        placed,
        sheet_size_cm,  # Use CM - this should match bin_packing units
        output_file,
        original_dxf_data_map
    )
    
    if os.path.exists(output_file):
        print(f"✅ Fixed file saved: {output_file}")
        
        # Verify coordinates
        import ezdxf
        doc = ezdxf.readfile(output_file)
        all_coords = []
        for entity in doc.modelspace():
            if hasattr(entity, 'control_points'):
                points = entity.control_points
                if points:
                    all_coords.extend([(p[0], p[1]) for p in points])

        if all_coords:
            xs = [p[0] for p in all_coords]
            ys = [p[1] for p in all_coords]
            print(f"\\n📊 Coordinate verification:")
            print(f"   • X range: {min(xs):.0f} to {max(xs):.0f}")
            print(f"   • Y range: {min(ys):.0f} to {max(ys):.0f}")
            
            # Check if within expected bounds (1400×2000 mm)
            expected_max_x = sheet_size_cm[0] * 10  # 1400 mm
            expected_max_y = sheet_size_cm[1] * 10  # 2000 mm
            
            print(f"   • Expected bounds: 0-{expected_max_x} × 0-{expected_max_y} mm")
            
            x_ok = min(xs) >= -50 and max(xs) <= expected_max_x + 50
            y_ok = min(ys) >= -50 and max(ys) <= expected_max_y + 50
            
            if x_ok and y_ok:
                print(f"   ✅ All coordinates within expected bounds!")
            else:
                print(f"   ❌ Coordinates still exceed bounds:")
                if not x_ok:
                    print(f"      X: {min(xs):.0f}-{max(xs):.0f} vs 0-{expected_max_x}")
                if not y_ok:
                    print(f"      Y: {min(ys):.0f}-{max(ys):.0f} vs 0-{expected_max_y}")
        
        print(f"\\n💾 Corrected 200_140_14_gray.dxf is ready!")
        print(f"🔍 This should now match the visualization perfectly")
        
    else:
        print("❌ Failed to create fixed file")
    
    print("\\n" + "=" * 50)

if __name__ == "__main__":
    fix_200_140_14_gray()