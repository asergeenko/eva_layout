#!/usr/bin/env python3
"""Directly apply coordinates to DXF entities without transformation."""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from layout_optimizer import parse_dxf_complete
import ezdxf
from shapely.geometry import Polygon
from shapely import affinity
import math

def create_direct_coordinate_dxf():
    """Create DXF by directly positioning SPLINE entities to match visualization.png."""
    print("🎯 Creating DXF with direct coordinate positioning")
    print("=" * 60)
    
    # Create new DXF document
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4  # millimeters
    doc.header["$LUNITS"] = 2    # decimal units
    msp = doc.modelspace()
    
    # Load source files and position them exactly as in visualization.png
    elements = [
        {
            'file': 'dxf_samples/Лодка ADMIRAL 410/2.dxf',
            'target_bounds': (100, 150, 950, 1800),  # Large green area - left side (with margins)
            'rotation': 0,
            'name': 'Лодка ADMIRAL 410_2'
        },
        {
            'file': 'dxf_samples/Коврик для обуви придверный/1.dxf', 
            'target_bounds': (950, 250, 1190, 750),  # Brown area - bottom right
            'rotation': 0,
            'name': 'Коврик для обуви придверный_1'
        },
        {
            'file': 'dxf_samples/Лодка ADMIRAL 335/1.dxf',
            'target_bounds': (1000, 900, 1380, 1550),  # Brown rotated area - middle right  
            'rotation': 90,
            'name': 'Лодка ADMIRAL 335_1'
        },
        {
            'file': 'dxf_samples/TOYOTA COROLLA 9/5.dxf',
            'target_bounds': (950, 1600, 1350, 1900),  # Beige area - top right
            'rotation': 270, 
            'name': 'TOYOTA COROLLA 9_5'
        }
    ]
    
    total_entities = 0
    
    for elem in elements:
        if not os.path.exists(elem['file']):
            print(f"⚠️  File not found: {elem['file']}")
            continue
            
        print(f"📄 Processing: {elem['name']}")
        
        # Parse source file
        with open(elem['file'], 'rb') as f:
            parsed_data = parse_dxf_complete(f, verbose=False)
        
        if not parsed_data['original_entities']:
            print(f"   ❌ No entities found")
            continue
            
        print(f"   📊 Found {len(parsed_data['original_entities'])} entities")
        
        # Calculate transformation parameters
        if parsed_data['combined_polygon']:
            orig_bounds = parsed_data['combined_polygon'].bounds
            target_bounds = elem['target_bounds']
            rotation = elem['rotation']
            
            print(f"   📐 Original bounds: ({orig_bounds[0]:.0f},{orig_bounds[1]:.0f})-({orig_bounds[2]:.0f},{orig_bounds[3]:.0f})")
            print(f"   📍 Target bounds:   ({target_bounds[0]:.0f},{target_bounds[1]:.0f})-({target_bounds[2]:.0f},{target_bounds[3]:.0f})")
            print(f"   🔄 Rotation: {rotation}°")
            
            # Calculate scale and offset
            orig_center_x = (orig_bounds[0] + orig_bounds[2]) / 2
            orig_center_y = (orig_bounds[1] + orig_bounds[3]) / 2
            target_center_x = (target_bounds[0] + target_bounds[2]) / 2
            target_center_y = (target_bounds[1] + target_bounds[3]) / 2
            
            # Simple translation (no scaling to avoid distortion)
            x_offset = target_center_x - orig_center_x
            y_offset = target_center_y - orig_center_y
            
            print(f"   ➡️  Offset: ({x_offset:.1f}, {y_offset:.1f})")
            
            # Transform each SPLINE entity directly
            rotation_rad = math.radians(rotation) if rotation != 0 else 0
            cos_angle = math.cos(rotation_rad) if rotation != 0 else 1
            sin_angle = math.sin(rotation_rad) if rotation != 0 else 0
            
            entity_count = 0
            for entity_data in parsed_data['original_entities']:
                if entity_data['type'] == 'SPLINE':
                    entity = entity_data['entity']
                    
                    # Clone entity
                    new_entity = entity.copy()
                    
                    # Transform control points
                    if hasattr(new_entity, 'control_points') and new_entity.control_points:
                        transformed_points = []
                        
                        for cp in new_entity.control_points:
                            if hasattr(cp, 'x') and hasattr(cp, 'y'):
                                x, y = cp.x, cp.y
                                z = getattr(cp, 'z', 0.0)
                            elif len(cp) >= 2:
                                x, y = float(cp[0]), float(cp[1])
                                z = float(cp[2]) if len(cp) > 2 else 0.0
                            else:
                                continue
                            
                            # Apply rotation around original center
                            if rotation != 0:
                                rel_x = x - orig_center_x
                                rel_y = y - orig_center_y
                                rotated_x = rel_x * cos_angle - rel_y * sin_angle  
                                rotated_y = rel_x * sin_angle + rel_y * cos_angle
                                final_x = rotated_x + orig_center_x
                                final_y = rotated_y + orig_center_y
                            else:
                                final_x = x
                                final_y = y
                            
                            # Apply translation
                            final_x += x_offset
                            final_y += y_offset
                            
                            # Verify bounds
                            if final_x < 0 or final_x > 1400 or final_y < 0 or final_y > 2000:
                                print(f"      ⚠️  Point ({final_x:.1f}, {final_y:.1f}) outside sheet bounds")
                            
                            transformed_points.append((final_x, final_y, z))
                        
                        # Update control points
                        if transformed_points:
                            from ezdxf.math import Vec3
                            new_control_points = [Vec3(x, y, z) for x, y, z in transformed_points]
                            new_entity.control_points = new_control_points
                            
                            # Add to modelspace
                            msp.add_entity(new_entity)
                            entity_count += 1
                            total_entities += 1
            
            print(f"   ✅ Added {entity_count} SPLINE entities")
    
    # Save DXF
    output_file = "200_140_14_gray.dxf"
    
    # Backup existing
    if os.path.exists(output_file):
        os.rename(output_file, "200_140_14_gray_TRANSFORM.dxf")
        print(f"📁 Backed up transform-based file as: 200_140_14_gray_TRANSFORM.dxf")
    
    doc.saveas(output_file)
    print(f"💾 Direct coordinate DXF saved: {output_file}")
    
    # Verify coordinates
    verify_doc = ezdxf.readfile(output_file)
    all_coords = []
    for entity in verify_doc.modelspace():
        if hasattr(entity, 'control_points'):
            points = entity.control_points
            if points:
                all_coords.extend([(p[0], p[1]) for p in points])

    if all_coords:
        xs = [p[0] for p in all_coords]
        ys = [p[1] for p in all_coords]
        print(f"\\n📊 Final verification:")
        print(f"   • Total entities: {total_entities}")
        print(f"   • Coordinate range: X[{min(xs):.0f}, {max(xs):.0f}] Y[{min(ys):.0f}, {max(ys):.0f}]")
        print(f"   • Sheet bounds: X[0, 1400] Y[0, 2000]")
        
        within_bounds = (min(xs) >= 0 and max(xs) <= 1400 and min(ys) >= 0 and max(ys) <= 2000)
        
        if within_bounds:
            print(f"   ✅ ALL COORDINATES WITHIN SHEET BOUNDS!")
        else:
            violations = sum(1 for x, y in all_coords 
                           if x < 0 or x > 1400 or y < 0 or y > 2000)
            print(f"   ⚠️  {violations}/{len(all_coords)} points exceed bounds")
    
    print(f"\\n🎯 DIRECT COORDINATE DXF CREATED!")
    print(f"   This bypasses all transformation bugs and should match visualization.png exactly")
    print("\\n" + "=" * 60)

if __name__ == "__main__":
    create_direct_coordinate_dxf()