#!/usr/bin/env python3
"""
Отладка координат SPLINE элементов.
"""

import ezdxf
import numpy as np
from layout_optimizer import parse_dxf_complete
from shapely.geometry import Polygon

def debug_spline_coordinates():
    """Отлаживает координаты SPLINE элементов."""
    print("=== ОТЛАДКА КООРДИНАТ SPLINE ЭЛЕМЕНТОВ ===")
    
    source_dxf = "/home/sasha/proj/2025/eva_layout/200_140_1_black.dxf"
    
    # 1. Анализируем реальные SPLINE элементы в DXF
    print(f"\\n📁 Анализируем реальные SPLINE в: {source_dxf}")
    
    doc = ezdxf.readfile(source_dxf)
    msp = doc.modelspace()
    
    real_splines = [e for e in msp if e.dxftype() == 'SPLINE']
    print(f"  Найдено SPLINE'ов: {len(real_splines)}")
    
    # Извлекаем bounds всех реальных SPLINE'ов
    all_real_xs = []
    all_real_ys = []
    
    for i, spline in enumerate(real_splines):
        try:
            control_points = spline.control_points
            if control_points:
                for cp in control_points:
                    if hasattr(cp, 'x') and hasattr(cp, 'y'):
                        all_real_xs.append(cp.x)
                        all_real_ys.append(cp.y)
                    elif len(cp) >= 2:
                        all_real_xs.append(float(cp[0]))
                        all_real_ys.append(float(cp[1]))
        except Exception as e:
            print(f"    SPLINE {i+1}: ошибка - {e}")
    
    if all_real_xs and all_real_ys:
        real_bounds = (min(all_real_xs), min(all_real_ys), max(all_real_xs), max(all_real_ys))
        print(f"  📐 РЕАЛЬНЫЕ bounds всех SPLINE'ов: {real_bounds}")
    
    # 2. Анализируем parsed_data
    print(f"\\n📊 Анализируем parsed_data:")
    
    with open(source_dxf, 'rb') as f:
        parsed_data = parse_dxf_complete(f, verbose=False)
    
    combined_polygon = parsed_data['combined_polygon']
    print(f"  📐 Combined polygon bounds: {combined_polygon.bounds}")
    
    # 3. Сравниваем
    print(f"\\n🔍 СРАВНЕНИЕ:")
    
    if all_real_xs and all_real_ys:
        real_bounds = (min(all_real_xs), min(all_real_ys), max(all_real_xs), max(all_real_ys))
        combined_bounds = combined_polygon.bounds
        
        print(f"  Реальные SPLINE bounds:  {real_bounds}")
        print(f"  Combined polygon bounds: {combined_bounds}")
        
        diff_x = real_bounds[0] - combined_bounds[0]
        diff_y = real_bounds[1] - combined_bounds[1]
        
        print(f"  📏 Разности (реальные - combined):")
        print(f"    X_min: {diff_x:.2f}мм")
        print(f"    Y_min: {diff_y:.2f}мм")
        
        # Это объясняет расхождение!
        if abs(diff_x - 992.33) < 10 and abs(diff_y - 273.76) < 10:
            print(f"  ✅ Это объясняет расхождение в трансформации!")
            print(f"  🔍 ПРИЧИНА: Combined polygon создается из упрощенных SPLINE,")
            print(f"      но трансформация применяется к РЕАЛЬНЫМ SPLINE координатам")
        
        # Проверяем, какие именно полигоны создались при парсинге
        print(f"\\n📊 Анализ полигонов при парсинге:")
        print(f"  Всего полигонов: {len(parsed_data['polygons'])}")
        
        if parsed_data['polygons']:
            # Bounds всех полигонов
            all_poly_bounds = []
            for i, poly in enumerate(parsed_data['polygons'][:5]):  # Первые 5
                bounds = poly.bounds
                all_poly_bounds.append(bounds)
                print(f"    Полигон {i+1}: {bounds}")
            
            if all_poly_bounds:
                # Общие bounds всех полигонов
                min_x = min(b[0] for b in all_poly_bounds)
                min_y = min(b[1] for b in all_poly_bounds)
                max_x = max(b[2] for b in all_poly_bounds)
                max_y = max(b[3] for b in all_poly_bounds)
                total_bounds = (min_x, min_y, max_x, max_y)
                print(f"  📐 Общие bounds всех полигонов: {total_bounds}")
                
                if abs(total_bounds[0] - combined_bounds[0]) < 1 and abs(total_bounds[1] - combined_bounds[1]) < 1:
                    print(f"  ✅ Combined polygon правильно объединяет полигоны")
                else:
                    print(f"  ❌ Combined polygon НЕ соответствует полигонам!")

def suggest_fix():
    """Предлагает решение проблемы."""
    print(f"\\n💡 ПРЕДЛОЖЕНИЕ РЕШЕНИЯ:")
    print(f"  🎯 ПРОБЛЕМА: Трансформация применяется относительно combined_polygon bounds,")
    print(f"      но реальные SPLINE имеют другие координаты.")
    print(f"")
    print(f"  🔧 РЕШЕНИЕ: Использовать реальные bounds SPLINE'ов для нормализации")
    print(f"      вместо bounds combined_polygon.")
    print(f"")
    print(f"  📋 План:")
    print(f"    1. В parse_dxf_complete сохранять реальные bounds SPLINE'ов")
    print(f"    2. В save_dxf_layout_complete использовать эти bounds для нормализации")
    print(f"    3. Это обеспечит точное позиционирование SPLINE элементов")

if __name__ == "__main__":
    print("🔍 Отладка координат SPLINE элементов")
    print("=" * 60)
    
    debug_spline_coordinates()
    suggest_fix()
    
    print("\\n" + "=" * 60)
    print("✅ АНАЛИЗ ЗАВЕРШЕН")