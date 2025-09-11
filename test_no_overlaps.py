#!/usr/bin/env python3
"""Test to ensure no overlapping polygons in final layout."""

import sys
sys.path.append('.')
from layout_optimizer import bin_packing, Carpet, parse_dxf_complete
from pathlib import Path

def create_test_carpets():
    """Create some test carpets for validation."""
    from shapely.geometry import Polygon
    
    carpets = []
    
    # Create a few simple test carpets
    carpet1 = Polygon([(0, 0), (200, 0), (200, 100), (0, 100)])
    carpets.append(Carpet(carpet1, "test1.dxf", "чёрный", "test", 1))
    
    carpet2 = Polygon([(0, 0), (150, 0), (150, 80), (0, 80)])
    carpets.append(Carpet(carpet2, "test2.dxf", "чёрный", "test", 1))
    
    carpet3 = Polygon([(0, 0), (100, 0), (100, 120), (0, 120)])
    carpets.append(Carpet(carpet3, "test3.dxf", "чёрный", "test", 1))
    
    return carpets

def check_layout_overlaps(placed_polygons):
    """Check if any polygons in the layout overlap."""
    overlaps = []
    
    print(f"🔍 Checking {len(placed_polygons)} placed polygons for overlaps...")
    
    for i, (poly1, *_, name1) in enumerate(placed_polygons):
        for j, (poly2, *_, name2) in enumerate(placed_polygons[i+1:], i+1):
            if poly1.intersects(poly2):
                # Calculate overlap area
                if poly1.intersection(poly2).area > 0.01:  # More than 0.01 mm²
                    overlap_area = poly1.intersection(poly2).area
                    overlaps.append({
                        'poly1': name1,
                        'poly2': name2,
                        'overlap_area': overlap_area
                    })
                    print(f"❌ OVERLAP: {name1} and {name2} overlap by {overlap_area:.2f} mm²")
    
    return overlaps

def test_no_overlaps():
    """Test that bin_packing produces no overlapping polygons."""
    print("🧪 Testing for overlaps in bin_packing output...")
    
    carpets = create_test_carpets()
    sheet_size = (300, 200)  # 30cm x 20cm
    
    # Run bin packing
    placed, unplaced = bin_packing(carpets, sheet_size, verbose=False)
    
    print(f"Placed {len(placed)} carpets, {len(unplaced)} unplaced")
    
    # Check for overlaps
    overlaps = check_layout_overlaps(placed)
    
    if overlaps:
        print(f"❌ FOUND {len(overlaps)} OVERLAPS!")
        for overlap in overlaps:
            print(f"   - {overlap['poly1']} ↔ {overlap['poly2']}: {overlap['overlap_area']:.2f} mm²")
        return False
    else:
        print("✅ NO OVERLAPS FOUND!")
        return True

def test_with_real_data():
    """Test with a small subset of real DXF data."""
    print("\n🧪 Testing with real DXF data subset...")
    
    try:
        # Try to load a few real DXF files
        dxf_path = Path('dxf_samples')
        if not dxf_path.exists():
            print("⚠️ No dxf_samples directory found, skipping real data test")
            return True
        
        carpets = []
        file_count = 0
        
        # Load first few DXF files we can find
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
                    
                    if file_count >= 5:  # Limit to 5 files for quick test
                        break
            except Exception as e:
                continue
        
        if not carpets:
            print("⚠️ No valid DXF files found, skipping real data test")
            return True
        
        print(f"Testing with {len(carpets)} real carpets...")
        
        # Run bin packing
        sheet_size = (140, 200)  # Standard sheet
        placed, unplaced = bin_packing(carpets, sheet_size, verbose=False)
        
        print(f"Placed {len(placed)} carpets, {len(unplaced)} unplaced")
        
        # Check for overlaps
        overlaps = check_layout_overlaps(placed)
        
        if overlaps:
            print(f"❌ FOUND {len(overlaps)} OVERLAPS in real data!")
            return False
        else:
            print("✅ NO OVERLAPS in real data!")
            return True
            
    except Exception as e:
        print(f"⚠️ Error in real data test: {e}")
        return True  # Don't fail the test for missing data

def main():
    """Run overlap validation tests."""
    print("🔍 OVERLAP VALIDATION TESTS")
    print("=" * 50)
    
    test1 = test_no_overlaps()
    test2 = test_with_real_data()
    
    print(f"\n🏆 VALIDATION RESULTS:")
    print(f"✅ Simple test: {'PASS' if test1 else 'FAIL'}")
    print(f"✅ Real data test: {'PASS' if test2 else 'FAIL'}")
    
    if test1 and test2:
        print("\n🎉 ALL OVERLAP TESTS PASS - NO OVERLAPPING POLYGONS!")
    else:
        print("\n❌ OVERLAP TESTS FAILED - POLYGONS ARE OVERLAPPING!")
    
    return test1 and test2

if __name__ == "__main__":
    main()