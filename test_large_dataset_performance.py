#!/usr/bin/env python3
"""Test performance optimization for large datasets."""

import sys
import time
sys.path.append('.')
from shapely.geometry import Polygon
from layout_optimizer import bin_packing, Carpet
import numpy as np

def create_large_dataset(size=50):
    """Create a large dataset of varied carpet shapes."""
    carpets = []
    
    # Create diverse shapes to simulate real workload
    for i in range(size):
        shape_type = i % 5
        
        if shape_type == 0:
            # Rectangle variants
            w, h = 80 + (i % 40), 60 + (i % 30)
            poly = Polygon([(0, 0), (w, 0), (w, h), (0, h)])
        elif shape_type == 1:
            # L-shapes
            poly = Polygon([
                (0, 0), (100 + i % 20, 0), (100 + i % 20, 50 + i % 15),
                (50 + i % 10, 50 + i % 15), (50 + i % 10, 100 + i % 25), 
                (0, 100 + i % 25)
            ])
        elif shape_type == 2:
            # T-shapes
            poly = Polygon([
                (0, 30), (120 + i % 15, 30), (120 + i % 15, 70),
                (70 + i % 10, 70), (70 + i % 10, 150 + i % 20),
                (50 + i % 10, 150 + i % 20), (50 + i % 10, 70),
                (0, 70)
            ])
        elif shape_type == 3:
            # Irregular polygons
            points = [(0, 0), (80 + i % 10, 10), (90 + i % 15, 60 + i % 10),
                     (70 + i % 5, 90 + i % 15), (20, 85 + i % 10), (5, 40)]
            poly = Polygon(points)
        else:
            # Complex shapes
            poly = Polygon([
                (0, 0), (60 + i % 8, 0), (60 + i % 8, 30), (90 + i % 12, 30),
                (90 + i % 12, 80 + i % 15), (40 + i % 5, 80 + i % 15),
                (40 + i % 5, 120 + i % 10), (0, 120 + i % 10)
            ])
        
        carpets.append(Carpet(poly, f"carpet_{i:03d}.dxf", "чёрный", f"batch_{i//10}", 1))
    
    return carpets

def test_performance_scaling():
    """Test how performance scales with dataset size."""
    print("⏱️  TESTING PERFORMANCE SCALING")
    print("=" * 50)
    
    sizes = [10, 20, 30, 50]  # Different dataset sizes
    results = []
    
    for size in sizes:
        print(f"\n🧪 Testing with {size} carpets...")
        
        carpets = create_large_dataset(size)
        sheet_size = (200, 150)  # Large sheet for testing
        
        start_time = time.time()
        placed, unplaced = bin_packing(carpets, sheet_size, verbose=False)
        duration = time.time() - start_time
        
        placement_rate = len(placed) / len(carpets) * 100
        speed = len(carpets) / duration  # carpets per second
        
        results.append({
            'size': size,
            'duration': duration,
            'placed': len(placed),
            'unplaced': len(unplaced),
            'placement_rate': placement_rate,
            'speed': speed
        })
        
        print(f"   ⏱️  Duration: {duration:.1f}s")
        print(f"   📊 Placed: {len(placed)}/{len(carpets)} ({placement_rate:.1f}%)")
        print(f"   🚀 Speed: {speed:.1f} carpets/second")
    
    return results

def analyze_scaling_results(results):
    """Analyze how well the algorithm scales."""
    print(f"\n📈 SCALING ANALYSIS:")
    print("-" * 30)
    
    for i, result in enumerate(results):
        size = result['size']
        duration = result['duration']
        speed = result['speed']
        
        if i == 0:
            baseline_speed = speed
            efficiency = 100
        else:
            # Calculate efficiency relative to smallest dataset
            expected_duration = size / baseline_speed  # Linear scaling
            efficiency = (expected_duration / duration) * 100
        
        print(f"Size {size:2d}: {duration:5.1f}s, {speed:4.1f} c/s, {efficiency:5.1f}% efficiency")
    
    # Performance assessment
    last_result = results[-1]
    if last_result['speed'] > 3.0:
        print("\n🎉 EXCELLENT: >3 carpets/second even for large datasets!")
    elif last_result['speed'] > 2.0:
        print("\n👍 GOOD: >2 carpets/second for large datasets")
    elif last_result['speed'] > 1.0:
        print("\n⚠️  MODERATE: >1 carpet/second, could be better")
    else:
        print("\n❌ SLOW: <1 carpet/second, needs optimization")

def test_quality_vs_speed():
    """Test if quality is maintained with speed optimizations."""
    print(f"\n🎯 QUALITY vs SPEED ANALYSIS:")
    print("=" * 40)
    
    # Test with different sized datasets
    for size in [15, 30, 50]:
        carpets = create_large_dataset(size)
        sheet_size = (180, 200)
        
        start_time = time.time()
        placed, unplaced = bin_packing(carpets, sheet_size, verbose=False)
        duration = time.time() - start_time
        
        # Analyze packing density
        if len(placed) >= 2:
            distances = []
            for i, (poly1, *_) in enumerate(placed):
                for j, (poly2, *_) in enumerate(placed[i+1:], i+1):
                    distances.append(poly1.distance(poly2))
            
            min_distance = min(distances) if distances else float('inf')
            avg_distance = np.mean(distances) if distances else float('inf')
            
            print(f"Size {size}: {duration:.1f}s, min_gap: {min_distance:.2f}mm, avg_gap: {avg_distance:.1f}mm")
        else:
            print(f"Size {size}: {duration:.1f}s, insufficient placements for density analysis")

def main():
    """Run large dataset performance tests."""
    print("🚀 LARGE DATASET PERFORMANCE OPTIMIZATION TEST")
    print("=" * 60)
    
    # Test scaling
    results = test_performance_scaling()
    
    # Analyze results
    analyze_scaling_results(results)
    
    # Test quality maintenance
    test_quality_vs_speed()
    
    # Overall assessment
    largest_test = results[-1]
    if largest_test['duration'] < 30 and largest_test['placement_rate'] > 80:
        print("\n🏆 OPTIMIZATION SUCCESS!")
        print(f"   Large datasets ({largest_test['size']} items) processed in {largest_test['duration']:.1f}s")
        print(f"   High placement rate: {largest_test['placement_rate']:.1f}%")
    else:
        print(f"\n⚠️  NEEDS MORE OPTIMIZATION")
        print(f"   Large dataset took {largest_test['duration']:.1f}s")
        print(f"   Placement rate: {largest_test['placement_rate']:.1f}%")

if __name__ == "__main__":
    main()