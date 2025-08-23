#!/usr/bin/env python3
"""
Полная диагностика всех проблем: наложения, визуализация, единицы измерения
"""

import sys
sys.path.insert(0, '.')

import os
import tempfile
import ezdxf
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPolygon
from io import BytesIO
from layout_optimizer import (
    parse_dxf_complete, bin_packing, save_dxf_layout_complete, 
    plot_layout
)

def comprehensive_debug():
    """Полная диагностика всех проблем"""
    print("🔍 КОМПЛЕКСНАЯ ДИАГНОСТИКА ВСЕХ ПРОБЛЕМ")
    print("=" * 70)
    
    # Тестируем с файлами TANK 300/1.dxf и 4.dxf
    tank_files = [
        "dxf_samples/TANK 300/1.dxf",
        "dxf_samples/TANK 300/4.dxf"
    ]
    
    for tank_file in tank_files:
        if not os.path.exists(tank_file):
            print(f"❌ Файл {tank_file} не найден!")
            continue
            
        print(f"\n" + "="*50)
        print(f"📋 АНАЛИЗ ФАЙЛА: {os.path.basename(tank_file)}")
        print("="*50)
        
        try:
            # 1. Анализ исходного DXF
            print(f"\n🔍 ШАГ 1: АНАЛИЗ ИСХОДНОГО DXF")
            
            doc = ezdxf.readfile(tank_file)
            modelspace = doc.modelspace()
            entities = list(modelspace)
            
            print(f"  Исходных объектов: {len(entities)}")
            
            # Единицы измерения
            units = doc.header.get('$INSUNITS', 0)
            units_map = {0: 'Unitless', 1: 'Inches', 2: 'Feet', 4: 'Millimeters', 5: 'Centimeters', 6: 'Meters'}
            print(f"  Единицы измерения в DXF: {units_map.get(units, f'Unknown ({units})')}")
            
            # Общие габариты исходного DXF
            all_x, all_y = [], []
            for entity in entities:
                try:
                    bbox = entity.bbox()
                    if bbox:
                        all_x.extend([bbox.extmin.x, bbox.extmax.x])
                        all_y.extend([bbox.extmin.y, bbox.extmax.y])
                except:
                    pass
            
            if all_x and all_y:
                orig_width = max(all_x) - min(all_x)
                orig_height = max(all_y) - min(all_y)
                print(f"  Исходные габариты DXF: {orig_width:.1f}×{orig_height:.1f} единиц")
                print(f"  Диапазон X: {min(all_x):.1f} - {max(all_x):.1f}")
                print(f"  Диапазон Y: {min(all_y):.1f} - {max(all_y):.1f}")
            else:
                orig_width = 0
                orig_height = 0
                print(f"  ❌ Не удалось получить границы исходного DXF")
            
            # 2. Парсинг через parse_dxf_complete
            print(f"\n📦 ШАГ 2: ПАРСИНГ ЧЕРЕЗ parse_dxf_complete")
            
            result = parse_dxf_complete(tank_file, verbose=False)
            
            print(f"  Полигонов для визуализации: {len(result.get('polygons', []))}")
            print(f"  Исходных объектов: {len(result.get('original_entities', []))}")
            print(f"  Главный слой: {result.get('bottom_layer_name')}")
            
            # Анализ полигонов
            if result.get('polygons'):
                total_area = sum(p.area for p in result['polygons'])
                print(f"  Общая площадь полигонов: {total_area:.0f}")
                
                # Габариты всех полигонов
                all_bounds = []
                for poly in result['polygons']:
                    all_bounds.append(poly.bounds)
                
                if all_bounds:
                    min_x = min(b[0] for b in all_bounds)
                    max_x = max(b[2] for b in all_bounds)
                    min_y = min(b[1] for b in all_bounds)
                    max_y = max(b[3] for b in all_bounds)
                    
                    parsed_width = max_x - min_x
                    parsed_height = max_y - min_y
                    
                    print(f"  Габариты всех полигонов: {parsed_width:.1f}×{parsed_height:.1f}")
                    print(f"  Диапазон X: {min_x:.1f} - {max_x:.1f}")
                    print(f"  Диапазон Y: {min_y:.1f} - {max_y:.1f}")
                    
                    # Проверяем масштабирование при парсинге
                    if orig_width > 0 and parsed_width > 0:
                        scale_factor = parsed_width / orig_width
                        print(f"  Коэффициент масштабирования при парсинге: {scale_factor:.4f}")
                        
                        if abs(scale_factor - 1.0) > 0.01:
                            print(f"  ⚠️ МАСШТАБИРОВАНИЕ ПРИ ПАРСИНГЕ: {scale_factor:.4f}")
                        else:
                            print(f"  ✅ Парсинг без масштабирования")
            
            # 3. Тест размещения
            print(f"\n🎯 ШАГ 3: ТЕСТ РАЗМЕЩЕНИЯ")
            
            if not result.get('polygons'):
                print("  ❌ Нет полигонов для размещения!")
                continue
            
            # Находим самый большой полигон (внешний контур) для тестирования
            largest_poly = max(result['polygons'], key=lambda p: p.area)
            largest_idx = result['polygons'].index(largest_poly)
            
            print(f"  Выбран полигон {largest_idx} (самый большой, площадь: {largest_poly.area:.0f})")
            bounds = largest_poly.bounds
            print(f"  Размер: {bounds[2]-bounds[0]:.1f}×{bounds[3]-bounds[1]:.1f}мм")
            
            # Создаем простое размещение - 2 одинаковых объекта через настоящий алгоритм
            polygons_with_names = [
                (largest_poly, "test1.dxf", "черный", 1),
                (largest_poly, "test2.dxf", "черный", 2)
            ]
            
            sheet_size = (140, 200)  # 140×200 см
            placed, unplaced = bin_packing(polygons_with_names, sheet_size, verbose=True)
            
            print(f"  Размещенных объектов: {len(placed)}")
            print(f"  Неразмещенных: {len(unplaced)}")
            
            if len(placed) >= 2:
                # Анализируем позиции размещения
                pos1 = placed[0]  # (polygon, x_offset, y_offset, rotation, filename, color)
                pos2 = placed[1]
                
                # Координаты центров в визуализации
                p1_bounds = pos1[0].bounds
                p2_bounds = pos2[0].bounds
                
                p1_center_x = (p1_bounds[0] + p1_bounds[2]) / 2
                p1_center_y = (p1_bounds[1] + p1_bounds[3]) / 2
                p2_center_x = (p2_bounds[0] + p2_bounds[2]) / 2
                p2_center_y = (p2_bounds[1] + p2_bounds[3]) / 2
                
                viz_distance = ((p2_center_x - p1_center_x)**2 + (p2_center_y - p1_center_y)**2)**0.5
                
                print(f"  Позиция 1: центр ({p1_center_x:.1f}, {p1_center_y:.1f})")
                print(f"  Позиция 2: центр ({p2_center_x:.1f}, {p2_center_y:.1f})")
                print(f"  Расстояние в визуализации: {viz_distance:.1f}мм")
                
            # 4. Сохранение в DXF и анализ
            print(f"\n💾 ШАГ 4: СОХРАНЕНИЕ В DXF И АНАЛИЗ")
            
            if placed:
                original_dxf_data_map = {}
                for p in placed:
                    original_dxf_data_map[p[4]] = result
                
                with tempfile.NamedTemporaryFile(suffix='.dxf', delete=False) as tmp_file:
                    output_path = tmp_file.name
                
                save_dxf_layout_complete(placed, sheet_size, output_path, original_dxf_data_map, verbose=False)
                
                # Анализируем созданный DXF
                saved_doc = ezdxf.readfile(output_path)
                saved_msp = saved_doc.modelspace()
                saved_entities = list(saved_msp)
                
                print(f"  Сохраненных объектов: {len(saved_entities)}")
                
                # Группируем по слоям (файлам)
                layers_info = {}
                for entity in saved_entities:
                    if entity.dxftype() == 'SPLINE':
                        layer = getattr(entity.dxf, 'layer', '0')
                        base_layer = layer.split('_')[-1] if '_' in layer else layer  # извлекаем базовый слой
                        
                        if layer not in layers_info:
                            layers_info[layer] = {'entities': [], 'base_layer': base_layer}
                        layers_info[layer]['entities'].append(entity)
                
                print(f"  Слоев со SPLINE: {len(layers_info)}")
                
                # Анализируем расстояния между файлами в DXF
                file1_layers = [l for l in layers_info.keys() if l.startswith('test1')]
                file2_layers = [l for l in layers_info.keys() if l.startswith('test2')]
                
                if file1_layers and file2_layers:
                    # Берем первый слой каждого файла для сравнения
                    layer1 = file1_layers[0]
                    layer2 = file2_layers[0]
                    
                    def get_layer_center(layer):
                        entities = layers_info[layer]['entities']
                        if entities:
                            entity = entities[0]
                            if hasattr(entity, 'control_points') and entity.control_points:
                                cp = entity.control_points[0]
                                if hasattr(cp, 'x'):
                                    return cp.x, cp.y
                                else:
                                    return cp[0], cp[1]
                        return None, None
                    
                    dxf_c1_x, dxf_c1_y = get_layer_center(layer1)
                    dxf_c2_x, dxf_c2_y = get_layer_center(layer2)
                    
                    if dxf_c1_x is not None and dxf_c2_x is not None:
                        dxf_distance = ((dxf_c2_x - dxf_c1_x)**2 + (dxf_c2_y - dxf_c1_y)**2)**0.5
                        
                        print(f"  DXF позиция 1: ({dxf_c1_x:.1f}, {dxf_c1_y:.1f})")
                        print(f"  DXF позиция 2: ({dxf_c2_x:.1f}, {dxf_c2_y:.1f})")
                        print(f"  Расстояние в DXF: {dxf_distance:.1f}мм")
                        
                        # Сравниваем расстояния
                        if 'viz_distance' in locals() and viz_distance > 0 and dxf_distance > 0:
                            ratio = dxf_distance / viz_distance
                            print(f"  Соотношение расстояний (DXF/Визуализация): {ratio:.4f}")
                            
                            if abs(ratio - 1.0) > 0.1:
                                print(f"  ❌ РАСХОЖДЕНИЕ В РАССТОЯНИЯХ: {ratio:.4f}")
                            else:
                                print(f"  ✅ Расстояния совпадают")
                        
                        # Проверяем наложения
                        if dxf_distance < 100:  # меньше 10см
                            print(f"  🚨 НАЛОЖЕНИЯ В DXF! Расстояние {dxf_distance:.1f}мм < 100мм")
                        elif dxf_distance < 200:  # меньше 20см
                            print(f"  ⚠️ Возможные наложения в DXF: {dxf_distance:.1f}мм")
                        else:
                            print(f"  ✅ Нет наложений в DXF")
                
                # Очистка
                try:
                    os.unlink(output_path)
                except:
                    pass
            
        except Exception as e:
            print(f"❌ Ошибка анализа {tank_file}: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    comprehensive_debug()