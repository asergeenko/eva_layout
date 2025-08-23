#!/usr/bin/env python3
"""
Тестируем parse_dxf_complete чтобы найти где происходит уменьшение
"""

import sys
sys.path.insert(0, '.')

import ezdxf
from layout_optimizer import parse_dxf_complete, convert_entity_to_polygon_improved
import os

def test_parse_complete():
    """Сравниваем размеры до и после parse_dxf_complete"""
    print("🔍 ТЕСТ parse_dxf_complete")
    print("=" * 60)
    
    tank_file = "dxf_samples/TANK 300/1.dxf"
    if not os.path.exists(tank_file):
        print(f"❌ Файл {tank_file} не найден!")
        return
    
    try:
        # ШАГ 1: Прямая конвертация каждого объекта
        print(f"\n📋 ШАГ 1: ПРЯМАЯ КОНВЕРТАЦИЯ ОБЪЕКТОВ")
        
        doc = ezdxf.readfile(tank_file)
        modelspace = doc.modelspace()
        
        individual_polygons = []
        for i, entity in enumerate(modelspace):
            polygon = convert_entity_to_polygon_improved(entity)
            if polygon and not polygon.is_empty:
                bounds = polygon.bounds
                width = bounds[2] - bounds[0]
                height = bounds[3] - bounds[1]
                individual_polygons.append(polygon)
                
                if i < 3:  # показываем первые 3
                    print(f"  Объект {i+1}: {width:.3f}×{height:.3f}")
                
        print(f"Всего индивидуальных полигонов: {len(individual_polygons)}")
        
        if individual_polygons:
            # Общие габариты всех полигонов
            all_bounds = []
            for poly in individual_polygons:
                all_bounds.extend([poly.bounds[0], poly.bounds[2]])  # x coords
            
            all_y_bounds = []
            for poly in individual_polygons:
                all_y_bounds.extend([poly.bounds[1], poly.bounds[3]])  # y coords
                
            individual_total_width = max(all_bounds) - min(all_bounds)
            individual_total_height = max(all_y_bounds) - min(all_y_bounds)
            print(f"  Общие габариты индивидуальных: {individual_total_width:.3f}×{individual_total_height:.3f}")
        
        # ШАГ 2: parse_dxf_complete
        print(f"\n📦 ШАГ 2: parse_dxf_complete")
        
        result = parse_dxf_complete(tank_file, verbose=False)  # отключаем verbose для чистоты вывода
        
        if 'polygons' in result and result['polygons']:
            print(f"  Полигонов через parse_dxf_complete: {len(result['polygons'])}")
            
            for i, poly in enumerate(result['polygons'][:3]):  # первые 3
                bounds = poly.bounds
                width = bounds[2] - bounds[0]
                height = bounds[3] - bounds[1]
                print(f"    Полигон {i+1}: {width:.3f}×{height:.3f}")
        
        # ШАГ 3: combined_polygon если есть
        if 'combined_polygon' in result and result['combined_polygon']:
            combined = result['combined_polygon']
            bounds = combined.bounds
            combined_width = bounds[2] - bounds[0]
            combined_height = bounds[3] - bounds[1]
            print(f"\n🔗 КОМБИНИРОВАННЫЙ ПОЛИГОН: {combined_width:.3f}×{combined_height:.3f}")
            print(f"   Bounds: ({bounds[0]:.3f}, {bounds[1]:.3f}, {bounds[2]:.3f}, {bounds[3]:.3f})")
            
            # СРАВНИВАЕМ С ИНДИВИДУАЛЬНЫМИ
            if individual_polygons:
                scale_factor_w = combined_width / individual_total_width if individual_total_width > 0 else 1
                scale_factor_h = combined_height / individual_total_height if individual_total_height > 0 else 1
                
                print(f"\n📊 СРАВНЕНИЕ:")
                print(f"  Индивидуальные габариты: {individual_total_width:.3f}×{individual_total_height:.3f}")
                print(f"  Комбинированный: {combined_width:.3f}×{combined_height:.3f}")
                print(f"  Коэффициент изменения: ширина={scale_factor_w:.6f}, высота={scale_factor_h:.6f}")
                
                if scale_factor_w < 0.1 or scale_factor_h < 0.1:
                    print(f"  ⚠️ НАЙДЕНО МАСШТАБИРОВАНИЕ! Объекты уменьшились в {1/min(scale_factor_w, scale_factor_h):.1f} раз")
                
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_parse_complete()