#!/usr/bin/env python3
"""Test contour-following packing algorithm without bounding box constraints."""

import numpy as np
import matplotlib.pyplot as plt
from shapely.geometry import Polygon
from layout_optimizer import (
    check_collision,
    find_contour_following_position, 
    translate_polygon,
    Carpet,
    bin_packing
)

def create_test_shapes():
    """Create test shapes that can potentially nestle together."""
    shapes = []
    
    # Shape 1: L-shaped polygon (concave)
    l_shape = Polygon([
        (0, 0), (100, 0), (100, 50), (50, 50), 
        (50, 100), (0, 100), (0, 0)
    ])
    shapes.append(Carpet(l_shape, "L-shape", "чёрный", "test1", 1))
    
    # Shape 2: Rectangular piece that could fit into L's concave area
    rect = Polygon([(0, 0), (40, 0), (40, 40), (0, 40)])
    shapes.append(Carpet(rect, "Rectangle", "чёрный", "test2", 1))
    
    # Shape 3: Another small rectangle
    rect2 = Polygon([(0, 0), (30, 0), (30, 30), (0, 30)])
    shapes.append(Carpet(rect2, "Rectangle2", "чёрный", "test3", 1))
    
    return shapes

def test_true_geometric_collision():
    """Test that our collision detection uses true geometry, not bounding boxes."""
    print("🧪 Testing TRUE GEOMETRIC collision detection...")
    
    # Create L-shape and rectangle that could fit in its concave area
    l_shape = Polygon([
        (0, 0), (100, 0), (100, 50), (50, 50), 
        (50, 100), (0, 100), (0, 0)
    ])
    
    # Rectangle positioned in the L's concave area (should NOT collide geometrically)
    rect_in_concave = Polygon([(55, 55), (95, 55), (95, 95), (55, 95)])
    
    # Check collision with ultra-tight gap
    collision = check_collision(l_shape, rect_in_concave, min_gap=0.1)
    
    print(f"L-shape vs Rectangle in concave area: {'COLLISION' if collision else 'NO COLLISION'}")
    print(f"Geometric distance: {l_shape.distance(rect_in_concave):.2f}mm")
    
    # This should be NO COLLISION because they don't actually touch geometrically
    return not collision  # Success if no collision detected

def test_contour_following():
    """Test contour-following placement algorithm."""
    print("\n🚀 Testing CONTOUR-FOLLOWING placement...")
    
    shapes = create_test_shapes()
    sheet_size = (200, 200)  # 20cm x 20cm sheet
    
    # Test with new algorithm
    placed, unplaced = bin_packing(shapes, sheet_size, verbose=False)
    
    print(f"Placed shapes: {len(placed)}/{len(shapes)}")
    
    # Calculate minimum distances between shapes
    min_distances = []
    for i, (poly1, *_) in enumerate(placed):
        for j, (poly2, *_) in enumerate(placed[i+1:], i+1):
            distance = poly1.distance(poly2)
            min_distances.append(distance)
    
    if min_distances:
        print(f"Minimum distance between shapes: {min(min_distances):.2f}mm")
        print(f"Average distance: {np.mean(min_distances):.2f}mm")
    
    # Create visualization
    fig, ax = plt.subplots(figsize=(8, 8))
    
    colors = ['red', 'blue', 'green', 'orange', 'purple']
    for i, (polygon, *_, filename) in enumerate(placed):
        x, y = polygon.exterior.xy
        ax.fill(x, y, alpha=0.7, color=colors[i % len(colors)], 
                edgecolor='black', linewidth=2, label=filename)
        
        # Mark centroid
        centroid = polygon.centroid
        ax.plot(centroid.x, centroid.y, 'ko', markersize=5)
    
    ax.set_xlim(0, 2000)  # 200cm in mm
    ax.set_ylim(0, 2000)
    ax.set_aspect('equal')
    ax.grid(True, alpha=0.3)
    ax.legend()
    ax.set_title('Contour-Following Packing Test\n(Shapes can nestle in concave areas)')
    ax.set_xlabel('X (mm)')
    ax.set_ylabel('Y (mm)')
    
    plt.savefig('/tmp/contour_packing_test.png', dpi=150, bbox_inches='tight')
    print("📊 Visualization saved to /tmp/contour_packing_test.png")
    
    return len(placed) == len(shapes), min_distances

def main():
    """Run all contour packing tests."""
    print("🎯 TESTING CONTOUR-FOLLOWING PACKING (NO BOUNDING BOX CONSTRAINTS)")
    print("=" * 70)
    
    # Test 1: Geometric collision detection
    geometric_test = test_true_geometric_collision()
    
    # Test 2: Contour-following placement
    all_placed, distances = test_contour_following()
    
    print(f"\n🏆 RESULTS:")
    print(f"✅ True geometric collision detection: {'PASS' if geometric_test else 'FAIL'}")
    print(f"✅ All shapes placed: {'PASS' if all_placed else 'FAIL'}")
    
    if distances:
        avg_distance = np.mean(distances)
        print(f"📐 Average distance between shapes: {avg_distance:.2f}mm")
        
        if avg_distance < 1.0:
            print("🎉 EXCELLENT! Ultra-tight packing achieved!")
        elif avg_distance < 2.0:
            print("👍 GOOD! Tight packing achieved!")
        else:
            print("⚠️ MODERATE: Still room for improvement")

if __name__ == "__main__":
    main()