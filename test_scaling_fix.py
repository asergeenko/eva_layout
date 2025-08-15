#!/usr/bin/env python3
"""Test script to verify scaling and positioning with actual DXF files."""

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
    plot_layout,
    scale_polygons_to_fit,
    save_dxf_layout_complete
)

def test_with_scaling():
    """Test positioning with scaling enabled."""
    print("=== Testing positioning with scaling ===")
    
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
        file_name = "200_140_1_black.dxf"
        color = "черный"
        order_id = "test_order"
        
        # Create test data in expected format
        polygons = [(polygon, file_name, color, order_id)]
        
        # Test with different sheet sizes
        sheet_sizes = [
            (200, 140),  # Standard sheet
            (300, 200),  # Larger sheet
            (400, 300),  # Very large sheet
        ]
        
        for sheet_size in sheet_sizes:
            print(f"\nTesting on sheet {sheet_size[0]}x{sheet_size[1]} cm:")
            
            # Apply scaling
            scaled_polygons = scale_polygons_to_fit(polygons, sheet_size, verbose=True)
            
            if scaled_polygons:
                scaled_polygon = scaled_polygons[0][0]
                bounds = scaled_polygon.bounds
                width_mm = bounds[2] - bounds[0]
                height_mm = bounds[3] - bounds[1]
                
                print(f"  Scaled dimensions: {width_mm/10:.1f} x {height_mm/10:.1f} cm")
                
                # Try positioning
                placed, unplaced = bin_packing(scaled_polygons, sheet_size, verbose=False)
                
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
                    print(f"  Final position: ({bounds[0]:.1f}, {bounds[1]:.1f}) to ({bounds[2]:.1f}, {bounds[3]:.1f})")
                    
                    if len(placed[0]) > 3:
                        rotation = placed[0][3]
                        print(f"  Rotation: {rotation}°")
                    
                    # Create visualization
                    try:
                        plot_buf = plot_layout(placed, sheet_size)
                        plot_filename = f"scaled_layout_{sheet_size[0]}x{sheet_size[1]}.png"
                        with open(plot_filename, 'wb') as f:
                            f.write(plot_buf.getvalue())
                        print(f"  ✅ Visualization saved to {plot_filename}")
                        
                        # Save DXF layout
                        dxf_filename = f"scaled_layout_{sheet_size[0]}x{sheet_size[1]}.dxf"
                        original_dxf_data = {file_name: result}
                        save_dxf_layout_complete(placed, sheet_size, dxf_filename, original_dxf_data)
                        print(f"  ✅ DXF layout saved to {dxf_filename}")
                        
                    except Exception as e:
                        print(f"  ❌ Error creating output: {e}")
                else:
                    print("  ❌ Could not place scaled polygon")
            else:
                print("  ❌ Scaling failed")
                
        return True
        
    except Exception as e:
        print(f"Error in scaling test: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_multiple_polygons():
    """Test with multiple small polygons to verify collision detection."""
    print("\n=== Testing multiple polygon collision detection ===")
    
    # Create several small rectangular polygons
    polygons = []
    for i in range(5):
        # Create 30x20mm rectangles at different positions
        x_offset = i * 100  # Spread them out initially
        polygon = Polygon([(x_offset, 0), (x_offset + 300, 0), (x_offset + 300, 200), (x_offset, 200)])
        polygons.append((polygon, f"carpet_{i}.dxf", "черный", f"order_{i}"))
    
    sheet_size = (200, 140)  # 200x140 cm sheet
    
    print(f"Testing {len(polygons)} polygons on {sheet_size[0]}x{sheet_size[1]} cm sheet")
    
    try:
        placed, unplaced = bin_packing(polygons, sheet_size, verbose=True)
        
        print(f"\nResults: {len(placed)} placed, {len(unplaced)} unplaced")
        
        # Check for overlaps
        overlaps = 0
        for i, placed1 in enumerate(placed):
            for j, placed2 in enumerate(placed[i+1:], i+1):
                if check_collision(placed1[0], placed2[0]):
                    overlaps += 1
                    print(f"  ❌ Overlap detected between polygon {i} and {j}")
        
        if overlaps == 0:
            print("  ✅ No overlaps detected!")
        else:
            print(f"  ❌ Found {overlaps} overlaps!")
        
        # Create visualization
        if placed:
            try:
                plot_buf = plot_layout(placed, sheet_size)
                with open("multi_polygon_test.png", 'wb') as f:
                    f.write(plot_buf.getvalue())
                print("  ✅ Visualization saved to multi_polygon_test.png")
            except Exception as e:
                print(f"  ❌ Error creating visualization: {e}")
        
        return overlaps == 0
        
    except Exception as e:
        print(f"Error in multiple polygon test: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Testing scaling and collision fixes...")
    
    success = True
    
    # Run tests
    success &= test_with_scaling()
    success &= test_multiple_polygons()
    
    if success:
        print("\n✅ All scaling and collision tests passed!")
    else:
        print("\n❌ Some tests failed!")
        sys.exit(1)