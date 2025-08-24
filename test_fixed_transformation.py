#!/usr/bin/env python3
"""Test the fixed save_dxf_layout_complete function."""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from layout_optimizer import parse_dxf_complete, save_dxf_layout_complete, bin_packing

def test_fixed_transformation():
    """Test that the fixed transformation logic produces correct DXF positioning."""
    print("🧪 Testing fixed save_dxf_layout_complete transformation")
    print("=" * 60)
    
    # Use the same files as in create_perfect_dxf.py for comparison
    sample_files = [
        'dxf_samples/Лодка ADMIRAL 410/2.dxf',
        'dxf_samples/Коврик для обуви придверный/1.dxf', 
        'dxf_samples/Лодка ADMIRAL 335/1.dxf',
        'dxf_samples/TOYOTA COROLLA 9/5.dxf'
    ]
    
    # Parse all files
    parsed_data_map = {}
    polygons = []
    
    for file_path in sample_files:
        if os.path.exists(file_path):
            print(f"📄 Parsing: {os.path.basename(file_path)}")
            with open(file_path, 'rb') as f:
                parsed_data = parse_dxf_complete(f, verbose=False)
                parsed_data_map[file_path] = parsed_data
                
                if parsed_data['combined_polygon']:
                    polygons.append((parsed_data['combined_polygon'], file_path))
                    print(f"   ✅ Polygon extracted: {len(parsed_data['original_entities'])} entities")
                else:
                    print(f"   ❌ No polygon found")
    
    if not polygons:
        print("❌ No polygons found to process")
        return
    
    # Run bin packing
    print(f"\n📦 Running bin packing with {len(polygons)} polygons")
    sheet_size = (140, 200)  # 140x200 cm
    
    placed_elements, _ = bin_packing(
        polygons=polygons,
        sheet_size=sheet_size,
        verbose=False
    )
    
    print(f"📊 Bin packing result: {len(placed_elements)} placed elements")
    
    # Save using the fixed function
    output_path = "test_fixed_200_140_14_gray.dxf"
    save_dxf_layout_complete(
        placed_elements=placed_elements,
        sheet_size=sheet_size,
        output_path=output_path,
        original_dxf_data_map=parsed_data_map
    )
    
    print(f"💾 Saved test file: {output_path}")
    
    # Verify the result
    if os.path.exists(output_path):
        import ezdxf
        verify_doc = ezdxf.readfile(output_path)
        all_coords = []
        
        for entity in verify_doc.modelspace():
            if hasattr(entity, 'control_points') and entity.control_points:
                all_coords.extend([(p[0], p[1]) for p in entity.control_points])
        
        if all_coords:
            xs = [p[0] for p in all_coords]
            ys = [p[1] for p in all_coords]
            
            print(f"\n📊 Verification of fixed transformation:")
            print(f"   • Total coordinates: {len(all_coords)}")
            print(f"   • X range: [{min(xs):.0f}, {max(xs):.0f}]")
            print(f"   • Y range: [{min(ys):.0f}, {max(ys):.0f}]")
            print(f"   • Sheet bounds: [0, 1400] x [0, 2000] (mm)")
            
            within_bounds = (min(xs) >= 0 and max(xs) <= 1400 and 
                           min(ys) >= 0 and max(ys) <= 2000)
            
            if within_bounds:
                print(f"   ✅ All coordinates within sheet bounds!")
                
                # Compare with create_perfect_dxf.py result
                perfect_ranges = "X[81, 1335] Y[200, 1951]"
                print(f"   🎯 Target (create_perfect_dxf.py): {perfect_ranges}")
                print(f"   🧪 Fixed function result: X[{min(xs):.0f}, {max(xs):.0f}] Y[{min(ys):.0f}, {max(ys):.0f}]")
                
                # Check if they match approximately
                x_match = abs(min(xs) - 81) < 50 and abs(max(xs) - 1335) < 50
                y_match = abs(min(ys) - 200) < 50 and abs(max(ys) - 1951) < 50
                
                if x_match and y_match:
                    print(f"   ✅ TRANSFORMATION FIX SUCCESSFUL! Coordinates match target range.")
                else:
                    print(f"   ⚠️  Coordinates don't match target range closely.")
            else:
                violations = sum(1 for x, y in all_coords 
                               if x < 0 or x > 1400 or y < 0 or y > 2000)
                print(f"   ⚠️  {violations}/{len(all_coords)} points exceed bounds")
        else:
            print("   ❌ No coordinates found in output file")
    else:
        print(f"   ❌ Output file not created: {output_path}")
    
    print(f"\n🧪 FIXED TRANSFORMATION TEST COMPLETE!")
    print("=" * 60)

if __name__ == "__main__":
    test_fixed_transformation()