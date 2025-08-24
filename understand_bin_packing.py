#!/usr/bin/env python3
"""Understand how bin_packing actually works."""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from layout_optimizer import parse_dxf_complete, bin_packing
from shapely.geometry import Polygon

def understand_bin_packing():
    """Understand the actual bin packing process."""
    print("🔧 Understanding bin packing transformation")
    print("=" * 50)
    
    source_file = "200_140_14_gray.dxf"
    if not os.path.exists(source_file):
        print(f"❌ Source file {source_file} not found")
        return
    
    # Parse the source file
    with open(source_file, 'rb') as f:
        parsed_data = parse_dxf_complete(f, verbose=False)
    
    if not parsed_data['combined_polygon']:
        print("❌ No combined polygon found")
        return
    
    original_polygon = parsed_data['combined_polygon']
    print(f"📊 Original polygon:")
    print(f"   • Bounds: {original_polygon.bounds}")
    print(f"   • Centroid: {original_polygon.centroid}")
    
    # Test with bin_packing to see what happens
    polygons = [(original_polygon, os.path.basename(source_file), 'gray')]
    sheet_size = (300, 250)  # 300×250 cm = 3000×2500 mm (bigger sheet)
    
    print(f"\n🔄 Running bin_packing on sheet {sheet_size} cm")
    placed, unplaced = bin_packing(polygons, sheet_size, verbose=False)
    
    if placed:
        placed_result = placed[0]
        print(f"📊 Bin packing result:")
        print(f"   • Result format: {len(placed_result)} elements")
        if len(placed_result) >= 4:
            transformed_polygon, x_offset, y_offset, rotation_angle = placed_result[:4]
            print(f"   • Transformed polygon bounds: {transformed_polygon.bounds}")
            print(f"   • Transformed polygon centroid: {transformed_polygon.centroid}")  
            print(f"   • x_offset: {x_offset}")
            print(f"   • y_offset: {y_offset}")
            print(f"   • rotation_angle: {rotation_angle}")
            
            # Calculate expected position
            print(f"\n🧮 Position analysis:")
            orig_bounds = original_polygon.bounds
            trans_bounds = transformed_polygon.bounds
            
            print(f"   • Original bottom-left: ({orig_bounds[0]:.1f}, {orig_bounds[1]:.1f})")
            print(f"   • Transformed bottom-left: ({trans_bounds[0]:.1f}, {trans_bounds[1]:.1f})")
            print(f"   • Movement: ({trans_bounds[0] - orig_bounds[0]:.1f}, {trans_bounds[1] - orig_bounds[1]:.1f})")
            
            # Compare with offsets
            print(f"   • Expected movement from offsets: ({x_offset:.1f}, {y_offset:.1f})")
    else:
        print("❌ No placement found")
    
    print("\n" + "=" * 50)

if __name__ == "__main__":
    understand_bin_packing()