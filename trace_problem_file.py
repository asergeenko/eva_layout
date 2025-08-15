#!/usr/bin/env python3
"""
Трассировка создания проблемного файла 200_140_1_black.dxf
"""

from layout_optimizer import parse_dxf_complete, bin_packing_with_inventory, save_dxf_layout_complete, check_collision
import os
import glob

def analyze_problem_file():
    """Анализируем как создается проблемный файл"""
    print("=== АНАЛИЗ СОЗДАНИЯ ФАЙЛА 200_140_1_black.dxf ===")
    
    # Анализируем исходные DXF файлы в папке dxf_samples
    dxf_samples_dir = "/home/sasha/proj/2025/eva_layout/dxf_samples"
    
    if not os.path.exists(dxf_samples_dir):
        print(f"❌ Папка {dxf_samples_dir} не найдена")
        return False
    
    # Ищем все DXF файлы
    all_dxf_files = []
    for root, dirs, files in os.walk(dxf_samples_dir):
        for file in files:
            if file.endswith('.dxf'):
                all_dxf_files.append(os.path.join(root, file))
    
    print(f"Найдено {len(all_dxf_files)} DXF файлов в образцах")
    
    if len(all_dxf_files) == 0:
        print("❌ Не найдено DXF файлов для анализа")
        return False
    
    # Возьмем несколько файлов для тестирования (как это делает приложение)
    test_files = all_dxf_files[:5]  # Первые 5 файлов
    print(f"Тестируем с {len(test_files)} файлами:")
    
    # Парсим исходные DXF файлы
    input_data = []
    original_dxf_data_map = {}
    
    for i, dxf_file in enumerate(test_files):
        print(f"  {i+1}. Парсинг {os.path.basename(dxf_file)}")
        
        try:
            dxf_data = parse_dxf_complete(dxf_file, verbose=False)
            
            if dxf_data['combined_polygon'] and dxf_data['combined_polygon'].area > 0:
                # Имитируем как приложение добавляет полигоны
                filename = os.path.basename(dxf_file)
                color = "черный"  # Предполагаем черный цвет для этого файла
                order_id = "order1"  # Все в одном заказе
                
                input_data.append((
                    dxf_data['combined_polygon'], 
                    filename, 
                    color, 
                    order_id
                ))
                
                original_dxf_data_map[filename] = dxf_data
                
                bounds = dxf_data['combined_polygon'].bounds
                width_cm = (bounds[2] - bounds[0]) / 10
                height_cm = (bounds[3] - bounds[1]) / 10
                print(f"    Размер: {width_cm:.1f}x{height_cm:.1f} см")
                
            else:
                print(f"    ⚠️ Не удалось получить валидный полигон")
                
        except Exception as e:
            print(f"    ❌ Ошибка парсинга: {e}")
    
    if len(input_data) == 0:
        print("❌ Не удалось обработать ни один DXF файл")
        return False
    
    print(f"\nУспешно обработано {len(input_data)} файлов")
    
    # Настройка листов (как в реальном приложении)
    available_sheets = [
        {
            'name': 'Лист 200x140',
            'width': 200,  # см
            'height': 140, # см
            'color': 'черный',
            'count': 10,
            'used': 0
        }
    ]
    
    print(f"\nЗапуск bin_packing_with_inventory...")
    print(f"Входные данные: {len(input_data)} полигонов")
    print(f"Доступные листы: {len(available_sheets)} типов")
    
    # Запускаем основной алгоритм размещения
    try:
        placed_layouts, unplaced = bin_packing_with_inventory(
            input_data, 
            available_sheets, 
            verbose=True,
            max_sheets_per_order=None
        )
        
        print(f"\nРезультат bin_packing_with_inventory:")
        print(f"  Созданных листов: {len(placed_layouts)}")
        print(f"  Не размещено полигонов: {len(unplaced)}")
        
        if len(placed_layouts) > 0:
            first_layout = placed_layouts[0]
            placed_polygons = first_layout['placed_polygons']
            
            print(f"\nАнализ первого листа:")
            print(f"  Размещено полигонов: {len(placed_polygons)}")
            print(f"  Использование: {first_layout['usage_percent']:.1f}%")
            
            # Проверяем коллизии между размещенными полигонами
            print(f"\nПроверка коллизий в результате bin_packing_with_inventory:")
            collision_count = 0
            
            for i in range(len(placed_polygons)):
                for j in range(i+1, len(placed_polygons)):
                    poly1 = placed_polygons[i][0]  # Первый элемент - полигон
                    poly2 = placed_polygons[j][0]
                    
                    if check_collision(poly1, poly2):
                        collision_count += 1
                        print(f"    ❌ КОЛЛИЗИЯ между полигонами {i+1} и {j+1}")
                        print(f"      Полигон {i+1}: bounds={poly1.bounds}")
                        print(f"      Полигон {j+1}: bounds={poly2.bounds}")
                        
                        if collision_count >= 5:  # Ограничиваем вывод
                            print(f"    ... и еще коллизий")
                            break
                if collision_count >= 5:
                    break
            
            if collision_count == 0:
                print(f"    ✅ Коллизий не найдено")
            else:
                print(f"    ❌ НАЙДЕНО {collision_count}+ КОЛЛИЗИЙ в bin_packing_with_inventory!")
                
                # Это критическая ошибка - алгоритм размещения создает наложения
                print(f"\n🚨 ПРОБЛЕМА НАЙДЕНА в bin_packing_with_inventory!")
                return False
            
            # Тестируем сохранение в DXF
            print(f"\n=== ТЕСТ СОХРАНЕНИЯ В DXF ===")
            
            output_path = "/tmp/test_problem_file.dxf"
            sheet_size = (first_layout['sheet_size'][0] / 10, first_layout['sheet_size'][1] / 10)  # см
            
            try:
                save_dxf_layout_complete(
                    placed_polygons,
                    sheet_size,
                    output_path,
                    original_dxf_data_map
                )
                
                print(f"✅ DXF файл сохранен: {output_path}")
                
                # Читаем сохраненный файл и проверяем наложения ПРАВИЛЬНО
                saved_data = parse_dxf_complete(output_path, verbose=False)
                
                if saved_data['original_entities']:
                    print(f"Из сохраненного DXF прочитано {len(saved_data['original_entities'])} entities")
                    
                    # Группируем entities по исходным коврам на основе имен слоев
                    carpet_groups = {}
                    for entity_data in saved_data['original_entities']:
                        layer = entity_data['layer']
                        if layer == 'SHEET_BOUNDARY':
                            continue  # Пропускаем границы листа
                        
                        # Извлекаем имя файла из имени слоя (например: "1_layer 2" -> "1")
                        carpet_name = layer.split('_')[0] if '_' in layer else layer
                        
                        if carpet_name not in carpet_groups:
                            carpet_groups[carpet_name] = []
                        carpet_groups[carpet_name].append(entity_data)
                    
                    print(f"Найдено {len(carpet_groups)} групп ковров: {list(carpet_groups.keys())}")
                    
                    # Создаем комбинированные полигоны для каждой группы ковров
                    carpet_combined_polygons = {}
                    from layout_optimizer import convert_entity_to_polygon_improved
                    from shapely.ops import unary_union
                    
                    for carpet_name, entities in carpet_groups.items():
                        polygons_in_carpet = []
                        for entity_data in entities:
                            try:
                                polygon = convert_entity_to_polygon_improved(entity_data['entity'])
                                if polygon and polygon.is_valid and polygon.area > 0.1:
                                    polygons_in_carpet.append(polygon)
                            except:
                                pass
                        
                        if polygons_in_carpet:
                            if len(polygons_in_carpet) == 1:
                                carpet_combined_polygons[carpet_name] = polygons_in_carpet[0]
                            else:
                                try:
                                    combined = unary_union(polygons_in_carpet)
                                    carpet_combined_polygons[carpet_name] = combined
                                except:
                                    # Fallback to first polygon if union fails
                                    carpet_combined_polygons[carpet_name] = polygons_in_carpet[0]
                    
                    print(f"Создано {len(carpet_combined_polygons)} комбинированных полигонов ковров")
                    
                    # Теперь проверяем коллизии ТОЛЬКО между разными коврами
                    carpet_names = list(carpet_combined_polygons.keys())
                    saved_collisions = 0
                    
                    for i in range(len(carpet_names)):
                        for j in range(i+1, len(carpet_names)):
                            carpet1_name = carpet_names[i]
                            carpet2_name = carpet_names[j]
                            polygon1 = carpet_combined_polygons[carpet1_name]
                            polygon2 = carpet_combined_polygons[carpet2_name]
                            
                            if check_collision(polygon1, polygon2):
                                saved_collisions += 1
                                if saved_collisions <= 3:
                                    print(f"    ❌ Коллизия между коврами '{carpet1_name}' и '{carpet2_name}'")
                                    print(f"      Ковер {carpet1_name}: bounds={polygon1.bounds}")
                                    print(f"      Ковер {carpet2_name}: bounds={polygon2.bounds}")
                    
                    if saved_collisions > 0:
                        print(f"    🚨 В СОХРАНЕННОМ DXF НАЙДЕНО {saved_collisions} РЕАЛЬНЫХ КОЛЛИЗИЙ между коврами!")
                        return False
                    else:
                        print(f"    ✅ В сохраненном DXF реальных коллизий между коврами нет")
                        return True
                else:
                    print(f"    ❌ Не удалось прочитать ковры из сохраненного DXF")
                    return False
                    
            except Exception as e:
                print(f"❌ Ошибка сохранения DXF: {e}")
                return False
            
        else:
            print("❌ Не создано ни одного листа")
            return False
        
    except Exception as e:
        print(f"❌ Ошибка в bin_packing_with_inventory: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("ТРАССИРОВКА ПРОБЛЕМНОГО ФАЙЛА")
    print("=" * 60)
    
    success = analyze_problem_file()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ Процесс создания файла работает корректно")
        print("Проблема может быть в специфических данных или условиях")
    else:
        print("🚨 НАЙДЕН ИСТОЧНИК ПРОБЛЕМЫ!")
        print("Обнаружены ошибки в процессе создания файла")
    print("=" * 60)