#!/usr/bin/env python3
"""Test the offset calculation fix."""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from layout_optimizer import parse_dxf_complete, save_dxf_layout_complete, bin_packing

def test_offset_fix():
    """Test the offset calculation fix."""
    print("🔧 Testing offset calculation fix")
    print("=" * 50)
    
    # Use a simple single element test
    source_file = "dxf_samples/TANK 300/4.dxf"
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
    
    # Use bin_packing
    polygons = [(parsed_data['combined_polygon'], os.path.basename(source_file), 'gray')]
    sheet_size = (1400, 2000)  # Correct orientation: width × height
    
    placed, unplaced = bin_packing(polygons, sheet_size, verbose=False)
    
    if not placed:
        print("❌ Bin packing failed")
        return
    
    original_dxf_data_map = {os.path.basename(source_file): parsed_data}
    
    print(f"🔄 Testing with offset fix...")
    output_file = "test_offset_fix.dxf"
    
    save_dxf_layout_complete(
        placed,
        sheet_size,
        output_file,
        original_dxf_data_map
    )
    
    if os.path.exists(output_file):
        print(f"✅ Output created: {output_file}")
        
        # Check coordinates
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
            print(f"📊 Coordinate ranges:")
            print(f"   X: {min(xs):.1f} to {max(xs):.1f}")
            print(f"   Y: {min(ys):.1f} to {max(ys):.1f}")
            
            # Check bounds
            within_bounds = (
                min(xs) >= -10 and max(xs) <= sheet_size[0] + 10 and
                min(ys) >= -10 and max(ys) <= sheet_size[1] + 10
            )
            
            if within_bounds:
                print(f"✅ All coordinates within sheet bounds!")
            else:
                print(f"❌ Coordinates outside sheet bounds {sheet_size}!")
                
                # Show violations
                violations = 0
                for x, y in all_coords:
                    if x < -10 or x > sheet_size[0] + 10 or y < -10 or y > sheet_size[1] + 10:
                        if violations < 5:  # Show first 5
                            print(f"   Violation: ({x:.1f}, {y:.1f})")
                        violations += 1
                if violations > 5:
                    print(f"   ... and {violations - 5} more violations")
        
        print(f"💾 Test file saved as: {output_file}")
        
    else:
        print("❌ Failed to create output")
    
    print("\n" + "=" * 50)

if __name__ == "__main__":
    test_offset_fix()