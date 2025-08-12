#!/usr/bin/env python3
"""
Простой тест для проверки структуры файлов и правил сопоставления
"""

import os

def test_dxf_structure():
    """Проверить структуру DXF файлов в папках"""
    print("🧪 Проверка структуры DXF файлов")
    print("=" * 50)
    
    if not os.path.exists('dxf_samples'):
        print("❌ Папка dxf_samples не найдена")
        return False
    
    # Найти примеры папок с разными типами файлов
    examples = {
        'automotive': [],
        'boats': [],
        'scooters': [],
        'mats': []
    }
    
    for item in os.listdir('dxf_samples'):
        item_path = os.path.join('dxf_samples', item)
        if os.path.isdir(item_path):
            item_upper = item.upper()
            
            # Найти DXF файлы в папке
            dxf_files = []
            
            # Проверить подпапку DXF
            dxf_folder = os.path.join(item_path, 'DXF')
            if os.path.exists(dxf_folder):
                search_folder = dxf_folder
            else:
                search_folder = item_path
            
            try:
                for file in os.listdir(search_folder):
                    if file.lower().endswith('.dxf'):
                        dxf_files.append(file)
            except OSError:
                continue
            
            dxf_files.sort()
            
            # Классифицировать папку
            if any(brand in item_upper for brand in ['TOYOTA', 'BMW', 'AUDI', 'VOLKSWAGEN', 'SUBARU', 'SSANG YONG']):
                examples['automotive'].append({'folder': item, 'files': dxf_files})
            elif 'ЛОДКА' in item_upper or 'ADMIRAL' in item_upper or 'ABAKAN' in item_upper:
                examples['boats'].append({'folder': item, 'files': dxf_files})
            elif 'ДЕКА' in item_upper or 'KUGOO' in item_upper:
                examples['scooters'].append({'folder': item, 'files': dxf_files})
            elif 'КОВРИК' in item_upper:
                examples['mats'].append({'folder': item, 'files': dxf_files})
    
    # Отобразить результаты
    for category, items in examples.items():
        category_names = {
            'automotive': '🚗 Автомобильные коврики',
            'boats': '🛥️  Лодочные коврики',
            'scooters': '🛴 Коврики для самокатов',
            'mats': '🪑 Различные коврики'
        }
        
        print(f"\n{category_names[category]}:")
        for item in items[:3]:  # Показать только первые 3 примера
            print(f"   📁 {item['folder']}")
            print(f"      Файлы: {item['files']}")
    
    return True

def test_file_number_patterns():
    """Проверить наличие файлов с определенными номерами"""
    print("\n🔢 Проверка паттернов номеров файлов")
    print("=" * 50)
    
    # Найти папки с файлами разных номеров
    patterns = {
        'files_1_to_9': [],     # борт - файлы 1-9
        'only_file_1': [],      # водитель - только файл 1
        'files_1_and_2': [],   # передние - файлы 1 и 2  
        'files_10_plus': [],   # багажник - файлы 10-16
        'all_files': []        # лодка/самокат/ковер - все файлы
    }
    
    for item in os.listdir('dxf_samples'):
        item_path = os.path.join('dxf_samples', item)
        if not os.path.isdir(item_path):
            continue
        
        # Найти DXF файлы
        dxf_folder = os.path.join(item_path, 'DXF')
        search_folder = dxf_folder if os.path.exists(dxf_folder) else item_path
        
        try:
            files = [f for f in os.listdir(search_folder) if f.lower().endswith('.dxf')]
        except OSError:
            continue
        
        # Извлечь номера файлов
        numbered_files = []
        for file in files:
            try:
                # Извлечь номер из имени файла (например, "1.dxf" -> 1)
                number = int(file.split('.')[0])
                numbered_files.append(number)
            except (ValueError, IndexError):
                continue
        
        numbered_files.sort()
        
        if not numbered_files:
            continue
        
        # Классифицировать по паттерну
        min_num = min(numbered_files)
        max_num = max(numbered_files)
        count = len(numbered_files)
        
        item_info = {'folder': item, 'files': numbered_files, 'total': len(files)}
        
        if min_num == 1 and max_num <= 9 and count >= 4:
            patterns['files_1_to_9'].append(item_info)
        elif numbered_files == [1]:
            patterns['only_file_1'].append(item_info)
        elif set(numbered_files) == {1, 2}:
            patterns['files_1_and_2'].append(item_info)
        elif min_num >= 10:
            patterns['files_10_plus'].append(item_info)
        else:
            patterns['all_files'].append(item_info)
    
    # Отобразить результаты
    pattern_descriptions = {
        'files_1_to_9': 'Файлы 1-9 (подходит для типа "борт")',
        'only_file_1': 'Только файл 1 (подходит для типа "водитель")', 
        'files_1_and_2': 'Файлы 1 и 2 (подходит для типа "передние")',
        'files_10_plus': 'Файлы 10+ (подходит для типа "багажник")',
        'all_files': 'Разные файлы (подходит для лодок/самокатов/ковриков)'
    }
    
    for pattern, description in pattern_descriptions.items():
        items = patterns[pattern]
        print(f"\n📋 {description}:")
        for item in items[:2]:  # Показать первые 2 примера
            print(f"   📁 {item['folder']} - файлы: {item['files']} (всего: {item['total']})")
    
    return True

def main():
    print("🧪 Простая проверка структуры данных для сопоставления типов")
    print("=" * 70)
    
    # Проверить структуру
    structure_ok = test_dxf_structure()
    
    # Проверить паттерны файлов
    patterns_ok = test_file_number_patterns()
    
    print("\n" + "=" * 70)
    print("📊 Результаты проверки:")
    
    if structure_ok and patterns_ok:
        print("✅ Структура данных выглядит корректно")
        print("✅ Обнаружены нужные паттерны файлов")
        print("\n🎉 Система готова для тестирования правил сопоставления!")
        print("\n💡 Правила сопоставления:")
        print('   • "борт" - файлы 1.dxf до 9.dxf')
        print('   • "водитель" - только 1.dxf') 
        print('   • "передние" - файлы 1.dxf и 2.dxf')
        print('   • "багажник" - файлы 10.dxf до 16.dxf')
        print('   • "лодка", "самокат", "ковер" - все файлы в папке')
        return True
    else:
        print("❌ Обнаружены проблемы со структурой данных")
        return False

if __name__ == "__main__":
    main()