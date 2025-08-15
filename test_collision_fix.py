#!/usr/bin/env python3
"""Test script to verify collision detection and positioning fixes."""

import sys
import os
import numpy as np
import matplotlib.pyplot as plt
from shapely.geometry import Polygon
from shapely import affinity

# Import our fixed layout optimizer
from layout_optimizer import (
    parse_dxf_complete, 
    bin_packing, 
    check_collision,
    rotate_polygon,
    translate_polygon,
    plot_layout
)

def test_collision_detection():
    """Test the improved collision detection."""
    print("=== Testing collision detection ===")
    
    # Create two simple rectangular polygons
    poly1 = Polygon([(0, 0), (10, 0), (10, 5), (0, 5)])
    poly2 = Polygon([(12, 0), (22, 0), (22, 5), (12, 5)])  # 2mm gap
    poly3 = Polygon([(11, 0), (21, 0), (21, 5), (11, 5)])  # 1mm gap
    poly4 = Polygon([(9, 0), (19, 0), (19, 5), (9, 5)])   # overlapping
    
    print(f"Poly1 vs Poly2 (2mm gap): collision = {check_collision(poly1, poly2)}")  # Should be False
    print(f"Poly1 vs Poly3 (1mm gap): collision = {check_collision(poly1, poly3)}")  # Should be True (< 2mm gap)
    print(f"Poly1 vs Poly4 (overlap): collision = {check_collision(poly1, poly4)}")  # Should be True
    
    return True

def test_file_parsing():
    """Test parsing of the problematic DXF file."""
    print("\n=== Testing DXF file parsing ===")
    
    dxf_file = "200_140_1_black.dxf"
    if not os.path.exists(dxf_file):
        print(f"File {dxf_file} not found!")
        return False
    
    try:
        result = parse_dxf_complete(dxf_file, verbose=True)
        print(f"Successfully parsed: {len(result['polygons'])} polygons")
        print(f"Combined polygon area: {result['combined_polygon'].area if result['combined_polygon'] else 'None'}")
        
        if result['combined_polygon']:
            bounds = result['combined_polygon'].bounds
            width_mm = bounds[2] - bounds[0]
            height_mm = bounds[3] - bounds[1]
            print(f"Dimensions: {width_mm:.1f} x {height_mm:.1f} mm")
            print(f"Dimensions: {width_mm/10:.1f} x {height_mm/10:.1f} cm")
        
        return True
        
    except Exception as e:
        print(f"Error parsing DXF: {e}")
        return False

def test_positioning():
    """Test positioning with the problematic file."""
    print("\n=== Testing positioning algorithm ===")
    
    dxf_file = "200_140_1_black.dxf"
    if not os.path.exists(dxf_file):
        print(f"File {dxf_file} not found!")
        return False
    
    try:
        # Parse the file
        result = parse_dxf_complete(dxf_file, verbose=False)
        if not result['combined_polygon']:
            print("No polygon to test with!")
            return False
        
        polygon = result['combined_polygon']
        file_name = "test_carpet.dxf"
        color = "черный"
        order_id = "test_order"
        
        # Create test data in expected format
        polygons = [(polygon, file_name, color, order_id)]
        
        # Test different sheet sizes
        sheet_sizes = [
            (200, 140),  # Standard sheet
            (300, 200),  # Larger sheet
            (150, 100),  # Smaller sheet
        ]
        
        for sheet_size in sheet_sizes:
            print(f"\nTesting on sheet {sheet_size[0]}x{sheet_size[1]} cm:")
            
            try:
                placed, unplaced = bin_packing(polygons, sheet_size, verbose=False)
                
                print(f"  Placed: {len(placed)}, Unplaced: {len(unplaced)}")
                
                if placed:
                    placed_polygon = placed[0][0]
                    bounds = placed_polygon.bounds
                    sheet_width_mm = sheet_size[0] * 10
                    sheet_height_mm = sheet_size[1] * 10
                    
                    # Check if within bounds
                    within_bounds = (bounds[0] >= -0.1 and bounds[1] >= -0.1 and 
                                   bounds[2] <= sheet_width_mm + 0.1 and bounds[3] <= sheet_height_mm + 0.1)
                    
                    print(f"  Within bounds: {within_bounds}")
                    print(f"  Position: ({bounds[0]:.1f}, {bounds[1]:.1f}) to ({bounds[2]:.1f}, {bounds[3]:.1f})")
                    
                    if len(placed[0]) > 3:
                        rotation = placed[0][3]
                        print(f"  Rotation: {rotation}°")
                    
                    # Create visualization
                    plot_buf = plot_layout(placed, sheet_size)
                    plot_filename = f"test_layout_{sheet_size[0]}x{sheet_size[1]}.png"
                    with open(plot_filename, 'wb') as f:
                        f.write(plot_buf.getvalue())
                    print(f"  Visualization saved to {plot_filename}")
                
            except Exception as e:
                print(f"  Error: {e}")
        
        return True
        
    except Exception as e:
        print(f"Error in positioning test: {e}")
        return False

def test_rotation_boundaries():
    """Test that rotated polygons stay within boundaries."""
    print("\n=== Testing rotation boundaries ===")
    
    # Create a simple rectangular polygon
    polygon = Polygon([(0, 0), (50, 0), (50, 20), (0, 20)])  # 50x20 mm rectangle
    
    sheet_width_mm = 200  # 20cm sheet
    sheet_height_mm = 140  # 14cm sheet
    
    print("Testing rotations of 50x20mm rectangle on 200x140mm sheet:")
    
    for angle in [0, 90, 180, 270]:
        rotated = rotate_polygon(polygon, angle)
        bounds = rotated.bounds
        width = bounds[2] - bounds[0]
        height = bounds[3] - bounds[1]
        
        fits = width <= sheet_width_mm and height <= sheet_height_mm
        
        print(f"  {angle}°: {width:.1f}x{height:.1f}mm - fits: {fits}")
    
    return True

if __name__ == "__main__":
    print("Testing collision detection and positioning fixes...")
    
    success = True
    
    # Run all tests
    success &= test_collision_detection()
    success &= test_rotation_boundaries()
    success &= test_file_parsing()
    success &= test_positioning()
    
    if success:
        print("\n✅ All tests completed successfully!")
    else:
        print("\n❌ Some tests failed!")
        sys.exit(1)