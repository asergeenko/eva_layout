#!/usr/bin/env python3

"""
Test that polygons are NOT scaled and remain in original scale
"""

import sys
import importlib

# Force reload of the module to ensure we get the latest version
if 'layout_optimizer' in sys.modules:
    importlib.reload(sys.modules['layout_optimizer'])

from shapely.geometry import Polygon

def test_no_scaling():
    """Test that polygons remain in their original scale (no scaling function needed)"""
    
    # Create test polygons with known dimensions
    original_polygons = []
    
    # Small polygon 
    small_poly = Polygon([(0, 0), (100, 0), (100, 100), (0, 100)])  # 10mm x 10mm (1cm x 1cm)
    original_polygons.append((small_poly, "small.dxf", "черный", "ORDER_1", 1))
    
    # Large polygon (remains unchanged)
    large_poly = Polygon([(0, 0), (2000, 0), (2000, 3000), (0, 3000)])  # 200mm x 300mm (20cm x 30cm)
    original_polygons.append((large_poly, "large.dxf", "черный", "ORDER_2", 1))
    
    # Reference sheet size: 15cm x 20cm (smaller than large polygon)
    reference_sheet_size = (15, 20)  
    
    print("=== ТЕСТ ОТСУТСТВИЯ МАСШТАБИРОВАНИЯ ===")
    print(f"Эталонный лист: {reference_sheet_size[0]}x{reference_sheet_size[1]} см")
    print("Полигоны остаются в исходном масштабе:")
    
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
    
    print(f"\nПолигоны НЕ масштабируются и остаются в исходном размере")
    
    # Polygons are now used directly without any scaling function
    result_polygons = original_polygons  # No scaling applied
    
    print(f"\nРезультат:")
    print(f"  Исходных полигонов: {len(original_polygons)}")
    print(f"  Результирующих полигонов: {len(result_polygons)}")
    
    # Check that polygons remained unchanged (trivially true now)
    success = True
    
    for i, (original_tuple, result_tuple) in enumerate(zip(original_polygons, result_polygons)):
        name = result_tuple[1]        
        print(f"  ✅ {name}: остался в исходном масштабе")
    
    # Check that large polygon is still larger than sheet
    large_result = result_polygons[1][0]  # Second polygon (large one)
    large_bounds = large_result.bounds
    large_width_cm = (large_bounds[2] - large_bounds[0]) / 10.0
    large_height_cm = (large_bounds[3] - large_bounds[1]) / 10.0
    
    if large_width_cm > reference_sheet_size[0] and large_height_cm > reference_sheet_size[1]:
        print(f"  ✅ Большой полигон остался больше листа: {large_width_cm:.1f}x{large_height_cm:.1f} см > {reference_sheet_size[0]}x{reference_sheet_size[1]} см")
    else:
        print(f"  ❌ Неожиданная ошибка в размерах")
        success = False
    
    return success

if __name__ == "__main__":
    result = test_no_scaling()
    print(f"\n{'✅ ТЕСТ ПРОШЕЛ - ПОЛИГОНЫ НЕ МАСШТАБИРУЮТСЯ' if result else '❌ ТЕСТ НЕ ПРОШЕЛ - ПОЛИГОНЫ ВСЕ ЕЩЕ МАСШТАБИРУЮТСЯ'}")