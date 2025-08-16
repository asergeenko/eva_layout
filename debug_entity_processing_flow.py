#!/usr/bin/env python3

import sys
import os
sys.path.append('.')

def manually_trace_entity_flow():
    """Вручную проследим поток обработки сущностей"""
    
    print("=== ТРАССИРОВКА ПОТОКА ОБРАБОТКИ СУЩНОСТЕЙ ===")
    
    # Давайте симулируем загрузку одного DXF файла и посмотрим что происходит
    import ezdxf
    from layout_optimizer import parse_dxf_complete
    
    # Найдем файл с IMAGE сущностями
    import glob
    
    dxf_files = glob.glob("dxf_samples/**/*.dxf", recursive=True)
    
    test_file = None
    for dxf_file in dxf_files[:20]:
        try:
            doc = ezdxf.readfile(dxf_file)
            msp = doc.modelspace()
            image_count = sum(1 for entity in msp if entity.dxftype() == 'IMAGE')
            if image_count > 0:
                test_file = dxf_file
                print(f"Найден тестовый файл с IMAGE: {test_file}")
                break
        except:
            continue
    
    if not test_file:
        print("⚠️  НЕ найден файл с IMAGE сущностями")
        return
    
    # Загрузим данные этого файла через нашу функцию
    print(f"\n--- Загрузка данных через load_dxf_data ---")
    try:
        dxf_data = parse_dxf_complete(test_file)
        
        print(f"Результат parse_dxf_complete:")
        print(f"  combined_polygon: {dxf_data['combined_polygon'] is not None}")
        print(f"  original_entities: {len(dxf_data['original_entities'])}")
        print(f"  layers: {dxf_data['layers']}")
        
        # Проверим типы сущностей в original_entities
        entity_types = {}
        for entity_data in dxf_data['original_entities']:
            entity_type = entity_data['type']
            entity_types[entity_type] = entity_types.get(entity_type, 0) + 1
        
        print(f"  типы сущностей в original_entities:")
        for etype, count in entity_types.items():
            print(f"    {etype}: {count}")
        
        # Проверим есть ли IMAGE среди original_entities
        image_entities = [ed for ed in dxf_data['original_entities'] if ed['type'] == 'IMAGE']
        print(f"  IMAGE сущности в original_entities: {len(image_entities)}")
        
        if image_entities:
            print("  Детали первой IMAGE сущности:")
            img_entity = image_entities[0]
            print(f"    layer: {img_entity['layer']}")
            print(f"    entity: {type(img_entity['entity'])}")
            
            # Проверим позицию IMAGE
            if hasattr(img_entity['entity'].dxf, 'insert'):
                pos = img_entity['entity'].dxf.insert
                print(f"    position: ({pos[0]:.1f}, {pos[1]:.1f})")
        
    except Exception as e:
        print(f"Ошибка загрузки данных: {e}")
        import traceback
        traceback.print_exc()

def check_save_function_call():
    """Проверим вызывается ли функция save_dxf_layout_complete"""
    
    print("\n=== ПРОВЕРКА ВЫЗОВА SAVE_DXF_LAYOUT_COMPLETE ===")
    
    # Добавим временную отладку в функцию
    try:
        with open("layout_optimizer.py", "r", encoding="utf-8") as f:
            content = f.read()
        
        # Найдем начало функции save_dxf_layout_complete
        lines = content.split('\n')
        func_line = None
        
        for i, line in enumerate(lines):
            if "def save_dxf_layout_complete" in line:
                func_line = i
                break
        
        if func_line:
            print(f"Функция save_dxf_layout_complete найдена на строке {func_line + 1}")
            
            # Посмотрим на первые несколько строк функции
            for i in range(func_line, min(func_line + 10, len(lines))):
                print(f"  {i+1}: {lines[i]}")
        else:
            print("⚠️  Функция save_dxf_layout_complete НЕ найдена")
        
        # Найдем где эта функция вызывается
        calls = []
        for i, line in enumerate(lines):
            if "save_dxf_layout_complete" in line and "def " not in line:
                calls.append((i+1, line.strip()))
        
        print(f"\nВызовы функции save_dxf_layout_complete: {len(calls)}")
        for line_num, line in calls:
            print(f"  {line_num}: {line}")
    
    except Exception as e:
        print(f"Ошибка анализа функции: {e}")

if __name__ == "__main__":
    manually_trace_entity_flow()
    check_save_function_call()