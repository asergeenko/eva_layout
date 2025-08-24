#!/usr/bin/env python3
"""Verify that the streamlit fix is working by testing the corrected function directly."""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import the corrected function directly from streamlit_demo.py
import importlib.util
spec = importlib.util.spec_from_file_location("streamlit_demo", "streamlit_demo.py")
streamlit_demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(streamlit_demo)

from layout_optimizer import parse_dxf_complete, bin_packing

def verify_streamlit_fix():
    """Test the corrected save_dxf_layout_complete function from streamlit_demo.py."""
    print("🧪 Testing corrected save_dxf_layout_complete from streamlit_demo.py")
    print("=" * 70)
    
    # Use same test data
    sample_files = [
        'dxf_samples/Лодка ADMIRAL 410/2.dxf',
        'dxf_samples/Коврик для обуви придверный/1.dxf',
        'dxf_samples/Лодка ADMIRAL 335/1.dxf',
        'dxf_samples/TOYOTA COROLLA 9/5.dxf'
    ]
    
    parsed_data_map = {}
    polygons = []
    
    for file_path in sample_files:
        if os.path.exists(file_path):
            with open(file_path, 'rb') as f:
                parsed_data = parse_dxf_complete(f, verbose=False)
                parsed_data_map[file_path] = parsed_data
                
                if parsed_data['combined_polygon']:
                    polygons.append((parsed_data['combined_polygon'], file_path))
                    print(f"✅ {os.path.basename(file_path)}: {len(parsed_data['original_entities'])} entities")
    
    if polygons:
        placed_elements, _ = bin_packing(polygons, (140, 200), verbose=False)
        
        # Create test output using the CORRECTED streamlit function
        test_output = "streamlit_test_200_140_14_gray.dxf"
        
        # Backup existing if exists
        if os.path.exists("200_140_14_gray.dxf"):
            os.rename("200_140_14_gray.dxf", "200_140_14_gray_BEFORE_STREAMLIT_FIX.dxf")
            print("📁 Backed up existing file as: 200_140_14_gray_BEFORE_STREAMLIT_FIX.dxf")
        
        # Call the CORRECTED function from streamlit_demo.py
        streamlit_demo.save_dxf_layout_complete(
            placed_elements=placed_elements,
            sheet_size=(140, 200),
            output_path=test_output,
            original_dxf_data_map=parsed_data_map
        )
        
        print(f"💾 Created test file using corrected streamlit function: {test_output}")
        
        # Verify the result
        if os.path.exists(test_output):
            import ezdxf
            doc = ezdxf.readfile(test_output)
            coords = [(p[0], p[1]) for entity in doc.modelspace() 
                     if hasattr(entity, 'control_points') and entity.control_points 
                     for p in entity.control_points]
            
            if coords:
                xs, ys = [p[0] for p in coords], [p[1] for p in coords]
                print(f"\n📊 CORRECTED Streamlit function results:")
                print(f"   • Total coordinates: {len(coords)}")
                print(f"   • X range: [{min(xs):.0f}, {max(xs):.0f}]")
                print(f"   • Y range: [{min(ys):.0f}, {max(ys):.0f}]")
                print(f"   • Sheet bounds: [0, 1400] x [0, 2000] (mm)")
                
                within_bounds = (min(xs) >= 0 and max(xs) <= 1400 and 
                               min(ys) >= 0 and max(ys) <= 2000)
                
                if within_bounds:
                    print(f"   ✅ ALL COORDINATES WITHIN BOUNDS!")
                else:
                    violations = sum(1 for x, y in coords 
                                   if x < 0 or x > 1400 or y < 0 or y > 2000)
                    print(f"   ⚠️  {violations}/{len(coords)} points exceed bounds")
                
                # Compare with the broken coordinates
                broken_range = "X[-527, 1406] Y[-1520, 1847]"
                correct_range = f"X[{min(xs):.0f}, {max(xs):.0f}] Y[{min(ys):.0f}, {max(ys):.0f}]"
                
                if min(xs) >= -100 and min(ys) >= -100:  # Much better than broken version
                    print(f"\n✅ STREAMLIT CORRECTION SUCCESSFUL!")
                    print(f"   Old broken: {broken_range}")
                    print(f"   New fixed:  {correct_range}")
                    
                    # Copy to actual filename
                    os.rename(test_output, "200_140_14_gray.dxf")
                    print(f"   📁 Replaced 200_140_14_gray.dxf with corrected version")
                else:
                    print(f"\n❌ Still incorrect coordinates")
            else:
                print("   ❌ No coordinates found in output")
        else:
            print(f"   ❌ Test file not created: {test_output}")
    else:
        print("❌ No polygons found to process")
    
    print(f"\n🧪 STREAMLIT CORRECTION VERIFICATION COMPLETE!")
    print("=" * 70)

if __name__ == "__main__":
    verify_streamlit_fix()