#!/usr/bin/env python3
"""
Проверяем масштаб TANK файлов - возможно они слишком маленькие
"""

import sys
sys.path.insert(0, '.')

import os
import glob
from layout_optimizer import parse_dxf_complete
import ezdxf

def check_tank_scale():
    """Проверяем реальные размеры TANK файлов"""
    print("🔍 ПРОВЕРКА МАСШТАБА TANK ФАЙЛОВ")
    print("=" * 50)
    
    tank_folder = "dxf_samples/TANK 300"
    if not os.path.exists(tank_folder):
        print(f"❌ Папка {tank_folder} не найдена!")
        return
    
    dxf_files = glob.glob(os.path.join(tank_folder, "*.dxf"))
    print(f"Найдено файлов: {len(dxf_files)}")
    
    for file_path in dxf_files:
        file_name = os.path.basename(file_path)
        print(f"\n📏 ФАЙЛ: {file_name}")
        
        try:
            # Метод 1: Через layout_optimizer
            result = parse_dxf_complete(file_path)
            polygons = result['polygons']
            
            print(f"  Полигонов через parse_dxf_complete: {len(polygons)}")
            
            if polygons:
                for i, poly in enumerate(polygons[:3]):  # первые 3
                    bounds = poly.bounds
                    width = bounds[2] - bounds[0]
                    height = bounds[3] - bounds[1]
                    print(f"    Полигон {i+1}: {width:.2f}×{height:.2f} единиц, площадь={poly.area:.1f}")
            
            # Метод 2: Прямое чтение DXF
            print(f"  \n📋 ПРЯМОЙ АНАЛИЗ DXF:")
            doc = ezdxf.readfile(file_path)
            modelspace = doc.modelspace()
            entities = list(modelspace)
            
            print(f"    Всего сущностей: {len(entities)}")
            
            # Находим экстенты всех объектов
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
                total_width = max(all_x) - min(all_x)
                total_height = max(all_y) - min(all_y)
                print(f"    Общие габариты файла: {total_width:.2f}×{total_height:.2f} единиц")
                
                # Определяем единицы измерения
                print(f"    \n🤔 АНАЛИЗ ЕДИНИЦ:")
                if total_width < 100 and total_height < 100:
                    print(f"      Если единицы = мм: {total_width:.1f}×{total_height:.1f}мм = {total_width/10:.1f}×{total_height/10:.1f}см")
                    print(f"      Если единицы = см: {total_width:.1f}×{total_height:.1f}см")
                    
                    # TANK 300 должен быть примерно 30×30мм или 3×3см
                    if total_width < 50:  # меньше 5см
                        print(f"      ⚠️ ПОДОЗРИТЕЛЬНО МАЛО! TANK 300 должен быть больше")
                        
                        # Предлагаем масштабирование
                        scale_factor = 30 / total_width if total_width > 0 else 1
                        print(f"      💡 ПРЕДЛАГАЕМОЕ МАСШТАБИРОВАНИЕ: ×{scale_factor:.1f}")
                        print(f"         После масштабирования: {total_width*scale_factor:.1f}×{total_height*scale_factor:.1f}мм")
            
            # Проверяем header DXF на единицы
            if hasattr(doc.header, '$INSUNITS'):
                units = doc.header.get('$INSUNITS', 0)
                units_map = {0: 'Unitless', 1: 'Inches', 2: 'Feet', 4: 'Millimeters', 5: 'Centimeters', 6: 'Meters'}
                print(f"    📐 Единицы в DXF header: {units_map.get(units, f'Unknown ({units})')}")
            
        except Exception as e:
            print(f"    ❌ Ошибка анализа: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\n🎯 ВЫВОДЫ:")
    print(f"1. Если размеры действительно ~15×25мм, то объекты СЛИШКОМ МАЛЕНЬКИЕ")
    print(f"2. TANK 300 должен быть примерно 30×30мм (3×3см) или больше")
    print(f"3. Возможно, нужно МАСШТАБИРОВАТЬ объекты при парсинге")

if __name__ == "__main__":
    check_tank_scale()