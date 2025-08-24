#!/usr/bin/env python3
"""Debug the exact differences between visualization and DXF generation."""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from layout_optimizer import (
    parse_dxf_complete, 
    save_dxf_layout_complete, 
    bin_packing,
    plot_layout
)
import matplotlib.pyplot as plt

def debug_visualization_vs_dxf():
    """Create identical test for visualization and DXF to find discrepancy."""
    print("🔧 Debug: Visualization vs DXF with identical parameters")
    print("=" * 70)
    
    # Load the same files that were used in the original visualization
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
                
                bounds = parsed_data['combined_polygon'].bounds
                print(f"   • {filename}: bounds=({bounds[0]:.0f},{bounds[1]:.0f})-({bounds[2]:.0f},{bounds[3]:.0f})")
        else:
            print(f"   ⚠️ File not found: {file_path}")
    
    if not polygons:
        print("❌ No polygons loaded")
        return
    
    print(f"\\n📊 Loaded {len(polygons)} elements")
    
    # CRITICAL: Use the SAME sheet size that was used for visualization
    # Looking at visualization.png, the title shows "140.0 × 200.0 см"
    sheet_size_cm = (140, 200)  # Width × Height in CM (as shown in visualization)
    
    print(f"📐 Sheet size: {sheet_size_cm[0]}×{sheet_size_cm[1]} cm")
    
    # Run bin_packing with the SAME parameters as visualization
    print(f"\\n🔄 Running bin_packing...")
    placed, unplaced = bin_packing(polygons, sheet_size_cm, verbose=True)
    
    if not placed:
        print("❌ Bin packing failed")
        return
    
    print(f"\\n📊 Bin packing results:")
    print(f"   • Placed: {len(placed)} elements")
    print(f"   • Unplaced: {len(unplaced)} elements")
    
    for i, placed_item in enumerate(placed):
        polygon, x_offset, y_offset, rotation = placed_item[:4] 
        filename = placed_item[4] if len(placed_item) > 4 else f"item_{i}"
        bounds = polygon.bounds
        print(f"   {i+1}. {filename}:")
        print(f"      • Final bounds: ({bounds[0]:.0f},{bounds[1]:.0f}) to ({bounds[2]:.0f},{bounds[3]:.0f})")
        print(f"      • Offset: ({x_offset:.1f}, {y_offset:.1f})")
        print(f"      • Rotation: {rotation}°")
    
    # STEP 1: Create visualization using plot_layout (same as original)
    print(f"\\n🎨 Creating visualization...")
    
    # plot_layout expects (cm) and converts to (mm) internally
    viz_buf = plot_layout(placed, sheet_size_cm)
    
    # Save visualization
    with open("debug_visualization.png", "wb") as f:
        f.write(viz_buf.getvalue())
    print(f"✅ Visualization saved: debug_visualization.png")
    
    # STEP 2: Create DXF using save_dxf_layout_complete
    print(f"\\n📄 Creating DXF...")
    
    # CRITICAL: save_dxf_layout_complete expects dimensions in MM, not CM
    # Convert sheet_size from CM to MM
    sheet_size_mm = (sheet_size_cm[0] * 10, sheet_size_cm[1] * 10)  # 1400×2000 mm
    
    output_file = "debug_identical.dxf"
    
    print(f"📐 DXF sheet size: {sheet_size_mm[0]}×{sheet_size_mm[1]} mm")
    
    save_dxf_layout_complete(
        placed,
        sheet_size_mm,  # Use MM for DXF
        output_file,
        original_dxf_data_map
    )
    
    if os.path.exists(output_file):
        print(f"✅ DXF saved: {output_file}")
        
        # Verify DXF coordinates
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
            print(f"\\n📊 DXF coordinate verification:")
            print(f"   • X range: {min(xs):.0f} to {max(xs):.0f} mm")
            print(f"   • Y range: {min(ys):.0f} to {max(ys):.0f} mm")
            print(f"   • Sheet limits: 0 to {sheet_size_mm[0]} × 0 to {sheet_size_mm[1]} mm")
            
            # Check if within bounds
            x_within = min(xs) >= -50 and max(xs) <= sheet_size_mm[0] + 50
            y_within = min(ys) >= -50 and max(ys) <= sheet_size_mm[1] + 50
            
            if x_within and y_within:
                print(f"   ✅ All coordinates within sheet bounds")
            else:
                print(f"   ❌ Coordinates exceed sheet bounds!")
                if not x_within:
                    print(f"      X violation: {min(xs):.0f} to {max(xs):.0f} vs 0-{sheet_size_mm[0]}")
                if not y_within:
                    print(f"      Y violation: {min(ys):.0f} to {max(ys):.0f} vs 0-{sheet_size_mm[1]}")
        
        print(f"\\n🔍 COMPARISON:")
        print(f"   • Visualization: debug_visualization.png (uses CM→MM conversion)")
        print(f"   • DXF: {output_file} (uses MM directly)")
        print(f"   • Compare these with original visualization.png and autodesk.png")
        
        # Check if current DXF matches
        current_exists = os.path.exists("200_140_14_gray.dxf")
        if current_exists:
            current_doc = ezdxf.readfile("200_140_14_gray.dxf")
            current_coords = []
            for entity in current_doc.modelspace():
                if hasattr(entity, 'control_points'):
                    points = entity.control_points
                    if points:
                        current_coords.extend([(p[0], p[1]) for p in points])
            
            if current_coords:
                curr_xs = [p[0] for p in current_coords]
                curr_ys = [p[1] for p in current_coords]
                print(f"\\n📋 Current 200_140_14_gray.dxf coordinates:")
                print(f"   • X range: {min(curr_xs):.0f} to {max(curr_xs):.0f}")
                print(f"   • Y range: {min(curr_ys):.0f} to {max(curr_ys):.0f}")
                
                # Check if they match
                x_match = abs(min(xs) - min(curr_xs)) < 100 and abs(max(xs) - max(curr_xs)) < 100
                y_match = abs(min(ys) - min(curr_ys)) < 100 and abs(max(ys) - max(curr_ys)) < 100
                
                if x_match and y_match:
                    print(f"   ✅ Matches our debug DXF")
                else:
                    print(f"   ❌ Different from our debug DXF - indicates multiple problems")
    
    else:
        print("❌ Failed to create DXF")
    
    print("\\n" + "=" * 70)

if __name__ == "__main__":
    debug_visualization_vs_dxf()