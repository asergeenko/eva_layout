#!/usr/bin/env python3

import sys
import os
sys.path.append('/home/sasha/proj/2025/eva_layout')

from layout_optimizer import parse_dxf_complete, bin_packing
import ezdxf
import matplotlib.pyplot as plt
from shapely.geometry import Polygon
import math

def analyze_coordinate_mismatch(dxf_path):
    """
    Анализируем рассогласование координат между:
    1. Полигонами, используемыми для размещения (visualization)
    2. SPLINE элементами в итоговом DXF файле
    """
    
    print(f"🔍 АНАЛИЗ КООРДИНАТНОГО РАССОГЛАСОВАНИЯ")
    print(f"📁 DXF файл: {dxf_path}")
    
    if not os.path.exists(dxf_path):
        print(f"❌ Файл не найден: {dxf_path}")
        return False
    
    try:
        # Открываем DXF файл
        doc = ezdxf.readfile(dxf_path)
        msp = doc.modelspace()
        
        # Группируем элементы по слоям
        elements_by_layer = {}
        
        for entity in msp:
            layer = entity.dxf.layer if hasattr(entity.dxf, 'layer') else 'DEFAULT'
            
            if layer not in elements_by_layer:
                elements_by_layer[layer] = []
            
            if entity.dxftype() == 'SPLINE':
                elements_by_layer[layer].append({
                    'type': 'SPLINE',
                    'entity': entity,
                    'color': entity.dxf.color if hasattr(entity.dxf, 'color') else 7
                })
        
        print(f"\n📋 Найденные слои:")
        for layer, elements in elements_by_layer.items():
            print(f"   🎨 {layer}: {len(elements)} элементов")
        
        # Находим внешние (красные) слои - они определяют границы для коллизий
        red_layers = []
        for layer, elements in elements_by_layer.items():
            for elem in elements:
                if elem['color'] == 1:  # Красный цвет
                    red_layers.append(layer)
                    break
        
        print(f"\n🔴 Красные слои (внешние границы): {red_layers}")
        
        # Для каждого красного слоя строим полигон и сравниваем с boundary
        for layer in red_layers:
            print(f"\n🔍 Анализ слоя '{layer}':")
            
            splines = [elem for elem in elements_by_layer[layer] if elem['type'] == 'SPLINE']
            print(f"   📐 SPLINE элементов: {len(splines)}")
            
            # Извлекаем все точки из SPLINE элементов
            all_points = []
            spline_bounds = {'min_x': float('inf'), 'max_x': float('-inf'), 
                           'min_y': float('inf'), 'max_y': float('-inf')}
            
            for spline_data in splines:
                spline = spline_data['entity']
                if hasattr(spline, 'control_points') and spline.control_points:
                    for cp in spline.control_points:
                        if hasattr(cp, 'x') and hasattr(cp, 'y'):
                            x, y = cp.x, cp.y
                        elif len(cp) >= 2:
                            x, y = float(cp[0]), float(cp[1])
                        else:
                            continue
                            
                        all_points.append((x, y))
                        spline_bounds['min_x'] = min(spline_bounds['min_x'], x)
                        spline_bounds['max_x'] = max(spline_bounds['max_x'], x)
                        spline_bounds['min_y'] = min(spline_bounds['min_y'], y)
                        spline_bounds['max_y'] = max(spline_bounds['max_y'], y)
            
            if all_points:
                # Вычисляем центр и размеры по SPLINE точкам
                spline_center_x = (spline_bounds['min_x'] + spline_bounds['max_x']) / 2
                spline_center_y = (spline_bounds['min_y'] + spline_bounds['max_y']) / 2
                spline_width = spline_bounds['max_x'] - spline_bounds['min_x']
                spline_height = spline_bounds['max_y'] - spline_bounds['min_y']
                
                print(f"   📊 SPLINE центр: ({spline_center_x:.1f}, {spline_center_y:.1f})")
                print(f"   📏 SPLINE размер: {spline_width:.1f} x {spline_height:.1f} мм")
                
                # Находим соответствующий элемент в visualization
                print(f"   🎯 Этот элемент в visualization должен иметь примерно такие же координаты")
                
    except Exception as e:
        print(f"❌ Ошибка анализа DXF: {e}")
        return False
    
    return True

def recreate_visualization_with_actual_coordinates():
    """
    Создаем visualization с теми же координатами, что используются в DXF
    """
    
    print(f"\n🎨 СОЗДАНИЕ ТОЧНОЙ ВИЗУАЛИЗАЦИИ")
    
    # Загружаем исходные файлы и запускаем bin_packing
    test_files = [
        'dxf_samples/SUBARU FORESTER 3 дорестайлинг/1.dxf',
        'dxf_samples/TOYOTA FORTUNER/2.dxf', 
        'dxf_samples/SUZUKI XBEE/1.dxf',
        'dxf_samples/2.dxf',
        'dxf_samples/TOYOTA FORTUNER/1.dxf'
    ]
    
    polygons_for_packing = []
    original_dxf_data_map = {}
    
    for file_path in test_files:
        if os.path.exists(file_path):
            result = parse_dxf_complete(file_path, verbose=False)
            polygon = result.get('combined_polygon')
            
            if polygon:
                polygons_for_packing.append((polygon, file_path, "black", 1))
                original_dxf_data_map[file_path] = result
    
    if len(polygons_for_packing) >= 2:
        placed_elements, unplaced_elements = bin_packing(polygons_for_packing, (200, 140))
        
        print(f"   ✅ Размещено элементов: {len(placed_elements)}")
        
        # Создаем visualization с фактическими SPLINE координатами
        fig, ax = plt.subplots(figsize=(16, 12))
        
        for i, element in enumerate(placed_elements):
            transformed_polygon, x_offset, y_offset, rotation_angle, file_name, color, order_id = element
            
            # Получаем оригинальные данные
            original_data_key = None
            file_basename = os.path.basename(file_name) if isinstance(file_name, str) else str(file_name)
            
            for key in original_dxf_data_map.keys():
                if os.path.basename(key) == file_basename:
                    original_data_key = key
                    break
            
            if not original_data_key:
                continue
                
            original_data = original_dxf_data_map[original_data_key]
            
            # Применяем ту же трансформацию, что и для SPLINE элементов
            original_polygon = original_data['combined_polygon']
            orig_bounds = original_polygon.bounds
            final_bounds = transformed_polygon.bounds
            
            # Центры для трансформации
            orig_center_x = (orig_bounds[0] + orig_bounds[2]) / 2
            orig_center_y = (orig_bounds[1] + orig_bounds[3]) / 2
            final_center_x = (final_bounds[0] + final_bounds[2]) / 2
            final_center_y = (final_bounds[1] + final_bounds[3]) / 2
            
            print(f"   🔄 Элемент {i+1}: {file_basename}")
            print(f"      📍 Исходный центр полигона: ({orig_center_x:.1f}, {orig_center_y:.1f})")
            print(f"      📍 Финальный центр полигона: ({final_center_x:.1f}, {final_center_y:.1f})")
            
            # Строим полигон ИЗ ТРАНСФОРМИРОВАННЫХ SPLINE КООРДИНАТ
            spline_polygon_points = []
            
            for entity_data in original_data['original_entities']:
                if entity_data['type'] == 'SPLINE' and entity_data.get('color') == 1:  # Только красные SPLINE
                    entity = entity_data['entity']
                    if hasattr(entity, 'control_points') and entity.control_points:
                        for cp in entity.control_points:
                            if hasattr(cp, 'x') and hasattr(cp, 'y'):
                                x, y = cp.x, cp.y
                            elif len(cp) >= 2:
                                x, y = float(cp[0]), float(cp[1])
                            else:
                                continue
                            
                            # ТОЧНО ТА ЖЕ ТРАНСФОРМАЦИЯ, что применяется к SPLINE в DXF
                            # 1. Перенос в начало координат
                            tx = x - orig_center_x
                            ty = y - orig_center_y
                            
                            # 2. Поворот
                            if rotation_angle != 0:
                                angle_rad = math.radians(rotation_angle)
                                cos_angle = math.cos(angle_rad)
                                sin_angle = math.sin(angle_rad)
                                
                                rotated_x = tx * cos_angle - ty * sin_angle
                                rotated_y = tx * sin_angle + ty * cos_angle
                            else:
                                rotated_x = tx
                                rotated_y = ty
                            
                            # 3. Перенос к финальной позиции
                            final_x = rotated_x + final_center_x
                            final_y = rotated_y + final_center_y
                            
                            spline_polygon_points.append((final_x, final_y))
            
            if spline_polygon_points and len(spline_polygon_points) >= 3:
                try:
                    spline_polygon = Polygon(spline_polygon_points)
                    if spline_polygon.is_valid:
                        # Рисуем полигон из SPLINE координат
                        x_coords, y_coords = spline_polygon.exterior.xy
                        ax.plot(x_coords, y_coords, 'r-', linewidth=2, alpha=0.8)
                        ax.fill(x_coords, y_coords, color='red', alpha=0.3)
                        
                        # Добавляем подпись
                        centroid = spline_polygon.centroid
                        ax.text(centroid.x, centroid.y, f"SPLINE {i+1}", 
                               ha='center', va='center', fontsize=8, fontweight='bold')
                        
                        print(f"      ✅ SPLINE полигон создан из {len(spline_polygon_points)} точек")
                    else:
                        print(f"      ❌ SPLINE полигон некорректный")
                except Exception as e:
                    print(f"      ❌ Ошибка создания SPLINE полигона: {e}")
            else:
                print(f"      ⚠️ Недостаточно SPLINE точек для создания полигона")
            
            # Для сравнения рисуем оригинальный полигон (пунктиром)
            orig_x, orig_y = transformed_polygon.exterior.xy
            ax.plot(orig_x, orig_y, '--', color='blue', linewidth=1, alpha=0.5)
        
        ax.set_xlim(0, 1400)
        ax.set_ylim(0, 2000)
        ax.set_xlabel('Ширина (мм)')
        ax.set_ylabel('Высота (мм)')
        ax.set_title('ТОЧНАЯ ВИЗУАЛИЗАЦИЯ: Красные = SPLINE границы, Синий пунктир = polygon границы')
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig('accurate_visualization.png', dpi=150, bbox_inches='tight')
        print(f"\n💾 Точная визуализация сохранена: accurate_visualization.png")
        
        return True
    
    return False

def main():
    """Основная функция"""
    
    print("🔍 АНАЛИЗ РАСХОЖДЕНИЯ МЕЖДУ VISUALIZATION И DXF")
    
    # 1. Анализируем координаты в итоговом DXF
    dxf_success = analyze_coordinate_mismatch('200_140_9_black.dxf')
    
    # 2. Создаем точную визуализацию
    viz_success = recreate_visualization_with_actual_coordinates()
    
    if dxf_success and viz_success:
        print(f"\n🎯 АНАЛИЗ ЗАВЕРШЕН!")
        print(f"📊 Проверьте accurate_visualization.png - должна совпадать с autodesk.png")
        print(f"🔧 Если они не совпадают, значит проблема в трансформации координат")
    else:
        print(f"\n❌ Ошибка в анализе")

if __name__ == "__main__":
    main()