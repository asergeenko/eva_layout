#!/usr/bin/env python3
"""Test to measure how tightly carpets are packed together."""

import sys
sys.path.append('.')
from layout_optimizer import bin_packing, Carpet, parse_dxf_complete
from pathlib import Path
import numpy as np

def create_test_shapes_for_density():
    """Create shapes that can potentially pack very tightly."""
    from shapely.geometry import Polygon
    
    carpets = []
    
    # L-shaped carpet that has concave areas
    l_shape = Polygon([
        (0, 0), (200, 0), (200, 100), (100, 100),
        (100, 200), (0, 200), (0, 0)
    ])
    carpets.append(Carpet(l_shape, "L-shape.dxf", "чёрный", "test", 1))
    
    # Rectangle that could fit in L's concave area
    rect1 = Polygon([(0, 0), (80, 0), (80, 80), (0, 80)])
    carpets.append(Carpet(rect1, "rect1.dxf", "чёрный", "test", 1))
    
    # Another rectangle
    rect2 = Polygon([(0, 0), (90, 0), (90, 90), (0, 90)])
    carpets.append(Carpet(rect2, "rect2.dxf", "чёрный", "test", 1))
    
    # T-shaped carpet
    t_shape = Polygon([
        (0, 50), (150, 50), (150, 100), (75, 100),
        (75, 200), (25, 200), (25, 100), (0, 100), (0, 50)
    ])
    carpets.append(Carpet(t_shape, "T-shape.dxf", "чёрный", "test", 1))
    
    return carpets

def analyze_packing_density(placed_polygons):
    """Analyze how tightly carpets are packed together."""
    print(f"🔍 Analyzing packing density for {len(placed_polygons)} carpets...")
    
    if len(placed_polygons) < 2:
        print("⚠️ Need at least 2 carpets to analyze density")
        return {}
    
    distances = []
    closest_pairs = []
    
    # Calculate distances between all pairs
    for i, (poly1, *_, name1) in enumerate(placed_polygons):
        for j, (poly2, *_, name2) in enumerate(placed_polygons[i+1:], i+1):
            distance = poly1.distance(poly2)
            distances.append(distance)
            
            # Track very close pairs
            if distance < 2.0:  # Less than 2mm apart
                closest_pairs.append({
                    'carpet1': name1,
                    'carpet2': name2,
                    'distance': distance
                })
    
    if not distances:
        return {}
    
    # Statistics
    min_distance = min(distances)
    avg_distance = np.mean(distances)
    median_distance = np.median(distances)
    
    # Count ultra-tight pairs
    ultra_tight = sum(1 for d in distances if d < 0.5)  # Less than 0.5mm
    tight = sum(1 for d in distances if d < 1.0)        # Less than 1.0mm
    close = sum(1 for d in distances if d < 2.0)        # Less than 2.0mm
    
    print(f"📊 PACKING DENSITY STATISTICS:")
    print(f"   Minimum distance: {min_distance:.3f} mm")
    print(f"   Average distance: {avg_distance:.2f} mm") 
    print(f"   Median distance: {median_distance:.2f} mm")
    print(f"   Ultra-tight pairs (<0.5mm): {ultra_tight}/{len(distances)}")
    print(f"   Tight pairs (<1.0mm): {tight}/{len(distances)}")
    print(f"   Close pairs (<2.0mm): {close}/{len(distances)}")
    
    if closest_pairs:
        print(f"\n🎯 CLOSEST PAIRS:")
        for pair in sorted(closest_pairs, key=lambda x: x['distance'])[:5]:
            print(f"   {pair['carpet1']} ↔ {pair['carpet2']}: {pair['distance']:.3f} mm")
    
    # Quality assessment
    if min_distance < 0.2:
        quality = "EXCELLENT"
    elif min_distance < 0.5:
        quality = "VERY GOOD"
    elif min_distance < 1.0:
        quality = "GOOD"
    elif min_distance < 2.0:
        quality = "MODERATE"
    else:
        quality = "POOR"
    
    print(f"\n🏆 DENSITY QUALITY: {quality}")
    
    return {
        'min_distance': min_distance,
        'avg_distance': avg_distance,
        'median_distance': median_distance,
        'ultra_tight_pairs': ultra_tight,
        'tight_pairs': tight,
        'close_pairs': close,
        'total_pairs': len(distances),
        'quality': quality
    }

def test_density_with_shapes():
    """Test packing density with custom shapes."""
    print("🧪 Testing packing density with custom shapes...")
    
    carpets = create_test_shapes_for_density()
    sheet_size = (400, 300)  # 40cm x 30cm sheet
    
    # Run bin packing with all rotations
    placed, unplaced = bin_packing(carpets, sheet_size, verbose=False)
    
    print(f"Placed {len(placed)} carpets, {len(unplaced)} unplaced")
    
    # Analyze density
    density_stats = analyze_packing_density(placed)
    
    return density_stats

def test_density_with_real_data():
    """Test density with real DXF data."""
    print("\n🧪 Testing packing density with real DXF data...")
    
    try:
        dxf_path = Path('dxf_samples')
        if not dxf_path.exists():
            print("⚠️ No dxf_samples directory found, skipping real data test")
            return {}
        
        carpets = []
        file_count = 0
        
        # Load several DXF files
        for dxf_file in dxf_path.rglob("*.dxf"):
            try:
                polygon_data = parse_dxf_complete(dxf_file.as_posix(), verbose=False)
                if polygon_data and polygon_data.get("combined_polygon"):
                    carpet = Carpet(
                        polygon_data["combined_polygon"], 
                        dxf_file.name, 
                        "чёрный", 
                        "test", 
                        1
                    )
                    carpets.append(carpet)
                    file_count += 1
                    
                    if file_count >= 8:  # More files for better density test
                        break
            except Exception:
                continue
        
        if len(carpets) < 2:
            print("⚠️ Need at least 2 valid DXF files, skipping real data test")
            return {}
        
        print(f"Testing density with {len(carpets)} real carpets...")
        
        # Run bin packing
        sheet_size = (140, 200)
        placed, unplaced = bin_packing(carpets, sheet_size, verbose=False)
        
        print(f"Placed {len(placed)} carpets, {len(unplaced)} unplaced")
        
        # Analyze density
        density_stats = analyze_packing_density(placed)
        
        return density_stats
        
    except Exception as e:
        print(f"⚠️ Error in real data density test: {e}")
        return {}

def main():
    """Run packing density tests."""
    print("📏 PACKING DENSITY ANALYSIS")
    print("=" * 50)
    
    # Test with custom shapes
    density1 = test_density_with_shapes()
    
    # Test with real data
    density2 = test_density_with_real_data()
    
    print(f"\n🏆 DENSITY COMPARISON:")
    
    if density1:
        print(f"Custom shapes - Min distance: {density1['min_distance']:.3f}mm, Quality: {density1['quality']}")
    
    if density2:
        print(f"Real data - Min distance: {density2['min_distance']:.3f}mm, Quality: {density2['quality']}")
    
    # Overall assessment
    if density1 and density1['min_distance'] < 0.5:
        print("\n🎉 EXCELLENT TIGHT PACKING ACHIEVED!")
    elif density1 and density1['min_distance'] < 1.0:
        print("\n👍 GOOD TIGHT PACKING!")
    elif density1:
        print("\n⚠️ MODERATE PACKING - Could be tighter")
    else:
        print("\n❓ Unable to assess density")

if __name__ == "__main__":
    main()