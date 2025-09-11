#!/usr/bin/env python3
"""Test to verify collision detection fixes."""

import sys
sys.path.append('.')
from shapely.geometry import Polygon
from layout_optimizer import check_collision_fast, check_collision

def test_overlapping_polygons():
    """Test that overlapping polygons are properly detected."""
    print("🧪 Testing overlapping polygon detection...")
    
    # Create two overlapping polygons (should ALWAYS return True for collision)
    poly1 = Polygon([(0, 0), (100, 0), (100, 100), (0, 100)])
    poly2 = Polygon([(50, 50), (150, 50), (150, 150), (50, 150)])  # 50% overlap
    
    collision_fast = check_collision_fast(poly1, poly2, min_gap=0.1)
    collision_regular = check_collision(poly1, poly2, min_gap=0.1)
    
    print(f"Overlapping polygons - Fast: {'COLLISION' if collision_fast else 'NO COLLISION'}")
    print(f"Overlapping polygons - Regular: {'COLLISION' if collision_regular else 'NO COLLISION'}")
    
    return collision_fast and collision_regular

def test_touching_polygons():
    """Test polygons that touch but don't overlap."""
    print("\n🧪 Testing touching polygon detection...")
    
    # Create two touching polygons
    poly1 = Polygon([(0, 0), (100, 0), (100, 100), (0, 100)])
    poly2 = Polygon([(100, 0), (200, 0), (200, 100), (100, 100)])  # Share edge
    
    collision_fast = check_collision_fast(poly1, poly2, min_gap=0.1)
    collision_regular = check_collision(poly1, poly2, min_gap=0.1)
    
    print(f"Touching polygons - Fast: {'COLLISION' if collision_fast else 'NO COLLISION'}")
    print(f"Touching polygons - Regular: {'COLLISION' if collision_regular else 'NO COLLISION'}")
    
    return collision_fast and collision_regular

def test_close_polygons():
    """Test polygons that are very close."""
    print("\n🧪 Testing close polygon detection...")
    
    # Create two close polygons (0.05mm gap - should trigger collision with 0.1mm min_gap)
    poly1 = Polygon([(0, 0), (100, 0), (100, 100), (0, 100)])
    poly2 = Polygon([(100.05, 0), (200, 0), (200, 100), (100.05, 100)])  # 0.05mm gap
    
    collision_fast = check_collision_fast(poly1, poly2, min_gap=0.1)
    collision_regular = check_collision(poly1, poly2, min_gap=0.1)
    
    print(f"Close polygons (0.05mm gap) - Fast: {'COLLISION' if collision_fast else 'NO COLLISION'}")
    print(f"Close polygons (0.05mm gap) - Regular: {'COLLISION' if collision_regular else 'NO COLLISION'}")
    
    return collision_fast and collision_regular

def test_distant_polygons():
    """Test polygons that are far apart."""
    print("\n🧪 Testing distant polygon detection...")
    
    # Create two distant polygons (should be NO COLLISION)
    poly1 = Polygon([(0, 0), (100, 0), (100, 100), (0, 100)])
    poly2 = Polygon([(200, 200), (300, 200), (300, 300), (200, 300)])  # Far apart
    
    collision_fast = check_collision_fast(poly1, poly2, min_gap=0.1)
    collision_regular = check_collision(poly1, poly2, min_gap=0.1)
    
    print(f"Distant polygons - Fast: {'COLLISION' if collision_fast else 'NO COLLISION'}")
    print(f"Distant polygons - Regular: {'COLLISION' if collision_regular else 'NO COLLISION'}")
    
    return not collision_fast and not collision_regular  # Should be NO collision

def main():
    """Run all collision tests."""
    print("🔍 TESTING COLLISION DETECTION FIXES")
    print("=" * 50)
    
    # Run tests
    test1 = test_overlapping_polygons()
    test2 = test_touching_polygons()
    test3 = test_close_polygons()
    test4 = test_distant_polygons()
    
    print(f"\n🏆 TEST RESULTS:")
    print(f"✅ Overlapping detection: {'PASS' if test1 else 'FAIL'}")
    print(f"✅ Touching detection: {'PASS' if test2 else 'FAIL'}")
    print(f"✅ Close detection: {'PASS' if test3 else 'FAIL'}")
    print(f"✅ Distant detection: {'PASS' if test4 else 'FAIL'}")
    
    all_pass = test1 and test2 and test3 and test4
    print(f"\n🎯 OVERALL: {'ALL TESTS PASS ✅' if all_pass else 'SOME TESTS FAIL ❌'}")
    
    return all_pass

if __name__ == "__main__":
    main()