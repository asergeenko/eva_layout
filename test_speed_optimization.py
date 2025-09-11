#!/usr/bin/env python3
"""Test speed optimizations for contour-following packing."""

import time
import sys
sys.path.append('.')

def test_optimized_performance():
    """Test the optimized algorithm performance."""
    print("🚀 TESTING OPTIMIZED SPEED PERFORMANCE")
    print("=" * 50)
    
    start_time = time.time()
    
    # Run the placement efficiency test
    test_code = open('tests/test_placement_efficiency.py').read()
    # Execute the test code in global scope
    global_scope = {}
    exec(test_code, global_scope)
    result = global_scope['test_placement_efficiency']()
    
    total_time = time.time() - start_time
    
    print(f"\n⏱️  PERFORMANCE RESULTS:")
    print(f"Total execution time: {total_time:.1f} seconds")
    print(f"Material utilization: {result['material_utilization']:.1f}%")
    print(f"Sheets used: {result['sheets_used']}")
    print(f"All carpets placed: {result['carpets_placed']}/{result['carpets_total']}")
    
    # Performance benchmarks
    if total_time < 30:
        print("🎉 EXCELLENT SPEED! Under 30 seconds")
    elif total_time < 60:
        print("👍 GOOD SPEED! Under 1 minute")
    elif total_time < 120:
        print("⚠️  ACCEPTABLE SPEED! Under 2 minutes")
    else:
        print("❌ TOO SLOW! Over 2 minutes")
    
    # Quality benchmarks
    if result['material_utilization'] > 60:
        print("🎯 EXCELLENT QUALITY! High material utilization")
    elif result['material_utilization'] > 50:
        print("✅ GOOD QUALITY! Decent material utilization")
    else:
        print("⚠️  ROOM FOR IMPROVEMENT in material utilization")
    
    return {
        'execution_time': total_time,
        'quality': result['material_utilization'],
        'success': result['carpets_placed'] == result['carpets_total']
    }

def quick_collision_test():
    """Test collision detection speed."""
    from layout_optimizer import check_collision_fast, check_collision
    from shapely.geometry import Polygon
    
    print("\n🧪 Testing collision detection speed...")
    
    # Create test polygons
    poly1 = Polygon([(0, 0), (100, 0), (100, 100), (0, 100)])
    poly2 = Polygon([(110, 0), (210, 0), (210, 100), (110, 100)])
    
    # Test speed
    iterations = 1000
    
    start = time.time()
    for _ in range(iterations):
        check_collision_fast(poly1, poly2, min_gap=0.1)
    fast_time = time.time() - start
    
    print(f"Fast collision detection: {fast_time:.3f}s for {iterations} tests")
    print(f"Speed: {iterations/fast_time:.0f} tests/second")
    
    return fast_time

if __name__ == "__main__":
    # Test collision speed
    collision_speed = quick_collision_test()
    
    # Test overall performance
    performance = test_optimized_performance()
    
    print(f"\n🏆 FINAL BENCHMARK:")
    print(f"⚡ Speed: {performance['execution_time']:.1f}s")
    print(f"🎯 Quality: {performance['quality']:.1f}%")
    print(f"✅ Success: {'YES' if performance['success'] else 'NO'}")
    
    if performance['execution_time'] < 60 and performance['quality'] > 50:
        print("🎉 OPTIMIZATION SUCCESS! Fast + Good Quality")
    elif performance['execution_time'] < 120:
        print("👍 GOOD PROGRESS! Reasonable speed achieved")
    else:
        print("⚠️  NEEDS MORE OPTIMIZATION")