#!/usr/bin/env python3
"""Test extreme performance with very large datasets."""

import sys
import time
sys.path.append('.')
from test_large_dataset_performance import create_large_dataset
from layout_optimizer import bin_packing

def test_extreme_sizes():
    """Test with extreme dataset sizes."""
    print("🔥 EXTREME PERFORMANCE TEST")
    print("=" * 40)
    
    sizes = [75, 100, 150]  # Very large datasets
    
    for size in sizes:
        print(f"\n🧪 Testing EXTREME size: {size} carpets...")
        
        try:
            carpets = create_large_dataset(size)
            sheet_size = (250, 200)  # Large sheet
            
            start_time = time.time()
            placed, unplaced = bin_packing(carpets, sheet_size, verbose=False, max_processing_time=60.0)
            duration = time.time() - start_time
            
            placement_rate = len(placed) / len(carpets) * 100
            speed = len(carpets) / duration
            
            print(f"   ⏱️  Duration: {duration:.1f}s")
            print(f"   📊 Placed: {len(placed)}/{len(carpets)} ({placement_rate:.1f}%)")
            print(f"   🚀 Speed: {speed:.1f} carpets/second")
            
            # Performance assessment
            if duration < 10:
                print("   🎉 EXCELLENT: Under 10 seconds!")
            elif duration < 30:
                print("   👍 GOOD: Under 30 seconds")
            elif duration < 60:
                print("   ⚠️  ACCEPTABLE: Under 1 minute")
            else:
                print("   ❌ TOO SLOW: Over 1 minute")
                
        except Exception as e:
            print(f"   ❌ ERROR: {e}")

def main():
    """Run extreme performance tests."""
    print("⚡ EXTREME DATASET PERFORMANCE TEST")
    print("=" * 50)
    
    test_extreme_sizes()
    
    print(f"\n🏆 CONCLUSION:")
    print("If tests complete in reasonable time, optimization is successful!")

if __name__ == "__main__":
    main()