#!/usr/bin/env python3

import sys
import os

# Добавим отладочную функцию для поиска места создания IMAGE сущностей
def trace_image_creation_in_code():
    """Ищем где в коде создаются/обрабатываются IMAGE сущности"""
    
    print("=== ПОИСК ОБРАБОТКИ IMAGE СУЩНОСТЕЙ В КОДЕ ===")
    
    try:
        with open("layout_optimizer.py", "r", encoding="utf-8") as f:
            content = f.read()
        
        lines = content.split('\n')
        image_related_lines = []
        
        for i, line in enumerate(lines):
            if any(keyword in line.upper() for keyword in ['IMAGE', 'ENTITY_DATA', 'ENTITY.DXFTYPE', 'ADD_ENTITY']):
                image_related_lines.append((i+1, line.strip()))
        
        print(f"Найдено {len(image_related_lines)} строк, связанных с IMAGE или сущностями:")
        
        for line_num, line in image_related_lines[:20]:  # Показать первые 20
            print(f"  Line {line_num}: {line}")
        
        # Ищем специфически обработку IMAGE
        if "entity_data['type'] == 'IMAGE'" in content:
            print("\n✅ Найдена специальная обработка IMAGE сущностей")
        else:
            print("\n⚠️  НЕ найдена специальная обработка IMAGE сущностей")
        
        # Ищем где добавляются сущности в modelspace
        add_entity_lines = []
        for i, line in enumerate(lines):
            if "add_entity" in line or "msp.add" in line:
                add_entity_lines.append((i+1, line.strip()))
        
        print(f"\nНайдено {len(add_entity_lines)} мест добавления сущностей:")
        for line_num, line in add_entity_lines:
            print(f"  Line {line_num}: {line}")
        
        # Проверяем, есть ли условие для обработки IMAGE
        debug_lines = []
        for i, line in enumerate(lines):
            if "🔍 DEBUG" in line and "IMAGE" in line:
                debug_lines.append((i+1, line.strip()))
        
        if debug_lines:
            print(f"\nНайдены отладочные сообщения для IMAGE:")
            for line_num, line in debug_lines:
                print(f"  Line {line_num}: {line}")
        else:
            print("\n⚠️  НЕ найдены отладочные сообщения для IMAGE")
            print("   Это может означать, что IMAGE трансформация не вызывается")
    
    except Exception as e:
        print(f"Ошибка анализа файла: {e}")

def check_original_dxf_data():
    """Проверяем есть ли IMAGE сущности в оригинальных данных"""
    
    print("\n=== ПРОВЕРКА ОРИГИНАЛЬНЫХ ДАННЫХ ===")
    
    # Попробуем найти исходные DXF файлы с IMAGE сущностями
    import glob
    import ezdxf
    
    dxf_files = glob.glob("dxf_samples/**/*.dxf", recursive=True)
    print(f"Найдено {len(dxf_files)} DXF файлов в dxf_samples/")
    
    # Проверим первые несколько файлов на наличие IMAGE сущностей
    files_with_images = []
    
    for dxf_file in dxf_files[:10]:  # Проверим первые 10 файлов
        try:
            doc = ezdxf.readfile(dxf_file)
            msp = doc.modelspace()
            
            image_count = sum(1 for entity in msp if entity.dxftype() == 'IMAGE')
            text_count = sum(1 for entity in msp if entity.dxftype() == 'TEXT')
            
            if image_count > 0 or text_count > 0:
                files_with_images.append((dxf_file, image_count, text_count))
                print(f"  {os.path.basename(dxf_file)}: {image_count} IMAGE, {text_count} TEXT")
                
        except Exception as e:
            continue  # Пропускаем файлы с ошибками
    
    if files_with_images:
        print(f"\nНайдено {len(files_with_images)} файлов с IMAGE/TEXT сущностями")
    else:
        print("\n⚠️  НЕ найдено файлов с IMAGE/TEXT сущностями в первых 10 файлах")

if __name__ == "__main__":
    trace_image_creation_in_code()
    check_original_dxf_data()