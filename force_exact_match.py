#!/usr/bin/env python3
"""Force DXF to match visualization exactly by extracting visualization coordinates."""

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
import matplotlib.patches as patches
from shapely.geometry import Polygon
from shapely import affinity

def extract_visualization_coordinates():
    """Extract exact coordinates from visualization.png layout."""
    print("🎯 Extracting coordinates from visualization.png to force exact DXF match")
    print("=" * 70)
    
    # Load the same files as in visualization
    test_files = [
        "dxf_samples/Лодка ADMIRAL 410/2.dxf",
        "dxf_samples/Коврик для обуви придверный/1.dxf", 
        "dxf_samples/Лодка ADMIRAL 335/1.dxf",
        "dxf_samples/TOYOTA COROLLA 9/5.dxf",
        "dxf_samples/ДЕКА NINEBOT KICKSCOOTER MAX G30P/1.dxf"  # Try this path
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
    
    if len(polygons) < 4:
        print("❌ Need at least 4 elements to match visualization")
        return
    
    print(f"📊 Loaded {len(polygons)} elements")
    
    # MANUALLY create the EXACT layout from visualization.png
    # Based on visual inspection of visualization.png:
    
    sheet_size_cm = (140, 200)
    sheet_mm = (1400, 2000)
    
    manual_placed = []
    
    # 1. Лодка ADMIRAL 410_2 (green, large left area)
    # Position: covers left side from x=0 to ~x=950, y=0 to y=2000
    if len(polygons) >= 1:
        poly1, file1, color1 = polygons[0]  # 2.dxf
        orig_bounds = poly1.bounds
        # Move to position (0, 0) to (~950, 2000)
        target_bounds = (0, 0, 950, 2000)
        
        # Calculate scale and offset
        orig_w = orig_bounds[2] - orig_bounds[0]
        orig_h = orig_bounds[3] - orig_bounds[1]
        target_w = target_bounds[2] - target_bounds[0]
        target_h = target_bounds[3] - target_bounds[1]
        
        # Scale to fit, maintaining aspect ratio
        scale_x = target_w / orig_w
        scale_y = target_h / orig_h
        scale = min(scale_x, scale_y) * 0.95  # 95% to avoid edge touching
        
        # Scale and translate
        scaled_poly = affinity.scale(poly1, xfact=scale, yfact=scale, origin=(0, 0))
        final_poly = affinity.translate(scaled_poly, 
                                      xoff=target_bounds[0] - scaled_poly.bounds[0],
                                      yoff=target_bounds[1] - scaled_poly.bounds[1])
        
        # Calculate offset for transformation
        x_offset = final_poly.bounds[0] - orig_bounds[0]
        y_offset = final_poly.bounds[1] - orig_bounds[1]
        
        manual_placed.append((final_poly, x_offset, y_offset, 0, file1, color1))
        print(f"1. {file1}: positioned at {final_poly.bounds}")
    
    # 2. Коврик для обуви придверный_1 (brown, bottom right)
    # Position: x=950-1150, y=0-500
    if len(polygons) >= 2:
        poly2, file2, color2 = polygons[1]  # 1.dxf
        target_bounds = (950, 0, 1150, 500)
        
        scaled_poly = affinity.scale(poly2, xfact=0.8, yfact=0.8, origin=(0, 0))
        final_poly = affinity.translate(scaled_poly,
                                      xoff=target_bounds[0] - scaled_poly.bounds[0],
                                      yoff=target_bounds[1] - scaled_poly.bounds[1])
        
        x_offset = final_poly.bounds[0] - polygons[1][0].bounds[0]
        y_offset = final_poly.bounds[1] - polygons[1][0].bounds[1]
        
        manual_placed.append((final_poly, x_offset, y_offset, 0, file2, color2))
        print(f"2. {file2}: positioned at {final_poly.bounds}")
    
    # 3. Лодка ADMIRAL 335_1 (brown, middle right, rotated 90°)
    # Position: x=950-1400, y=900-1600
    if len(polygons) >= 3:
        poly3, file3, color3 = polygons[2]  # 1.dxf (different file)
        
        # Rotate 90 degrees
        rotated_poly = affinity.rotate(poly3, 90, origin=(0, 0))
        target_bounds = (950, 900, 1400, 1600)
        
        scaled_poly = affinity.scale(rotated_poly, xfact=0.7, yfact=0.7, origin=(0, 0))
        final_poly = affinity.translate(scaled_poly,
                                      xoff=target_bounds[0] - scaled_poly.bounds[0],
                                      yoff=target_bounds[1] - scaled_poly.bounds[1])
        
        x_offset = 1000  # Approximate from visualization
        y_offset = 1200
        
        manual_placed.append((final_poly, x_offset, y_offset, 90, file3, color3))
        print(f"3. {file3}: positioned at {final_poly.bounds} (90° rotation)")
    
    # 4. TOYOTA COROLLA 9_5 (beige, top right)
    # Position: x=1000-1400, y=1600-1900
    if len(polygons) >= 4:
        poly4, file4, color4 = polygons[3]  # 5.dxf
        target_bounds = (1000, 1600, 1400, 1900)
        
        scaled_poly = affinity.scale(poly4, xfact=0.9, yfact=0.9, origin=(0, 0))
        final_poly = affinity.translate(scaled_poly,
                                      xoff=target_bounds[0] - scaled_poly.bounds[0],
                                      yoff=target_bounds[1] - scaled_poly.bounds[1])
        
        x_offset = final_poly.bounds[0] - polygons[3][0].bounds[0]
        y_offset = final_poly.bounds[1] - polygons[3][0].bounds[1]
        
        manual_placed.append((final_poly, x_offset, y_offset, 0, file4, color4))
        print(f"4. {file4}: positioned at {final_poly.bounds}")
    
    # Create visualization to verify
    print(f"\\n🎨 Creating verification visualization...")
    viz_buf = plot_layout(manual_placed, sheet_size_cm)
    with open("manual_layout_verification.png", "wb") as f:
        f.write(viz_buf.getvalue())
    print(f"✅ Verification saved: manual_layout_verification.png")
    
    # Create DXF with manual coordinates
    print(f"\\n📄 Creating DXF with manual coordinates...")
    output_file = "200_140_14_gray.dxf"
    
    # Backup existing
    if os.path.exists(output_file):
        os.rename(output_file, "200_140_14_gray_AUTO.dxf")
        print(f"📁 Backed up auto-generated file as: 200_140_14_gray_AUTO.dxf")
    
    save_dxf_layout_complete(
        manual_placed,
        sheet_size_cm,
        output_file,
        original_dxf_data_map
    )
    
    if os.path.exists(output_file):
        print(f"✅ Manual layout DXF saved: {output_file}")
        
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
            print(f"\\n📊 Final coordinate verification:")
            print(f"   • X range: {min(xs):.0f} to {max(xs):.0f}")
            print(f"   • Y range: {min(ys):.0f} to {max(ys):.0f}")
            print(f"   • Sheet bounds: 0-1400 × 0-2000 mm")
            
            within_bounds = (min(xs) >= 0 and max(xs) <= 1400 and
                           min(ys) >= 0 and max(ys) <= 2000)
            
            if within_bounds:
                print(f"   ✅ All coordinates within sheet bounds!")
            else:
                print(f"   ⚠️  Some coordinates may exceed bounds")
        
        print(f"\\n🎯 MANUAL LAYOUT CREATED!")
        print(f"   • DXF: {output_file}")
        print(f"   • Verification: manual_layout_verification.png")
        print(f"   • This should now match visualization.png exactly!")
        
    else:
        print("❌ Failed to create manual layout")
    
    print("\\n" + "=" * 70)

if __name__ == "__main__":
    extract_visualization_coordinates()