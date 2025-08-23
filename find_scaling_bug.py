#!/usr/bin/env python3
"""
Ищем где именно теряется масштаб - пошагово проверяем каждую функцию
"""

import sys
sys.path.insert(0, '.')

import ezdxf
from layout_optimizer import convert_entity_to_polygon_improved, parse_dxf_complete
import os

def find_scaling_bug():
    """Пошагово находим где теряется размер"""
    print("🔍 ПОИСК МЕСТА ПОТЕРИ МАСШТАБА")
    print("=" * 60)
    
    tank_file = "dxf_samples/TANK 300/1.dxf"
    if not os.path.exists(tank_file):
        print(f"❌ Файл {tank_file} не найден!")
        return
    
    # ШАГ 1: Исходные размеры в DXF
    print(f"\n📋 ШАГ 1: ИСХОДНЫЕ РАЗМЕРЫ В DXF")
    try:
        doc = ezdxf.readfile(tank_file)
        modelspace = doc.modelspace()
        
        # Находим общие габариты
        all_x, all_y = [], []
        entities = list(modelspace)
        
        for entity in entities:
            try:
                bbox = entity.bbox()
                if bbox:
                    all_x.extend([bbox.extmin.x, bbox.extmax.x])
                    all_y.extend([bbox.extmin.y, bbox.extmax.y])
            except:
                pass
        
        if all_x and all_y:
            original_width = max(all_x) - min(all_x)
            original_height = max(all_y) - min(all_y)
            print(f"  Исходные габариты: {original_width:.2f}×{original_height:.2f} единиц")
            print(f"  Диапазон X: {min(all_x):.2f} - {max(all_x):.2f}")
            print(f"  Диапазон Y: {min(all_y):.2f} - {max(all_y):.2f}")
            
            # ШАГ 2: После convert_entity_to_polygon_improved для каждого объекта
            print(f"\n🔄 ШАГ 2: ПОСЛЕ КОНВЕРТАЦИИ ОТДЕЛЬНЫХ ОБЪЕКТОВ")
            
            converted_polygons = []
            for i, entity in enumerate(entities):
                try:
                    polygon = convert_entity_to_polygon_improved(entity)
                    if polygon and not polygon.is_empty:
                        bounds = polygon.bounds
                        width = bounds[2] - bounds[0]
                        height = bounds[3] - bounds[1]
                        converted_polygons.append(polygon)
                        print(f"    Объект {i+1} ({entity.dxftype()}): {width:.2f}×{height:.2f}")
                        print(f"      Bounds: {bounds}")
                        
                        if i == 0:  # для первого объекта проверяем подробно
                            print(f"      🎯 ПЕРВЫЙ ОБЪЕКТ ДЕТАЛЬНО:")
                            # Сравниваем с исходным bbox
                            orig_bbox = entity.bbox()
                            if orig_bbox:
                                orig_w = orig_bbox.extmax.x - orig_bbox.extmin.x
                                orig_h = orig_bbox.extmax.y - orig_bbox.extmin.y
                                print(f"        Исходный bbox: {orig_w:.2f}×{orig_h:.2f}")
                                print(f"        После конвертации: {width:.2f}×{height:.2f}")
                                scale_factor = width / orig_w if orig_w > 0 else 1
                                print(f"        Коэффициент изменения: {scale_factor:.6f}")
                        
                        if i >= 5:  # ограничиваем вывод
                            break
                            
                except Exception as e:
                    print(f"    Объект {i+1}: ошибка конвертации - {e}")
            
            # ШАГ 3: Полный parse_dxf_complete
            print(f"\n📦 ШАГ 3: ПОЛНЫЙ ПАРСИНГ parse_dxf_complete")
            result = parse_dxf_complete(tank_file)
            if 'polygons' in result and result['polygons']:
                poly = result['polygons'][0]
                bounds = poly.bounds
                final_width = bounds[2] - bounds[0]
                final_height = bounds[3] - bounds[1]
                print(f"  Финальный размер первого полигона: {final_width:.2f}×{final_height:.2f}")
                
                # Сравниваем с исходным и промежуточным
                if converted_polygons:
                    conv_bounds = converted_polygons[0].bounds
                    conv_width = conv_bounds[2] - conv_bounds[0]
                    conv_height = conv_bounds[3] - conv_bounds[1]
                    
                    print(f"\n🔍 СРАВНЕНИЕ:")
                    print(f"  Исходный DXF: {original_width:.2f}×{original_height:.2f}")
                    print(f"  После convert_entity_to_polygon_improved: {conv_width:.2f}×{conv_height:.2f}")
                    print(f"  После parse_dxf_complete: {final_width:.2f}×{final_height:.2f}")
                    
                    # Коэффициенты изменения
                    scale1 = conv_width / original_width if original_width > 0 else 1
                    scale2 = final_width / conv_width if conv_width > 0 else 1
                    scale_total = final_width / original_width if original_width > 0 else 1
                    
                    print(f"\n📊 КОЭФФИЦИЕНТЫ МАСШТАБИРОВАНИЯ:")
                    print(f"  DXF → convert_entity: ×{scale1:.6f}")
                    print(f"  convert_entity → parse_complete: ×{scale2:.6f}")
                    print(f"  Общий: ×{scale_total:.6f}")
                    
                    if scale1 < 0.1:
                        print(f"  ⚠️ БОЛЬШАЯ ПОТЕРЯ МАСШТАБА в convert_entity_to_polygon_improved!")
                    elif scale2 < 0.1:
                        print(f"  ⚠️ БОЛЬШАЯ ПОТЕРЯ МАСШТАБА в parse_dxf_complete!")
                    elif scale_total < 0.1:
                        print(f"  ⚠️ ОБЩАЯ ПОТЕРЯ МАСШТАБА слишком велика!")
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    find_scaling_bug()