#!/usr/bin/env python3
"""Improved DXF handling to preserve all elements without loss."""

import ezdxf
import os
import tempfile
import numpy as np
from shapely.geometry import Polygon, MultiPolygon
from shapely.ops import unary_union
from io import BytesIO

def parse_dxf_complete(file, verbose=True):
    """Parse DXF file preserving all elements without loss."""
    
    if hasattr(file, 'read'):
        # If it's a file-like object (BytesIO), write to temp file first
        with tempfile.NamedTemporaryFile(suffix='.dxf', delete=False) as tmp_file:
            file.seek(0)  # Ensure we're at the beginning
            tmp_file.write(file.read())
            tmp_file.flush()
            temp_path = tmp_file.name
        
        try:
            doc = ezdxf.readfile(temp_path)
        finally:
            # Clean up temp file
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    else:
        # If it's a file path string
        doc = ezdxf.readfile(file)
    
    msp = doc.modelspace()
    
    result = {
        'polygons': [],           # List of Shapely polygons for layout optimization
        'original_entities': [],  # All original entities for reconstruction
        'bounds': None,          # Overall bounds
        'layers': set(),         # All layers
        'doc_header': {}  # Skip header for now to avoid issues
    }
    
    total_entities = 0
    entity_types = {}
    
    # Store all original entities
    for entity in msp:
        total_entities += 1
        entity_type = entity.dxftype()
        entity_types[entity_type] = entity_types.get(entity_type, 0) + 1
        
        # Store original entity with all attributes
        entity_data = {
            'type': entity_type,
            'entity': entity,  # Store reference to original entity
            'layer': getattr(entity.dxf, 'layer', '0'),
            'color': getattr(entity.dxf, 'color', 256),
            'dxf_attribs': entity.dxfattribs()
        }
        result['original_entities'].append(entity_data)
        result['layers'].add(entity_data['layer'])
        
        # Try to convert to polygon for layout purposes
        try:
            polygon = convert_entity_to_polygon_improved(entity)
            if polygon and polygon.is_valid and polygon.area > 0.1:  # Minimum area threshold
                result['polygons'].append(polygon)
        except Exception as e:
            if verbose:
                print(f"⚠️ Не удалось конвертировать {entity_type} в полигон: {e}")
    
    if verbose:
        print(f"📊 Парсинг завершен:")
        print(f"   • Всего элементов: {total_entities}")
        print(f"   • Типы: {entity_types}")
        print(f"   • Полигонов для оптимизации: {len(result['polygons'])}")
        print(f"   • Сохранено исходных элементов: {len(result['original_entities'])}")
    
    # Calculate overall bounds
    if result['polygons']:
        all_bounds = [p.bounds for p in result['polygons']]
        min_x = min(b[0] for b in all_bounds)
        min_y = min(b[1] for b in all_bounds)
        max_x = max(b[2] for b in all_bounds)
        max_y = max(b[3] for b in all_bounds)
        result['bounds'] = (min_x, min_y, max_x, max_y)
        
        # Create combined polygon for layout optimization (without convex_hull)
        if len(result['polygons']) == 1:
            result['combined_polygon'] = result['polygons'][0]
        else:
            # Use unary_union but don't simplify to convex_hull
            combined = unary_union(result['polygons'])
            if isinstance(combined, MultiPolygon):
                # Keep as MultiPolygon or take the largest polygon
                largest_polygon = max(combined.geoms, key=lambda p: p.area)
                result['combined_polygon'] = largest_polygon
                if verbose:
                    print(f"   • Взят наибольший полигон из {len(combined.geoms)} (без упрощения)")
            else:
                result['combined_polygon'] = combined
    else:
        if verbose:
            print("⚠️ Не найдено полигонов для оптимизации")
        result['combined_polygon'] = None
    
    return result

def convert_entity_to_polygon_improved(entity):
    """Improved entity to polygon conversion with better SPLINE handling."""
    entity_type = entity.dxftype()
    
    try:
        if entity_type == "LWPOLYLINE":
            points = [(p[0], p[1]) for p in entity.get_points()]
            if len(points) >= 3:
                return Polygon(points)
                
        elif entity_type == "POLYLINE":
            points = [(vertex.dxf.location[0], vertex.dxf.location[1]) for vertex in entity.vertices]
            if len(points) >= 3:
                return Polygon(points)
                
        elif entity_type == "SPLINE":
            # Improved SPLINE handling
            try:
                # Try to get more points for better accuracy
                sampled_points = []
                construction_tool = entity.construction_tool()
                # Sample more points (100 instead of 50) for better accuracy
                for t in np.linspace(0, 1, 100):
                    point = construction_tool.point(t)
                    sampled_points.append((point.x, point.y))
                
                if len(sampled_points) >= 3:
                    return Polygon(sampled_points)
            except Exception:
                # Fallback: use control points or fit points
                try:
                    if hasattr(entity, 'control_points') and entity.control_points:
                        control_points = [(cp[0], cp[1]) for cp in entity.control_points]
                        if len(control_points) >= 3:
                            return Polygon(control_points)
                    elif hasattr(entity, 'fit_points') and entity.fit_points:
                        fit_points = [(fp[0], fp[1]) for fp in entity.fit_points]
                        if len(fit_points) >= 3:
                            return Polygon(fit_points)
                except Exception:
                    pass
                    
        elif entity_type == "ELLIPSE":
            # Improved ELLIPSE with more points
            try:
                sampled_points = []
                for angle in np.linspace(0, 2*np.pi, 72):  # 72 points for smoother curve
                    point = entity.construction_tool().point(angle)
                    sampled_points.append((point.x, point.y))
                if len(sampled_points) >= 3:
                    return Polygon(sampled_points)
            except Exception:
                pass
                
        elif entity_type == "CIRCLE":
            center = entity.dxf.center
            radius = entity.dxf.radius
            points = []
            for angle in np.linspace(0, 2*np.pi, 36):  # 36 points for circle
                x = center[0] + radius * np.cos(angle)
                y = center[1] + radius * np.sin(angle)
                points.append((x, y))
            return Polygon(points)
            
        elif entity_type == "ARC":
            center = entity.dxf.center
            radius = entity.dxf.radius
            start_angle = np.radians(entity.dxf.start_angle)
            end_angle = np.radians(entity.dxf.end_angle)
            
            # Create arc as polygon (sector)
            points = [center[:2]]  # Start from center
            angles = np.linspace(start_angle, end_angle, 20)
            for angle in angles:
                x = center[0] + radius * np.cos(angle)
                y = center[1] + radius * np.sin(angle)
                points.append((x, y))
            points.append(center[:2])  # Back to center
            
            if len(points) >= 3:
                return Polygon(points)
                
    except Exception as e:
        print(f"⚠️ Ошибка конвертации {entity_type}: {e}")
        
    return None

def save_dxf_layout_complete(placed_elements, sheet_size, output_path):
    """Save layout preserving all original elements from source DXF files."""
    
    # Create new DXF document
    doc = ezdxf.new('R2010')  # Use R2010 for better compatibility
    
    # Set DXF units to millimeters
    doc.header['$INSUNITS'] = 4  # 4 = millimeters
    doc.header['$LUNITS'] = 2    # 2 = decimal units
    
    msp = doc.modelspace()
    
    # Add sheet boundary
    sheet_width_mm = sheet_size[0] * 10
    sheet_height_mm = sheet_size[1] * 10
    sheet_corners = [(0, 0), (sheet_width_mm, 0), (sheet_width_mm, sheet_height_mm), (0, sheet_height_mm), (0, 0)]
    msp.add_lwpolyline(sheet_corners, dxfattribs={"layer": "SHEET_BOUNDARY", "color": 1})
    
    # Process each placed element
    for placed_element in placed_elements:
        if len(placed_element) >= 6:  # New format with color
            transformed_polygon, x_offset, y_offset, rotation_angle, file_name, color = placed_element[:6]
        else:  # Old format without color
            transformed_polygon, x_offset, y_offset, rotation_angle, file_name = placed_element[:5]
            color = 'серый'
        
        # If we have original DXF data, use it
        if hasattr(transformed_polygon, 'original_dxf_data'):
            # Reconstruct from original elements
            original_data = transformed_polygon.original_dxf_data
            
            for entity_data in original_data['original_entities']:
                try:
                    # Clone the original entity
                    new_entity = entity_data['entity'].copy()
                    
                    # Apply transformations (translation and rotation)
                    if rotation_angle != 0:
                        # Rotate around original centroid, then translate
                        original_bounds = original_data['bounds']
                        if original_bounds:
                            cx = (original_bounds[0] + original_bounds[2]) / 2
                            cy = (original_bounds[1] + original_bounds[3]) / 2
                            new_entity.transform(ezdxf.math.Matrix44.chain(
                                ezdxf.math.Matrix44.translate(cx, cy, 0),
                                ezdxf.math.Matrix44.z_rotate(np.radians(rotation_angle)),
                                ezdxf.math.Matrix44.translate(-cx, -cy, 0)
                            ))
                    
                    # Apply translation
                    if x_offset != 0 or y_offset != 0:
                        new_entity.transform(ezdxf.math.Matrix44.translate(x_offset, y_offset, 0))
                    
                    # Update layer name to include file name
                    base_layer = entity_data['layer']
                    new_layer = f"{file_name.replace('.dxf', '').replace('..', '_')}_{base_layer}"
                    new_entity.dxf.layer = new_layer
                    
                    # Add to modelspace
                    msp.add_entity(new_entity)
                    
                except Exception as e:
                    print(f"⚠️ Ошибка добавления элемента {entity_data['type']}: {e}")
                    # Fallback: add as simple polyline
                    if hasattr(transformed_polygon, 'exterior'):
                        points = list(transformed_polygon.exterior.coords)[:-1]
                        layer_name = file_name.replace('.dxf', '').replace('..', '_')
                        msp.add_lwpolyline(points, dxfattribs={"layer": layer_name})
        else:
            # Fallback: save as simple polyline (current method)
            if hasattr(transformed_polygon, 'exterior'):
                points = list(transformed_polygon.exterior.coords)[:-1]
                layer_name = file_name.replace('.dxf', '').replace('..', '_')
                msp.add_lwpolyline(points, dxfattribs={"layer": layer_name})
                
                # Add interior holes if any
                for interior in transformed_polygon.interiors:
                    hole_points = list(interior.coords)[:-1]
                    msp.add_lwpolyline(hole_points, dxfattribs={"layer": f"{layer_name}_HOLE"})
    
    # Save the document
    doc.saveas(output_path)
    print(f"💾 Сохранен выходной DXF файл: {output_path}")

def test_improved_dxf_handling():
    """Test the improved DXF handling."""
    print("🧪 Тестирование улучшенной обработки DXF файлов")
    print("=" * 60)
    
    # Find a sample DXF file
    sample_file = None
    dxf_samples_path = "dxf_samples"
    
    if os.path.exists(dxf_samples_path):
        for root, dirs, files in os.walk(dxf_samples_path):
            for file in files:
                if file.lower().endswith('.dxf'):
                    sample_file = os.path.join(root, file)
                    break
            if sample_file:
                break
    
    if not sample_file:
        print("❌ Не найден образец DXF файла для тестирования")
        return
    
    print(f"📄 Тестируем с файлом: {os.path.basename(sample_file)}")
    
    # Test improved parsing
    with open(sample_file, 'rb') as f:
        parsed_data = parse_dxf_complete(f, verbose=True)
    
    if parsed_data and parsed_data['combined_polygon']:
        print(f"\n✅ Улучшенный парсинг успешен!")
        print(f"   • Комбинированный полигон: площадь {parsed_data['combined_polygon'].area:.2f} мм²")
        print(f"   • Сохранено исходных элементов: {len(parsed_data['original_entities'])}")
        print(f"   • Границы: {parsed_data['bounds']}")
        
        # Attach original data to polygon for later use
        setattr(parsed_data['combined_polygon'], 'original_dxf_data', parsed_data)
        
        # Test improved output
        test_output = "test_improved_output.dxf"
        placed_elements = [(parsed_data['combined_polygon'], 50, 50, 0, "test_improved.dxf", "серый")]
        sheet_size = (200, 200)  # 200x200 cm
        
        save_dxf_layout_complete(placed_elements, sheet_size, test_output)
        
        if os.path.exists(test_output):
            print(f"\n📄 Создан улучшенный выходной файл: {test_output}")
            
            # Analyze improved output
            with open(test_output, 'rb') as f:
                improved_result = parse_dxf_complete(f, verbose=False)
            
            print(f"\n📊 Сравнение:")
            print(f"   Исходный → Улучшенный выход:")
            print(f"   • Элементов: {len(parsed_data['original_entities'])} → {len(improved_result['original_entities'])}")
            print(f"   • Полигонов: {len(parsed_data['polygons'])} → {len(improved_result['polygons'])}")
            
            # Clean up
            os.remove(test_output)
            print(f"✅ Тест завершен успешно!")
        else:
            print("❌ Не удалось создать улучшенный выходной файл")
    else:
        print("❌ Улучшенный парсинг не удался")

if __name__ == "__main__":
    test_improved_dxf_handling()