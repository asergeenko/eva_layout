#!/usr/bin/env python3
"""
Тестируем функцию scale_polygons_to_fit - что она делает с TANK объектами
"""

import sys
sys.path.insert(0, '.')

import importlib
import layout_optimizer
importlib.reload(layout_optimizer)

from layout_optimizer import parse_dxf_complete, scale_polygons_to_fit
import os
import glob

def test_scale_function():
    """Тестируем scale_polygons_to_fit"""
    print("🔍 ТЕСТ ФУНКЦИИ scale_polygons_to_fit")
    print("=" * 50)
    
    # Загружаем TANK объекты
    tank_file = "dxf_samples/TANK 300/1.dxf"
    if not os.path.exists(tank_file):
        print(f"❌ Файл {tank_file} не найден!")
        return
    
    try:
        result = parse_dxf_complete(tank_file)
        polygons = result['polygons']
        
        if not polygons:
            print("❌ Полигоны не найдены!")
            return
        
        # Создаем список как в Streamlit
        polygons_with_names = []
        for i, poly in enumerate(polygons):
            polygons_with_names.append((poly, f"tank_{i+1}.dxf", "черный", i))
        
        print(f"Загружено {len(polygons_with_names)} объектов")
        
        # Размеры ДО scale_polygons_to_fit
        print(f"\n📏 РАЗМЕРЫ ДО МАСШТАБИРОВАНИЯ:")
        for i, (poly, name, color, oid) in enumerate(polygons_with_names):
            bounds = poly.bounds
            width = bounds[2] - bounds[0]
            height = bounds[3] - bounds[1]
            print(f"  Объект {i+1}: {width:.2f}×{height:.2f}мм, площадь={poly.area:.1f}")
        
        # Размер листа как в Streamlit
        reference_sheet_size = (140, 200)  # см
        print(f"\nРазмер листа: {reference_sheet_size} см = {reference_sheet_size[0]*10}×{reference_sheet_size[1]*10}мм")
        
        # Применяем scale_polygons_to_fit
        print(f"\n🔄 ПРИМЕНЯЕМ scale_polygons_to_fit...")
        scaled_polygons = scale_polygons_to_fit(polygons_with_names, reference_sheet_size, verbose=True)
        
        # Размеры ПОСЛЕ scale_polygons_to_fit
        print(f"\n📏 РАЗМЕРЫ ПОСЛЕ МАСШТАБИРОВАНИЯ:")
        for i, (poly, name, color, oid) in enumerate(scaled_polygons):
            bounds = poly.bounds
            width = bounds[2] - bounds[0]
            height = bounds[3] - bounds[1]
            print(f"  Объект {i+1}: {width:.2f}×{height:.2f}мм, площадь={poly.area:.1f}")
        
        # Проверяем коэффициент масштабирования
        if polygons_with_names and scaled_polygons:
            orig_bounds = polygons_with_names[0][0].bounds
            scaled_bounds = scaled_polygons[0][0].bounds
            
            orig_width = orig_bounds[2] - orig_bounds[0]
            scaled_width = scaled_bounds[2] - scaled_bounds[0]
            
            scale_factor = scaled_width / orig_width if orig_width > 0 else 1
            print(f"\n🎯 КОЭФФИЦИЕНТ МАСШТАБИРОВАНИЯ: {scale_factor:.4f}")
            
            if scale_factor < 1.0:
                print(f"❌ ОБЪЕКТЫ УМЕНЬШЕНЫ! Было {orig_width:.1f}мм → стало {scaled_width:.1f}мм")
            elif scale_factor > 1.0:
                print(f"✅ Объекты увеличены: {orig_width:.1f}мм → {scaled_width:.1f}мм")
            else:
                print(f"✅ Размер не изменился")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_scale_function()