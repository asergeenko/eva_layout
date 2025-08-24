#!/usr/bin/env python3
"""Recreate the problematic layout with fixed proportions."""

import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from layout_optimizer import (
    parse_dxf_complete,
    save_dxf_layout_complete,
    apply_placement_transform,
)


def recreate_fixed_layout():
    """Recreate 200_140_14_gray.dxf with proper proportions."""
    print("🔧 Recreating layout with fixed proportions")
    print("=" * 50)

    # Files mentioned in the problem description
    files_to_process = [
        "Лодка ADMIRAL 410/2.dxf",
        "Коврик для обуви придверный/1.dxf",
        "Лодка ADMIRAL 335/1.dxf",
        "TOYOTA COROLLA 9/5.dxf",
        "ДЕКА/1.dxf",
    ]

    sample_dir = "dxf_samples"
    if not os.path.exists(sample_dir):
        print("❌ No dxf_samples directory found")
        return

    # Find the actual files
    found_files = []
    for root, dirs, files in os.walk(sample_dir):
        for file in files:
            file_path = os.path.join(root, file)
            # Check if any of the target files match
            for target in files_to_process:
                if target.endswith(file) or file in target:
                    found_files.append(file_path)
                    break

    if not found_files:
        # Fallback: use any available files
        print("⚠️ Target files not found, using available samples...")
        for root, dirs, files in os.walk(sample_dir):
            for file in files[:5]:  # Take first 5
                if file.lower().endswith(".dxf"):
                    found_files.append(os.path.join(root, file))

    if not found_files:
        print("❌ No DXF files found")
        return

    print(f"📄 Processing {len(found_files)} files:")
    for f in found_files:
        print(f"   • {os.path.relpath(f)}")

    # Parse all files
    original_dxf_data_map = {}
    placed_elements = []

    # Simulate bin packing results with rotations that caused problems
    positions = [
        (100, 250, 0),  # First element: no rotation
        (500, 800, 90),  # Second element: 90° rotation (caused distortion)
        (900, 1200, 90),  # Third element: 90° rotation
        (200, 1600, 270),  # Fourth element: 270° rotation
        (1200, 400, 0),  # Fifth element: no rotation
    ]

    for i, file_path in enumerate(found_files[:5]):  # Limit to 5 files
        print(f"\n📖 Processing: {os.path.basename(file_path)}")

        try:
            with open(file_path, "rb") as f:
                parsed_data = parse_dxf_complete(f, verbose=False)

            if parsed_data["combined_polygon"]:
                original_dxf_data_map[file_path] = parsed_data

                # Get position and rotation for this element
                x, y, rotation = positions[i % len(positions)]

                print(f"   ✅ Parsed, placing at ({x}, {y}) with {rotation}° rotation")

                # Apply transformation (same as bin_packing would do)
                transformed_polygon = apply_placement_transform(
                    parsed_data["combined_polygon"], x, y, rotation
                )

                placed_elements.append(
                    (
                        transformed_polygon,
                        x,
                        y,
                        rotation,
                        os.path.basename(file_path),
                        "gray",
                    )
                )

        except Exception as e:
            print(f"   ❌ Error: {e}")

    if not placed_elements:
        print("❌ No elements processed successfully")
        return

    print(f"\n💾 Creating fixed layout with {len(placed_elements)} elements...")

    # Save with fixed transformation
    output_file = "200_140_14_gray_FIXED.dxf"
    save_dxf_layout_complete(
        placed_elements,
        (200, 140),  # 200x140 cm sheet
        output_file,
        original_dxf_data_map,
    )

    if os.path.exists(output_file):
        print(f"✅ Fixed layout created: {output_file}")

        # Analyze the output
        print("\n🔍 Analyzing fixed output...")
        with open(output_file, "rb") as f:
            output_data = parse_dxf_complete(f, verbose=False)

        print("📊 Fixed layout stats:")
        print(f"   • Elements: {len(placed_elements)}")
        print(f"   • Output entities: {len(output_data['original_entities'])}")
        print(f"   • Layers: {sorted(output_data['layers'])}")

        print("\n🎉 Layout recreation completed!")
        print(f"💡 Compare {output_file} with 200_140_14_gray.dxf in AutoCAD Viewer")
        print(
            "🔧 The fixed version should have proper proportions for rotated elements"
        )

    else:
        print("❌ Failed to create fixed layout")


if __name__ == "__main__":
    recreate_fixed_layout()
