#!/usr/bin/env python3
"""Trace which save function is being called."""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Monkey patch to trace function calls
original_save_dxf_layout = None
original_save_dxf_layout_complete = None

def trace_save_dxf_layout(*args, **kwargs):
    print("🔍 TRACE: save_dxf_layout called")
    print(f"   Args count: {len(args)}")
    print(f"   Has original_dxf_data_map: {len(args) > 3 and args[3] is not None}")
    if len(args) > 3 and args[3]:
        print(f"   original_dxf_data_map keys: {list(args[3].keys())}")
    
    # Call original function
    return original_save_dxf_layout(*args, **kwargs)

def trace_save_dxf_layout_complete(*args, **kwargs):
    print("🔍 TRACE: save_dxf_layout_complete called")
    print(f"   Args count: {len(args)}")
    print(f"   Has original_dxf_data_map: {len(args) > 3 and args[3] is not None}")
    if len(args) > 3 and args[3]:
        print(f"   original_dxf_data_map keys: {list(args[3].keys())}")
    
    # Call original function
    return original_save_dxf_layout_complete(*args, **kwargs)

# Apply monkey patches
from layout_optimizer import save_dxf_layout, save_dxf_layout_complete
original_save_dxf_layout = save_dxf_layout
original_save_dxf_layout_complete = save_dxf_layout_complete

import layout_optimizer
layout_optimizer.save_dxf_layout = trace_save_dxf_layout
layout_optimizer.save_dxf_layout_complete = trace_save_dxf_layout_complete

# Now test with a simple case
from layout_optimizer import parse_dxf_complete
from shapely.geometry import Polygon

def trace_save_functions():
    """Test which save function gets called."""
    print("🔧 Tracing save function calls")
    print("=" * 50)
    
    source_file = "200_140_14_gray.dxf"
    if not os.path.exists(source_file):
        print(f"❌ Source file {source_file} not found")
        return
    
    # Parse the source file
    with open(source_file, 'rb') as f:
        parsed_data = parse_dxf_complete(f, verbose=False)
    
    # Create test placement
    placed_polygons = [
        (parsed_data['combined_polygon'], 10, 20, 0, os.path.basename(source_file), 'gray')
    ]
    
    # Create original_dxf_data_map
    original_dxf_data_map = {os.path.basename(source_file): parsed_data}
    
    print("🔄 Testing save_dxf_layout WITH original_dxf_data_map")
    layout_optimizer.save_dxf_layout(
        placed_polygons,
        (200, 140),
        "trace_test_with_map.dxf",
        original_dxf_data_map
    )
    
    print("\n🔄 Testing save_dxf_layout WITHOUT original_dxf_data_map")
    layout_optimizer.save_dxf_layout(
        placed_polygons,
        (200, 140),
        "trace_test_without_map.dxf",
        None
    )
    
    print("\n" + "=" * 50)

if __name__ == "__main__":
    trace_save_functions()