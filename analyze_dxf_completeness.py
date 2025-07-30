#!/usr/bin/env python3
"""Analyze DXF files to check completeness of elements preservation."""

import ezdxf
import os
from shapely.geometry import Polygon
from shapely.ops import unary_union
import tempfile

def analyze_dxf_file(file_path, description=""):
    """Analyze a DXF file and return detailed information about its contents."""
    print(f"\n📄 Анализ файла: {os.path.basename(file_path)} {description}")
    print("=" * 70)
    
    try:
        doc = ezdxf.readfile(file_path)
        msp = doc.modelspace()
        
        analysis = {
            'total_entities': 0,
            'entity_types': {},
            'polygons': [],
            'text_entities': [],
            'other_entities': [],
            'layers': set(),
            'colors': set()
        }
        
        for entity in msp:
            analysis['total_entities'] += 1
            entity_type = entity.dxftype()
            analysis['entity_types'][entity_type] = analysis['entity_types'].get(entity_type, 0) + 1
            
            # Track layers and colors
            if hasattr(entity.dxf, 'layer'):
                analysis['layers'].add(entity.dxf.layer)
            if hasattr(entity.dxf, 'color'):
                analysis['colors'].add(entity.dxf.color)
            
            # Categorize entities
            if entity_type in ['LWPOLYLINE', 'POLYLINE', 'SPLINE', 'ELLIPSE', 'CIRCLE', 'ARC']:
                # These can be converted to polygons
                try:
                    polygon = convert_entity_to_polygon(entity)
                    if polygon and polygon.is_valid:
                        analysis['polygons'].append({
                            'type': entity_type,
                            'area': polygon.area,
                            'bounds': polygon.bounds,
                            'polygon': polygon
                        })
                except Exception as e:
                    print(f"⚠️ Ошибка конвертации {entity_type}: {e}")
                    
            elif entity_type in ['TEXT', 'MTEXT']:
                analysis['text_entities'].append({
                    'type': entity_type,
                    'text': getattr(entity.dxf, 'text', 'N/A'),
                    'position': getattr(entity.dxf, 'insert', 'N/A')
                })
                
            else:
                analysis['other_entities'].append({
                    'type': entity_type,
                    'attributes': str(entity.dxf)[:100]  # First 100 chars
                })
        
        # Print analysis
        print(f"📊 Общий анализ:")
        print(f"   • Всего элементов: {analysis['total_entities']}")
        print(f"   • Слоев: {len(analysis['layers'])}")
        print(f"   • Цветов: {len(analysis['colors'])}")
        
        print(f"\n🔧 Типы элементов:")
        for entity_type, count in sorted(analysis['entity_types'].items()):
            print(f"   • {entity_type}: {count}")
        
        print(f"\n🔷 Геометрические элементы (конвертируемые в полигоны): {len(analysis['polygons'])}")
        if analysis['polygons']:
            total_area = sum(p['area'] for p in analysis['polygons'])
            print(f"   • Общая площадь: {total_area:.2f} мм²")
            for i, poly_info in enumerate(analysis['polygons'][:5], 1):  # Show first 5
                print(f"   • {i}. {poly_info['type']}: площадь {poly_info['area']:.2f} мм²")
        
        print(f"\n📝 Текстовые элементы: {len(analysis['text_entities'])}")
        for i, text_info in enumerate(analysis['text_entities'][:3], 1):  # Show first 3
            print(f"   • {i}. {text_info['type']}: '{text_info['text']}'")
        
        print(f"\n❓ Другие элементы: {len(analysis['other_entities'])}")
        for i, other_info in enumerate(analysis['other_entities'][:3], 1):  # Show first 3
            print(f"   • {i}. {other_info['type']}")
        
        if analysis['layers']:
            print(f"\n🗂️ Слои: {', '.join(sorted(analysis['layers']))}")
        
        return analysis
        
    except Exception as e:
        print(f"❌ Ошибка анализа файла: {e}")
        return None

def convert_entity_to_polygon(entity):
    """Convert a DXF entity to a Shapely polygon."""
    entity_type = entity.dxftype()
    
    if entity_type == "LWPOLYLINE":
        points = [(p[0], p[1]) for p in entity.get_points()]
        if len(points) >= 3:
            return Polygon(points)
            
    elif entity_type == "POLYLINE":
        points = [(vertex.dxf.location[0], vertex.dxf.location[1]) for vertex in entity.vertices]
        if len(points) >= 3:
            return Polygon(points)
            
    elif entity_type == "CIRCLE":
        center = entity.dxf.center
        radius = entity.dxf.radius
        import numpy as np
        points = []
        for angle in np.linspace(0, 2*np.pi, 36):
            x = center[0] + radius * np.cos(angle)
            y = center[1] + radius * np.sin(angle)
            points.append((x, y))
        return Polygon(points)
        
    # Add more entity types as needed
    return None

def test_dxf_completeness():
    """Test DXF file completeness preservation."""
    print("🔍 Тестирование полноты сохранения элементов DXF файлов")
    print("=" * 80)
    
    # Find some sample DXF files
    sample_files = []
    dxf_samples_path = "dxf_samples"
    
    if os.path.exists(dxf_samples_path):
        for root, dirs, files in os.walk(dxf_samples_path):
            for file in files:
                if file.lower().endswith('.dxf'):
                    sample_files.append(os.path.join(root, file))
                    if len(sample_files) >= 3:  # Limit to 3 files for testing
                        break
            if len(sample_files) >= 3:
                break
    
    if not sample_files:
        print("❌ Не найдены образцы DXF файлов в папке dxf_samples")
        return
    
    print(f"📋 Найдено {len(sample_files)} образцов DXF файлов для анализа")
    
    # Analyze original files
    original_analyses = []
    for i, file_path in enumerate(sample_files, 1):
        print(f"\n{'='*10} ОБРАЗЕЦ {i} {'='*10}")
        analysis = analyze_dxf_file(file_path, "(исходный)")
        if analysis:
            original_analyses.append((file_path, analysis))
    
    # Test output file creation
    print(f"\n\n{'='*20} ТЕСТ СОЗДАНИЯ ВЫХОДНОГО ФАЙЛА {'='*20}")
    
    if original_analyses:
        # Take the first file for testing
        test_file, test_analysis = original_analyses[0]
        
        print(f"\n🧪 Тестирование с файлом: {os.path.basename(test_file)}")
        
        # Simulate current parsing and output process
        try:
            from layout_optimizer import parse_dxf, save_dxf_layout
            
            # Parse DXF (current method)
            with open(test_file, 'rb') as f:
                parsed_polygon = parse_dxf(f, verbose=False)
            
            if parsed_polygon:
                print(f"\n📈 Результат текущего парсинга:")
                print(f"   • Получен один полигон, площадь: {parsed_polygon.area:.2f} мм²")
                print(f"   • Границы: {parsed_polygon.bounds}")
                print(f"   • Внешний контур: {len(parsed_polygon.exterior.coords)} точек")
                print(f"   • Внутренние отверстия: {len(parsed_polygon.interiors)}")
                
                # Create test output
                test_output = "test_output.dxf"
                placed_polygons = [(parsed_polygon, 0, 0, 0, "test_file.dxf", "серый")]  # x, y, angle, name, color
                sheet_size = (100, 100)  # 100x100 cm
                
                save_dxf_layout(placed_polygons, sheet_size, test_output)
                
                if os.path.exists(test_output):
                    print(f"\n📄 Создан тестовый выходной файл: {test_output}")
                    
                    # Analyze output file
                    output_analysis = analyze_dxf_file(test_output, "(выходной)")
                    
                    # Compare
                    print(f"\n📊 СРАВНЕНИЕ ИСХОДНОГО И ВЫХОДНОГО ФАЙЛОВ:")
                    print(f"   Исходный файл:")
                    print(f"     • Всего элементов: {test_analysis['total_entities']}")
                    print(f"     • Типов элементов: {len(test_analysis['entity_types'])}")
                    print(f"     • Геометрических: {len(test_analysis['polygons'])}")
                    print(f"     • Текстовых: {len(test_analysis['text_entities'])}")
                    print(f"     • Других: {len(test_analysis['other_entities'])}")
                    
                    if output_analysis:
                        print(f"   Выходной файл:")
                        print(f"     • Всего элементов: {output_analysis['total_entities']}")
                        print(f"     • Типов элементов: {len(output_analysis['entity_types'])}")
                        print(f"     • Геометрических: {len(output_analysis['polygons'])}")
                        print(f"     • Текстовых: {len(output_analysis['text_entities'])}")
                        print(f"     • Других: {len(output_analysis['other_entities'])}")
                    
                    print(f"\n⚠️ ПОТЕНЦИАЛЬНЫЕ ПОТЕРИ:")
                    lost_elements = []
                    
                    if test_analysis['text_entities']:
                        lost_elements.append(f"📝 {len(test_analysis['text_entities'])} текстовых элементов")
                    
                    if test_analysis['other_entities']:
                        lost_elements.append(f"❓ {len(test_analysis['other_entities'])} других элементов")
                    
                    if len(test_analysis['polygons']) > 1:
                        lost_elements.append(f"🔷 {len(test_analysis['polygons'])-1} отдельных полигонов объединены в один")
                    
                    if any(p['polygon'].interiors for p in test_analysis['polygons']):
                        lost_elements.append("🕳️ Внутренние отверстия полигонов")
                    
                    if lost_elements:
                        print("     ❌ Теряются:")
                        for loss in lost_elements:
                            print(f"        • {loss}")
                    else:
                        print("     ✅ Видимых потерь не обнаружено")
                    
                    # Clean up
                    os.remove(test_output)
                else:
                    print("❌ Не удалось создать выходной файл")
            else:
                print("❌ Не удалось распарсить исходный файл")
                
        except Exception as e:
            print(f"❌ Ошибка тестирования: {e}")
    else:
        print("❌ Нет данных для тестирования")

if __name__ == "__main__":
    test_dxf_completeness()