#!/usr/bin/env python3
"""
Test script to verify basic functionality with the new data structure
"""

import os
import pandas as pd
from io import BytesIO

def test_excel_parsing():
    """Test parsing of the new Excel structure"""
    print("Testing Excel parsing...")
    
    # Check if sample_input.xlsx exists
    excel_path = "sample_input.xlsx"
    if not os.path.exists(excel_path):
        print(f"❌ Excel file {excel_path} not found")
        return False
    
    try:
        # Read Excel file
        df = pd.read_excel(excel_path)
        print(f"✅ Excel file loaded successfully")
        print(f"   - Shape: {df.shape}")
        print(f"   - Columns: {df.columns.tolist()}")
        
        # Check column H (ХАРАКТЕРИСТИКА)
        if len(df.columns) > 7:
            col_h_values = df.iloc[:, 7].value_counts()
            print(f"   - Column H (ХАРАКТЕРИСТИКА) values:")
            for value, count in col_h_values.items():
                print(f"     • {value}: {count}")
        
        return True
    except Exception as e:
        print(f"❌ Error reading Excel file: {e}")
        return False

def test_dxf_samples_structure():
    """Test DXF samples folder structure"""
    print("\nTesting DXF samples structure...")
    
    dxf_folder = "dxf_samples"
    if not os.path.exists(dxf_folder):
        print(f"❌ DXF samples folder {dxf_folder} not found")
        return False
    
    # Count folders and files
    folder_count = 0
    file_count = 0
    
    for root, dirs, files in os.walk(dxf_folder):
        folder_count += len(dirs)
        dxf_files = [f for f in files if f.lower().endswith('.dxf')]
        file_count += len(dxf_files)
    
    print(f"✅ DXF samples structure:")
    print(f"   - Folders: {folder_count}")
    print(f"   - DXF files: {file_count}")
    
    # List some sample folders
    sample_folders = []
    for item in os.listdir(dxf_folder):
        if os.path.isdir(os.path.join(dxf_folder, item)):
            sample_folders.append(item)
    
    print(f"   - Sample folders: {sample_folders[:10]}")  # First 10 folders
    
    return True

def test_layout_optimizer_import():
    """Test layout optimizer import"""
    print("\nTesting layout optimizer import...")
    
    try:
        from layout_optimizer import parse_dxf_complete, bin_packing_with_inventory
        print("✅ Layout optimizer imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Error importing layout optimizer: {e}")
        return False

def test_product_types():
    """Test product types from Excel"""
    print("\nTesting product types...")
    
    try:
        df = pd.read_excel("sample_input.xlsx")
        
        # Get unique product types from column H
        if len(df.columns) > 7:
            product_types = df.iloc[:, 7].dropna().unique()
            
            print(f"✅ Found product types:")
            for pt in product_types:
                if pd.notna(pt) and pt != 'Изделие':  # Skip header
                    print(f"   - {pt}")
                    
                    # Try to find corresponding DXF folders
                    if pt in ['борт', 'водитель', 'передние']:
                        print(f"     → Car floor mats category")
                    elif pt == 'самокат':
                        print(f"     → Scooter category")
                    elif pt == 'ковер':
                        print(f"     → Floor mat category")
                    elif pt == 'лодка':
                        print(f"     → Boat category")
        
        return True
    except Exception as e:
        print(f"❌ Error analyzing product types: {e}")
        return False

def main():
    print("🧪 Testing EVA Layout System with New Data Structure")
    print("=" * 60)
    
    tests = [
        test_excel_parsing,
        test_dxf_samples_structure,
        test_layout_optimizer_import,
        test_product_types
    ]
    
    results = []
    for test in tests:
        result = test()
        results.append(result)
    
    print("\n" + "=" * 60)
    print("📊 Test Results Summary:")
    
    passed = sum(results)
    total = len(results)
    
    print(f"   ✅ Passed: {passed}/{total}")
    if passed < total:
        print(f"   ❌ Failed: {total - passed}/{total}")
    
    if passed == total:
        print("\n🎉 All tests passed! System is ready to use.")
    else:
        print("\n⚠️  Some tests failed. Please check the output above.")
    
    return passed == total

if __name__ == "__main__":
    main()