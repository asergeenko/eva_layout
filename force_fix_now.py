#!/usr/bin/env python3
"""Force fix the 200_140_14_gray.dxf file immediately"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from layout_optimizer import parse_dxf_complete, bin_packing
import ezdxf
import math

def force_fix_dxf_now():
    """Immediately fix the DXF file using the correct transformation"""
    
    # Same files as always
    sample_files = [
        'dxf_samples/Лодка ADMIRAL 410/2.dxf',
        'dxf_samples/Коврик для обуви придверный/1.dxf',
        'dxf_samples/Лодка ADMIRAL 335/1.dxf',
        'dxf_samples/TOYOTA COROLLA 9/5.dxf'
    ]
    
    parsed_data_map = {}
    polygons = []
    
    print('🔥 FORCE FIXING 200_140_14_gray.dxf NOW!')
    
    for file_path in sample_files:
        if os.path.exists(file_path):
            with open(file_path, 'rb') as f:
                parsed_data = parse_dxf_complete(f, verbose=False)
                parsed_data_map[file_path] = parsed_data
                if parsed_data['combined_polygon']:
                    polygons.append((parsed_data['combined_polygon'], file_path))
    
    placed_elements, _ = bin_packing(polygons, (140, 200), verbose=False)
    
    # Create new DXF document with corrected transformation
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4  # millimeters
    doc.header["$LUNITS"] = 2    # decimal units
    msp = doc.modelspace()
    
    for placed_element in placed_elements:
        if len(placed_element) >= 6:
            (transformed_polygon, x_offset, y_offset, rotation_angle, file_name, color) = placed_element[:6]
        else:
            transformed_polygon, x_offset, y_offset, rotation_angle, file_name = placed_element[:5]
        
        # Get original DXF data
        file_basename = os.path.basename(file_name) if file_name else file_name
        original_data_key = None
        
        if parsed_data_map:
            if file_name in parsed_data_map:
                original_data_key = file_name
            elif file_basename in parsed_data_map:
                original_data_key = file_basename
            else:
                for key in parsed_data_map.keys():
                    if os.path.basename(key) == file_basename:
                        original_data_key = key
                        break
        
        if original_data_key:
            original_data = parsed_data_map[original_data_key]
            
            if original_data["original_entities"] and original_data["combined_polygon"]:
                original_polygon = original_data["combined_polygon"]
                orig_bounds = original_polygon.bounds
                orig_center_x = (orig_bounds[0] + orig_bounds[2]) / 2
                orig_center_y = (orig_bounds[1] + orig_bounds[3]) / 2
                
                # Transformation parameters
                rotation_rad = math.radians(rotation_angle)
                cos_angle = math.cos(rotation_rad)
                sin_angle = math.sin(rotation_rad)
                
                for entity_data in original_data["original_entities"]:
                    if entity_data["type"] == "SPLINE":
                        new_entity = entity_data["entity"].copy()
                        
                        if hasattr(new_entity, 'control_points') and new_entity.control_points:
                            transformed_points = []
                            
                            for cp in new_entity.control_points:
                                if hasattr(cp, "x") and hasattr(cp, "y"):
                                    x, y = cp.x, cp.y
                                    z = getattr(cp, "z", 0.0)
                                elif len(cp) >= 2:
                                    x, y = float(cp[0]), float(cp[1])
                                    z = float(cp[2]) if len(cp) > 2 else 0.0
                                else:
                                    continue
                                
                                # CORRECTED TRANSFORMATION
                                x_centered = x - orig_center_x
                                y_centered = y - orig_center_y
                                
                                if rotation_angle != 0:
                                    rotated_x = x_centered * cos_angle - y_centered * sin_angle
                                    rotated_y = x_centered * sin_angle + y_centered * cos_angle
                                else:
                                    rotated_x = x_centered
                                    rotated_y = y_centered
                                
                                final_x = rotated_x + orig_center_x + x_offset
                                final_y = rotated_y + orig_center_y + y_offset
                                
                                transformed_points.append((final_x, final_y, z))
                            
                            if transformed_points:
                                from ezdxf.math import Vec3
                                new_control_points = [Vec3(x, y, z) for x, y, z in transformed_points]
                                new_entity.control_points = new_control_points
                                new_entity.dxf.layer = entity_data["layer"]
                                msp.add_entity(new_entity)
                    elif entity_data["type"] == "IMAGE":
                        continue
    
    # Backup current file
    if os.path.exists("200_140_14_gray.dxf"):
        import time
        timestamp = int(time.time())
        backup_name = f"200_140_14_gray_BROKEN_{timestamp}.dxf"
        os.rename("200_140_14_gray.dxf", backup_name)
        print(f"📁 Backed up broken file as: {backup_name}")
    
    # Save the corrected document
    doc.saveas("200_140_14_gray.dxf")
    print("✅ FORCE FIXED 200_140_14_gray.dxf")
    
    # Verify
    doc_verify = ezdxf.readfile("200_140_14_gray.dxf")
    coords = [(p[0], p[1]) for entity in doc_verify.modelspace() 
             if hasattr(entity, 'control_points') and entity.control_points 
             for p in entity.control_points]
    
    if coords:
        xs, ys = [p[0] for p in coords], [p[1] for p in coords]
        print(f"📊 FIXED coordinates: X[{min(xs):.0f}, {max(xs):.0f}] Y[{min(ys):.0f}, {max(ys):.0f}]")
        
        if min(xs) >= -100 and min(ys) >= -100:
            print("✅ SUCCESS - Coordinates are now correct!")
        else:
            print("❌ STILL WRONG - coordinates are still broken")
    
    print("🔥 FORCE FIX COMPLETE!")

if __name__ == "__main__":
    force_fix_dxf_now()