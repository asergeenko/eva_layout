#!/usr/bin/env python3
"""
Диагностика проблемы трансформации SPLINE элементов в DXF
"""

import sys
sys.path.insert(0, '.')

import os
import tempfile
import ezdxf
from layout_optimizer import parse_dxf_complete, bin_packing, save_dxf_layout_complete

def debug_transformation_problem():
    """Диагностируем проблему трансформации"""
    print("🔍 ДИАГНОСТИКА ПРОБЛЕМЫ ТРАНСФОРМАЦИИ SPLINE")
    print("=" * 60)
    
    # Используем один файл из TANK 300 для простоты
    tank_file = "dxf_samples/TANK 300/1.dxf"
    if not os.path.exists(tank_file):
        print(f"❌ Файл {tank_file} не найден!")
        return
    
    try:
        # 1. Парсим файл
        print(f"\n📋 ШАГ 1: ПАРСИНГ")
        result = parse_dxf_complete(tank_file, verbose=False)
        
        print(f"  Полигонов: {len(result['polygons'])}")
        print(f"  Исходных объектов: {len(result['original_entities'])}")
        
        if result['polygons']:
            first_poly = result['polygons'][0]
            bounds = first_poly.bounds
            print(f"  Первый полигон: {bounds[2]-bounds[0]:.1f}×{bounds[3]-bounds[1]:.1f}")
            print(f"  Bounds: ({bounds[0]:.1f}, {bounds[1]:.1f}, {bounds[2]:.1f}, {bounds[3]:.1f})")
        
        # 2. Создаем простое размещение - два одинаковых объекта рядом
        print(f"\n📦 ШАГ 2: СОЗДАНИЕ ТЕСТОВОГО РАЗМЕЩЕНИЯ")
        
        if not result['polygons']:
            print("❌ Нет полигонов для тестирования!")
            return
            
        test_poly = result['polygons'][0]
        
        # Создаем два размещения: одно в (100, 100), другое в (500, 100)
        placed = [
            (test_poly, 100, 100, 0, "test1.dxf", "черный"),
            (test_poly, 500, 100, 0, "test2.dxf", "черный") 
        ]
        
        print(f"  Создано размещений: {len(placed)}")
        print(f"  Размещение 1: x=100, y=100")
        print(f"  Размещение 2: x=500, y=100")
        print(f"  Расстояние между центрами: 400мм")
        
        # 3. Сохраняем в DXF
        print(f"\n💾 ШАГ 3: СОХРАНЕНИЕ В DXF")
        
        original_dxf_data_map = {
            "test1.dxf": result,
            "test2.dxf": result
        }
        
        with tempfile.NamedTemporaryFile(suffix='.dxf', delete=False) as tmp_file:
            output_path = tmp_file.name
        
        save_dxf_layout_complete(placed, (140, 200), output_path, original_dxf_data_map, verbose=False)
        print(f"  DXF сохранен: {output_path}")
        
        # 4. Анализируем результат
        print(f"\n📊 ШАГ 4: АНАЛИЗ РЕЗУЛЬТАТА")
        
        saved_doc = ezdxf.readfile(output_path)
        saved_msp = saved_doc.modelspace()
        
        # Группируем SPLINE элементы по слоям (файлам)
        splines_by_layer = {}
        for entity in saved_msp:
            if entity.dxftype() == 'SPLINE':
                layer = getattr(entity.dxf, 'layer', '0')
                if layer not in splines_by_layer:
                    splines_by_layer[layer] = []
                splines_by_layer[layer].append(entity)
        
        print(f"  Найдено слоев со SPLINE: {len(splines_by_layer)}")
        
        # Анализируем координаты для каждого слоя (файла)
        for layer, splines in splines_by_layer.items():
            print(f"\n    СЛОЙ: {layer}")
            print(f"      SPLINE объектов: {len(splines)}")
            
            if splines:
                # Анализируем первый SPLINE в этом слое
                spline = splines[0]
                if hasattr(spline, 'control_points') and spline.control_points:
                    first_cp = spline.control_points[0]
                    if hasattr(first_cp, 'x'):
                        x, y = first_cp.x, first_cp.y
                    else:
                        x, y = first_cp[0], first_cp[1]
                    
                    print(f"      Первая контрольная точка: ({x:.1f}, {y:.1f})")
                    
                    # Находим границы всех SPLINE в этом слое
                    all_x, all_y = [], []
                    for s in splines:
                        if hasattr(s, 'control_points') and s.control_points:
                            for cp in s.control_points:
                                if hasattr(cp, 'x'):
                                    all_x.append(cp.x)
                                    all_y.append(cp.y)
                                else:
                                    all_x.append(cp[0])
                                    all_y.append(cp[1])
                    
                    if all_x and all_y:
                        min_x, max_x = min(all_x), max(all_x)
                        min_y, max_y = min(all_y), max(all_y)
                        width = max_x - min_x
                        height = max_y - min_y
                        center_x = (min_x + max_x) / 2
                        center_y = (min_y + max_y) / 2
                        
                        print(f"      Границы: ({min_x:.1f}, {min_y:.1f}) - ({max_x:.1f}, {max_y:.1f})")
                        print(f"      Размер: {width:.1f}×{height:.1f}")
                        print(f"      Центр: ({center_x:.1f}, {center_y:.1f})")
        
        # 5. Проверяем расстояния между объектами
        print(f"\n🔍 ШАГ 5: ПРОВЕРКА РАССТОЯНИЙ")
        
        layer_names = list(splines_by_layer.keys())
        # ИСПРАВЛЕНО: Сравниваем одинаковые слои разных объектов
        test1_layers = [l for l in layer_names if l.startswith('test1_')]
        test2_layers = [l for l in layer_names if l.startswith('test2_')]
        
        if test1_layers and test2_layers:
            # Находим соответствующие слои для сравнения
            matching_pairs = []
            for t1_layer in test1_layers:
                layer_suffix = t1_layer.replace('test1_', '')
                t2_layer = f'test2_{layer_suffix}'
                if t2_layer in test2_layers:
                    matching_pairs.append((t1_layer, t2_layer))
            
            if matching_pairs:
                # Анализируем первую пару
                t1_layer, t2_layer = matching_pairs[0]
                
                def get_layer_center(layer):
                    splines = splines_by_layer[layer]
                    all_x, all_y = [], []
                    for s in splines:
                        if hasattr(s, 'control_points') and s.control_points:
                            for cp in s.control_points:
                                if hasattr(cp, 'x'):
                                    all_x.append(cp.x)
                                    all_y.append(cp.y)
                                else:
                                    all_x.append(cp[0])
                                    all_y.append(cp[1])
                    
                    if all_x and all_y:
                        return (min(all_x) + max(all_x)) / 2, (min(all_y) + max(all_y)) / 2
                    return None, None
                
                c1_x, c1_y = get_layer_center(t1_layer)
                c2_x, c2_y = get_layer_center(t2_layer)
                
                if c1_x is not None and c2_x is not None:
                    distance = ((c2_x - c1_x)**2 + (c2_y - c1_y)**2)**0.5
                    
                    print(f"  Центр объекта 1 ({t1_layer}): ({c1_x:.1f}, {c1_y:.1f})")
                    print(f"  Центр объекта 2 ({t2_layer}): ({c2_x:.1f}, {c2_y:.1f})")
                    print(f"  Расстояние между центрами: {distance:.1f}мм")
                    print(f"  Ожидалось: 400мм")
                
                if abs(distance - 400) < 50:
                    print(f"  ✅ РАССТОЯНИЕ ПРАВИЛЬНОЕ")
                else:
                    print(f"  ❌ НЕПРАВИЛЬНОЕ РАССТОЯНИЕ! Разница: {abs(distance - 400):.1f}мм")
                    
                    if distance < 100:
                        print(f"  🚨 ОБЪЕКТЫ НАКЛАДЫВАЮТСЯ! (расстояние < 100мм)")
        
        # Очистка
        try:
            os.unlink(output_path)
        except:
            pass
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_transformation_problem()