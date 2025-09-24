#!/usr/bin/env python3
"""
Build script for Rust extension module
"""
import subprocess
import sys
import os
import shutil
from pathlib import Path

def build_rust_extension():
    """Build the Rust extension and copy to current directory"""
    print("🦀 Building Rust extension...")

    # Build the extension
    result = subprocess.run([
        "cargo", "build", "--release"
    ], capture_output=True, text=True)

    if result.returncode != 0:
        print(f"❌ Build failed:")
        print(result.stderr)
        return False

    print("✅ Rust build successful!")

    # Find the built extension
    target_dir = Path("target/release")

    # Look for the shared library
    extensions = [
        "liblayout_optimizer_rust.so",  # Linux
        "liblayout_optimizer_rust.dylib",  # macOS
        "layout_optimizer_rust.dll",  # Windows
    ]

    built_lib = None
    for ext in extensions:
        lib_path = target_dir / ext
        if lib_path.exists():
            built_lib = lib_path
            break

    if not built_lib:
        print(f"❌ Could not find built extension in {target_dir}")
        return False

    # Copy to current directory with .so extension (Python expects .so)
    dest_path = Path("layout_optimizer_rust.so")
    shutil.copy2(built_lib, dest_path)
    print(f"📦 Copied {built_lib} -> {dest_path}")

    return True

def test_import():
    """Test that the extension can be imported"""
    try:
        import layout_optimizer_rust
        print("✅ Import test successful!")

        # Test basic functionality
        result = layout_optimizer_rust.fast_grid_search(
            (0.0, 0.0, 10.0, 10.0),  # carpet bounds
            [(20.0, 20.0, 30.0, 30.0)],  # placed bounds
            100.0,  # sheet width
            100.0,  # sheet height
            5  # grid size
        )
        print(f"✅ Function test successful: {result}")
        return True
    except Exception as e:
        print(f"❌ Import test failed: {e}")
        return False

if __name__ == "__main__":
    if build_rust_extension():
        test_import()
    else:
        sys.exit(1)