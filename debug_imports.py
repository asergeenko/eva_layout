#!/usr/bin/env python3
"""Debug script to test imports for Streamlit Cloud."""

import sys
import traceback

def test_imports():
    """Test all imports required by the application."""
    print("🔧 Тестирование импортов для Streamlit Cloud")
    print("=" * 50)
    
    # Test basic imports
    try:
        import streamlit as st
        print("✅ streamlit импортирован")
    except Exception as e:
        print(f"❌ streamlit: {e}")
        return False
    
    try:
        import pandas as pd
        print("✅ pandas импортирован")
    except Exception as e:
        print(f"❌ pandas: {e}")
        return False
    
    try:
        import numpy as np
        print("✅ numpy импортирован")
    except Exception as e:
        print(f"❌ numpy: {e}")
        return False
    
    try:
        from shapely.geometry import Polygon
        print("✅ shapely импортирован")
    except Exception as e:
        print(f"❌ shapely: {e}")
        return False
    
    try:
        import ezdxf
        print("✅ ezdxf импортирован")
    except Exception as e:
        print(f"❌ ezdxf: {e}")
        return False
    
    try:
        import matplotlib.pyplot as plt
        print("✅ matplotlib импортирован")
    except Exception as e:
        print(f"❌ matplotlib: {e}")
        return False
    
    # Test layout_optimizer module
    try:
        import layout_optimizer
        print(f"✅ layout_optimizer импортирован (версия: {getattr(layout_optimizer, '__version__', 'unknown')})")
        
        # Test specific functions
        required_functions = [
            'parse_dxf', 
            'bin_packing', 
            'bin_packing_with_inventory', 
            'save_dxf_layout', 
            'plot_layout', 
            'plot_input_polygons', 
            'scale_polygons_to_fit'
        ]
        
        for func_name in required_functions:
            if hasattr(layout_optimizer, func_name):
                print(f"  ✅ {func_name}")
            else:
                print(f"  ❌ {func_name} НЕ НАЙДЕНА!")
                return False
                
    except Exception as e:
        print(f"❌ layout_optimizer: {e}")
        traceback.print_exc()
        return False
    
    print("=" * 50)
    print("🎉 Все импорты прошли успешно!")
    return True

if __name__ == "__main__":
    success = test_imports()
    sys.exit(0 if success else 1)