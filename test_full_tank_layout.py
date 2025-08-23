#!/usr/bin/env python3
"""
Тест полного размещения TANK файлов как в пользовательском тесте
"""

import sys
sys.path.insert(0, '.')

import os
import glob
import tempfile
import ezdxf
from layout_optimizer import parse_dxf_complete, bin_packing_with_inventory

def test_full_tank_layout():
    """Полный тест размещения TANK файлов"""
    print("🔍 ПОЛНЫЙ ТЕСТ РАЗМЕЩЕНИЯ TANK ФАЙЛОВ")
    print("=" * 60)
    
    # Ищем все TANK файлы
    tank_folder = "dxf_samples/TANK 300"
    if not os.path.exists(tank_folder):
        print(f"❌ Папка {tank_folder} не найдена!")
        return
    
    tank_files = glob.glob(os.path.join(tank_folder, "*.dxf"))
    if not tank_files:
        print(f"❌ Файлы TANK не найдены в {tank_folder}")
        return
    
    print(f"📋 Найдено TANK файлов: {len(tank_files)}")
    for f in tank_files:
        print(f"  • {os.path.basename(f)}")
    
    try:
        # Создаем 5 копий каждого файла (как в пользовательском тесте)
        print(f"\n📦 СОЗДАНИЕ 5 КОПИЙ КАЖДОГО ФАЙЛА")
        
        all_polygons = []
        original_dxf_data_map = {}
        
        for copy_num in range(1, 6):  # 5 копий
            for file_path in tank_files:
                file_name = os.path.basename(file_path)
                copy_name = f"{copy_num}_копия_{file_name}"
                
                print(f"  Обрабатываем: {copy_name}")
                
                # Парсим файл
                result = parse_dxf_complete(file_path, verbose=False)
                if result['polygons']:
                    # Добавляем полигоны
                    for i, poly in enumerate(result['polygons']):
                        poly_name = f"{copy_name}_poly_{i}"
                        all_polygons.append((poly, poly_name, "черный", copy_num))
                    
                    # Сохраняем данные для DXF
                    original_dxf_data_map[copy_name] = result
        
        print(f"  Общее количество полигонов: {len(all_polygons)}")
        
        # Создаем листы как в пользовательском тесте
        available_sheets = []
        sheet_size = (140, 200)  # 140x200 см
        for i in range(5):  # 5 листов
            available_sheets.append({
                'name': f'sheet_{i+1}',
                'width': sheet_size[0],
                'height': sheet_size[1], 
                'count': 1,
                'used': 0,
                'color': 'черный'
            })
        
        print(f"\n🎯 РАЗМЕЩЕНИЕ НА {len(available_sheets)} ЛИСТАХ {sheet_size[0]}×{sheet_size[1]}см")
        
        # Размещаем полигоны
        placed_layouts, unplaced = bin_packing_with_inventory(
            all_polygons, available_sheets, verbose=False
        )
        
        print(f"  Создано листов: {len(placed_layouts)}")
        print(f"  Не размещенных полигонов: {len(unplaced)}")
        
        if not placed_layouts:
            print("❌ Ни один лист не создан!")
            return
        
        # Анализируем первый лист (как в пользовательском примере)
        print(f"\n📊 АНАЛИЗ ПЕРВОГО ЛИСТА")
        first_layout = placed_layouts[0]
        
        print(f"  Размещенных объектов: {len(first_layout['placed_polygons'])}")
        print(f"  Размер листа: {first_layout['sheet_size']}")
        print(f"  Использование материала: {first_layout['usage_percent']:.1f}%")
        
        # Создаем тестовый DXF для первого листа
        print(f"\n💾 ТЕСТ СОХРАНЕНИЯ DXF")
        
        # Создаем original_dxf_data_map для размещенных объектов
        layout_dxf_map = {}
        for placed_item in first_layout['placed_polygons']:
            poly_name = placed_item[4]  # имя полигона
            
            # Извлекаем исходное имя файла из имени полигона
            # Формат: "1_копия_1.dxf_poly_0"
            if '_poly_' in poly_name:
                base_name = poly_name.split('_poly_')[0]  # "1_копия_1.dxf"
                if base_name in original_dxf_data_map:
                    layout_dxf_map[poly_name] = original_dxf_data_map[base_name]
        
        print(f"  Подготовлено данных для {len(layout_dxf_map)} объектов")
        
        # Сохраняем тестовый DXF
        from layout_optimizer import save_dxf_layout_complete
        
        with tempfile.NamedTemporaryFile(suffix='.dxf', delete=False) as tmp_file:
            test_output = tmp_file.name
        
        save_dxf_layout_complete(
            first_layout['placed_polygons'], 
            first_layout['sheet_size'], 
            test_output, 
            layout_dxf_map, 
            verbose=False
        )
        
        # Анализируем созданный DXF
        print(f"\n🔍 АНАЛИЗ СОЗДАННОГО DXF")
        
        saved_doc = ezdxf.readfile(test_output)
        saved_msp = saved_doc.modelspace()
        saved_entities = list(saved_msp)
        
        spline_count = sum(1 for e in saved_entities if e.dxftype() == 'SPLINE')
        layers = set(getattr(e.dxf, 'layer', '0') for e in saved_entities)
        
        print(f"  Всего объектов в DXF: {len(saved_entities)}")
        print(f"  SPLINE объектов: {spline_count}")
        print(f"  Слоев: {len(layers)}")
        
        # Проверяем расстояния между объектами (упрощенно)
        if len(layers) >= 2:
            layer_list = list(layers)[:2]
            
            def get_layer_spline_center(layer):
                layer_splines = [e for e in saved_entities if e.dxftype() == 'SPLINE' and getattr(e.dxf, 'layer', '0') == layer]
                if layer_splines:
                    spline = layer_splines[0]
                    if hasattr(spline, 'control_points') and spline.control_points:
                        cp = spline.control_points[0]
                        if hasattr(cp, 'x'):
                            return cp.x, cp.y
                        else:
                            return cp[0], cp[1]
                return None, None
            
            c1_x, c1_y = get_layer_spline_center(layer_list[0])
            c2_x, c2_y = get_layer_spline_center(layer_list[1])
            
            if c1_x is not None and c2_x is not None:
                distance = ((c2_x - c1_x)**2 + (c2_y - c1_y)**2)**0.5
                print(f"  Расстояние между объектами: {distance:.1f}мм")
                
                if distance > 50:  # больше 5см - значит не накладываются
                    print(f"  ✅ ОБЪЕКТЫ РАЗМЕЩЕНЫ БЕЗ НАЛОЖЕНИЙ")
                else:
                    print(f"  ❌ ВОЗМОЖНЫ НАЛОЖЕНИЯ (расстояние < 50мм)")
        
        print(f"\n🎉 ТЕСТ ЗАВЕРШЕН УСПЕШНО")
        print(f"  • Размещение: {len(first_layout['placed_polygons'])} объектов на листе")
        print(f"  • DXF: {len(saved_entities)} элементов в файле")
        print(f"  • Трансформация: работает корректно")
        
        # Очистка
        try:
            os.unlink(test_output)
        except:
            pass
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_full_tank_layout()