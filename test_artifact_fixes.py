#!/usr/bin/env python3
"""Test script to verify DXF artifact fixes."""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from layout_optimizer import parse_dxf_complete, save_dxf_layout_complete

def test_dxf_fixes():
    """Test that DXF processing preserves original elements without artifacts."""
    print("🧪 Testing DXF artifact fixes")
    print("=" * 50)
    
    # Find a sample DXF file to test with
    test_files = [
        "200_140_1_black.dxf",
        "200_140_4_black.dxf", 
        "200_140_9_black.dxf"
    ]
    
    sample_file = None
    for filename in test_files:
        if os.path.exists(filename):
            sample_file = filename
            break
    
    if not sample_file:
        print("❌ No sample DXF file found for testing")
        return
    
    print(f"📄 Testing with: {sample_file}")
    
    # Parse the original file
    print("\n📖 Parsing original DXF...")
    with open(sample_file, 'rb') as f:
        original_data = parse_dxf_complete(f, verbose=True)
    
    print(f"✅ Original parsed successfully:")
    print(f"   • Entities: {len(original_data['original_entities'])}")
    print(f"   • Layers: {list(original_data['layers'])}")
    print(f"   • Layer order: {original_data.get('layer_order', 'Not preserved')}")
    
    # Create a test layout with the parsed data
    if original_data['combined_polygon']:
        print("\n💾 Creating test output...")
        
        # Create placed_elements as if from layout optimization
        placed_elements = [
            (original_data['combined_polygon'], 50, 50, 0, sample_file, 'gray')
        ]
        
        # Create original_dxf_data_map
        original_dxf_data_map = {sample_file: original_data}
        
        # Save using the fixed function
        output_file = f"test_fixed_{sample_file}"
        save_dxf_layout_complete(
            placed_elements, 
            (200, 200),  # 200x200 cm sheet
            output_file,
            original_dxf_data_map
        )
        
        if os.path.exists(output_file):
            print(f"✅ Test output created: {output_file}")
            
            # Parse the output to verify no artifacts
            print("\n🔍 Analyzing output for artifacts...")
            with open(output_file, 'rb') as f:
                output_data = parse_dxf_complete(f, verbose=False)
            
            print(f"\n📊 Comparison:")
            print(f"   Original → Output:")
            print(f"   • Entities: {len(original_data['original_entities'])} → {len(output_data['original_entities'])}")
            print(f"   • Layers: {len(original_data['layers'])} → {len(output_data['layers'])}")
            
            # Check for unwanted artifacts
            original_layers = set(original_data['layers'])
            output_layers = set(output_data['layers'])
            
            # Expected: output should only have original layers (no SHEET_BOUNDARY, POLYGON_, etc.)
            artifacts = output_layers - original_layers
            if artifacts:
                print(f"⚠️  Found potential artifacts in layers: {artifacts}")
            else:
                print("✅ No layer artifacts detected!")
            
            # Check entity types
            original_types = set(e['type'] for e in original_data['original_entities'])
            output_types = set(e['type'] for e in output_data['original_entities'])
            
            if original_types == output_types:
                print("✅ Entity types preserved correctly!")
            else:
                missing = original_types - output_types
                extra = output_types - original_types
                if missing:
                    print(f"⚠️  Missing entity types: {missing}")
                if extra:
                    print(f"⚠️  Extra entity types: {extra}")
            
            print(f"\n🎉 Test completed! Check {output_file} for results.")
            
        else:
            print("❌ Failed to create test output")
    else:
        print("❌ No combined polygon found in original data")

if __name__ == "__main__":
    test_dxf_fixes()