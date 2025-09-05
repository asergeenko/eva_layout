#!/usr/bin/env python3

"""
Test that polygons are NOT scaled and remain in original scale
"""

import sys
import importlib

# Force reload of the module to ensure we get the latest version
if 'layout_optimizer' in sys.modules:
    importlib.reload(sys.modules['layout_optimizer'])

from layout_optimizer import scale_polygons_to_fit
from shapely.geometry import Polygon

def test_no_scaling():
    """Test that polygons keep their original scale"""
    
    # Create test polygons with known dimensions
    original_polygons = []
    
    # Small polygon (should not be scaled)
    small_poly = Polygon([(0, 0), (100, 0), (100, 100), (0, 100)])  # 10mm x 10mm (1cm x 1cm)
    original_polygons.append((small_poly, "small.dxf", "черный", "ORDER_1", 1))
    
    # Large polygon (in old system would be scaled, now should remain unchanged)
    large_poly = Polygon([(0, 0), (2000, 0), (2000, 3000), (0, 3000)])  # 200mm x 300mm (20cm x 30cm)
    original_polygons.append((large_poly, "large.dxf", "черный", "ORDER_2", 1))
    
    # Reference sheet size: 15cm x 20cm (smaller than large polygon)
    reference_sheet_size = (15, 20)  
    
    print("=== ТЕСТ ОТСУТСТВИЯ МАСШТАБИРОВАНИЯ ===")
    print(f"Эталонный лист: {reference_sheet_size[0]}x{reference_sheet_size[1]} см")
    print("Полигоны:")
    
    # Show original dimensions
    for poly_tuple in original_polygons:
        polygon = poly_tuple[0]
        name = poly_tuple[1]
        bounds = polygon.bounds
        width_mm = bounds[2] - bounds[0]
        height_mm = bounds[3] - bounds[1]
        width_cm = width_mm / 10.0
        height_cm = height_mm / 10.0
        print(f"  {name}: {width_cm:.1f}x{height_cm:.1f} см ({width_mm}x{height_mm} мм)")
    
    print(f"\nВызываем scale_polygons_to_fit()...")
    
    # Apply the scale function (should NOT scale anything now)
    result_polygons = scale_polygons_to_fit(
        original_polygons, 
        reference_sheet_size, 
        verbose=False  # Disable verbose to avoid streamlit calls in test
    )
    
    print(f"\nРезультат:")
    print(f"  Исходных полигонов: {len(original_polygons)}")
    print(f"  Результирующих полигонов: {len(result_polygons)}")
    
    # Check that polygons remained unchanged
    success = True
    
    for i, (original_tuple, result_tuple) in enumerate(zip(original_polygons, result_polygons)):
        original_poly = original_tuple[0]
        result_poly = result_tuple[0]
        name = result_tuple[1]
        
        # Check dimensions
        orig_bounds = original_poly.bounds
        result_bounds = result_poly.bounds
        
        orig_width = orig_bounds[2] - orig_bounds[0]
        orig_height = orig_bounds[3] - orig_bounds[1]
        
        result_width = result_bounds[2] - result_bounds[0]
        result_height = result_bounds[3] - result_bounds[1]
        
        # Dimensions should be exactly the same
        if abs(orig_width - result_width) < 0.001 and abs(orig_height - result_height) < 0.001:
            print(f"  ✅ {name}: размеры не изменились ({result_width/10:.1f}x{result_height/10:.1f} см)")
        else:
            print(f"  ❌ {name}: размеры изменились! {orig_width/10:.1f}x{orig_height/10:.1f} → {result_width/10:.1f}x{result_height/10:.1f} см")
            success = False
    
    # Check that even large polygon wasn't scaled down
    large_result = result_polygons[1][0]  # Second polygon (large one)
    large_bounds = large_result.bounds
    large_width_cm = (large_bounds[2] - large_bounds[0]) / 10.0
    large_height_cm = (large_bounds[3] - large_bounds[1]) / 10.0
    
    if large_width_cm > reference_sheet_size[0] and large_height_cm > reference_sheet_size[1]:
        print(f"  ✅ Большой полигон остался больше листа: {large_width_cm:.1f}x{large_height_cm:.1f} см > {reference_sheet_size[0]}x{reference_sheet_size[1]} см")
    else:
        print(f"  ❌ Большой полигон был уменьшен: {large_width_cm:.1f}x{large_height_cm:.1f} см")
        success = False
    
    return success

if __name__ == "__main__":
    result = test_no_scaling()
    print(f"\n{'✅ ТЕСТ ПРОШЕЛ - ПОЛИГОНЫ НЕ МАСШТАБИРУЮТСЯ' if result else '❌ ТЕСТ НЕ ПРОШЕЛ - ПОЛИГОНЫ ВСЕ ЕЩЕ МАСШТАБИРУЮТСЯ'}")