#!/usr/bin/env python3
"""Debug exact streamlit call to understand why coordinates are wrong."""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Clear all modules like streamlit would
modules_to_remove = [k for k in sys.modules.keys() if 'layout_optimizer' in k]
for module in modules_to_remove:
    if module in sys.modules:
        del sys.modules[module]

print("🔍 Testing exact streamlit import and call pattern")

# Import exactly like streamlit does
from layout_optimizer import (
    parse_dxf_complete,
    save_dxf_layout_complete,
    bin_packing_with_inventory,
    plot_layout,
    plot_input_polygons,
    scale_polygons_to_fit,
)

def test_exact_streamlit_pattern():
    """Test the exact pattern that streamlit uses."""
    
    # Use the same files
    sample_files = [
        'dxf_samples/Лодка ADMIRAL 410/2.dxf',
        'dxf_samples/Коврик для обуви придверный/1.dxf',
        'dxf_samples/Лодка ADMIRAL 335/1.dxf',
        'dxf_samples/TOYOTA COROLLA 9/5.dxf'
    ]
    
    # Parse files exactly like streamlit
    original_dxf_data_map = {}
    polygons_with_names = []
    
    for file_path in sample_files:
        if os.path.exists(file_path):
            with open(file_path, 'rb') as f:
                parsed_data = parse_dxf_complete(f, verbose=False)
                original_dxf_data_map[file_path] = parsed_data
                
                if parsed_data['combined_polygon']:
                    polygons_with_names.append((parsed_data['combined_polygon'], file_path))
    
    # Use simple bin_packing to match our test
    from layout_optimizer import bin_packing
    sheet_size = (140, 200)  # CM
    placed_polygons, _ = bin_packing(
        polygons=polygons_with_names,
        sheet_size=sheet_size,
        verbose=False
    )
    
    # Create layout structure like streamlit expects
    layout = {
        "placed_polygons": placed_polygons,
        "sheet_size": sheet_size
    }
    
    print(f"📊 Layout info:")
    print(f"   • Placed polygons: {len(layout['placed_polygons'])}")
    print(f"   • Sheet size: {layout['sheet_size']}")
    
    # Check coordinates in the layout BEFORE saving to DXF
    print(f"📊 Polygon coordinates in layout (before DXF save):")
    for i, placed_poly in enumerate(layout['placed_polygons']):
        if len(placed_poly) >= 5:
            polygon, x_offset, y_offset, rotation, filename = placed_poly[:5]
            bounds = polygon.bounds
            print(f"   {i+1}. {os.path.basename(filename)}: offset=({x_offset:.0f},{y_offset:.0f}), bounds=({bounds[0]:.0f},{bounds[1]:.0f})-({bounds[2]:.0f},{bounds[3]:.0f})")
    
    # Save DXF exactly like streamlit - mimic the OUTPUT_FOLDER pattern
    OUTPUT_FOLDER = "."  # Current directory
    sheet_height = 200
    sheet_width = 140
    sheet_number = 14
    color_suffix = "gray"
    
    output_filename = f"{sheet_height}_{sheet_width}_{sheet_number}_{color_suffix}.dxf"
    output_file = os.path.join(OUTPUT_FOLDER, output_filename)
    
    print(f"💾 About to call save_dxf_layout_complete...")
    print(f"   Output file: {output_file}")
    
    # Backup existing file
    if os.path.exists(output_file):
        os.rename(output_file, f"{output_file}.BACKUP_BEFORE_STREAMLIT_TEST")
    
    # Call exactly like streamlit does
    save_dxf_layout_complete(
        layout["placed_polygons"],      # placed_elements
        layout["sheet_size"],           # sheet_size  
        output_file,                    # output_path
        original_dxf_data_map,          # original_dxf_data_map
    )
    
    print(f"💾 save_dxf_layout_complete call completed")
    
    # Verify result
    if os.path.exists(output_file):
        import ezdxf
        doc = ezdxf.readfile(output_file)
        coords = [(p[0], p[1]) for entity in doc.modelspace() 
                 if hasattr(entity, 'control_points') and entity.control_points 
                 for p in entity.control_points]
        
        if coords:
            xs, ys = [p[0] for p in coords], [p[1] for p in coords]
            print(f"📊 FINAL DXF coordinates:")
            print(f"   X range: [{min(xs):.0f}, {max(xs):.0f}]")
            print(f"   Y range: [{min(ys):.0f}, {max(ys):.0f}]")
            
            # Check if coordinates are correct
            if min(xs) >= -100 and min(ys) >= -100:  # Much better than broken version
                print(f"   ✅ COORDINATES LOOK CORRECT!")
            else:
                print(f"   ❌ COORDINATES STILL WRONG!")
                print(f"   Expected positive coordinates, got negative minimums")
        else:
            print(f"   ❌ No coordinates found in DXF")
    else:
        print(f"   ❌ Output file not created")

if __name__ == "__main__":
    test_exact_streamlit_pattern()