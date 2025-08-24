#!/usr/bin/env python3
"""Debug the real problem with DXF artifacts and positioning."""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from layout_optimizer import parse_dxf_complete
import ezdxf

def debug_real_problem():
    """Debug the real DXF problem."""
    print("🔧 Debugging real DXF problem")
    print("=" * 50)
    
    # Check the problematic DXF file
    problematic_file = "200_140_14_gray.dxf" 
    if not os.path.exists(problematic_file):
        print(f"❌ File {problematic_file} not found")
        return
    
    print(f"📄 Analyzing problematic file: {problematic_file}")
    
    # Parse with ezdxf directly to see what's really in the file
    doc = ezdxf.readfile(problematic_file)
    msp = doc.modelspace()
    
    layer_analysis = {}
    entity_analysis = {}
    
    for entity in msp:
        layer = entity.dxf.layer
        entity_type = entity.dxftype()
        
        if layer not in layer_analysis:
            layer_analysis[layer] = {}
        if entity_type not in layer_analysis[layer]:
            layer_analysis[layer][entity_type] = 0
        layer_analysis[layer][entity_type] += 1
        
        if entity_type not in entity_analysis:
            entity_analysis[entity_type] = 0
        entity_analysis[entity_type] += 1
        
        # Check for suspicious layer names or entity properties
        if any(suspect in layer for suspect in ['POLYGON', 'SHEET', 'BOUNDARY', '.dxf']):
            print(f"⚠️  Suspicious layer found: {layer} - {entity_type}")
    
    print(f"📊 Layer analysis:")
    for layer, entities in layer_analysis.items():
        total = sum(entities.values())
        print(f"   {layer}: {total} entities - {entities}")
    
    print(f"📋 Entity type analysis:")
    for entity_type, count in sorted(entity_analysis.items()):
        print(f"   {entity_type}: {count}")
    
    # Now check what our parsing function sees
    print(f"\n🔍 Testing our parse_dxf_complete function:")
    with open(problematic_file, 'rb') as f:
        data = parse_dxf_complete(f, verbose=False)
    
    print(f"📊 Our parser results:")
    print(f"   • Entities found: {len(data['original_entities'])}")
    print(f"   • Layers found: {sorted(data['layers'])}")
    
    entity_breakdown = {}
    for entity_data in data['original_entities']:
        layer = entity_data['layer']
        entity_type = entity_data['type']
        key = f"{layer}:{entity_type}"
        entity_breakdown[key] = entity_breakdown.get(key, 0) + 1
    
    print(f"📋 Our parser entity breakdown:")
    for key, count in sorted(entity_breakdown.items()):
        print(f"   • {key}: {count}")
    
    # Check bounds and positions
    if data['combined_polygon']:
        bounds = data['combined_polygon'].bounds
        print(f"📍 Combined polygon bounds: ({bounds[0]:.1f}, {bounds[1]:.1f}) to ({bounds[2]:.1f}, {bounds[3]:.1f})")
        print(f"📏 Size: {bounds[2]-bounds[0]:.1f} × {bounds[3]-bounds[1]:.1f} mm")
    
    print("\n" + "=" * 50)

if __name__ == "__main__":
    debug_real_problem()