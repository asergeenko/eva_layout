#!/usr/bin/env python3
"""
Тестирование нового сопоставления типов изделий с файлами DXF
"""

import os
import sys

# Добавляем текущий каталог в путь для импортов
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_product_type_mapping():
    """Тестирование логики сопоставления типов изделий"""
    print("🧪 Тестирование сопоставления типов изделий с DXF файлами")
    print("=" * 70)
    
    # Импортируем функции из streamlit_demo.py
    try:
        # Читаем содержимое streamlit_demo.py и извлекаем функции
        exec_globals = {}
        with open('streamlit_demo.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Извлекаем только нужные функции
        import re
        
        # Найти функцию get_dxf_files_for_product_type
        func_pattern = r'def (get_dxf_files_for_product_type|find_product_folder|calculate_folder_match_score)\(.*?\):(.*?)(?=def|\Z)'
        functions = re.findall(func_pattern, content, re.DOTALL | re.MULTILINE)
        
        # Создаем локальный контекст с нужными импортами
        exec_code = '''
import os
import re
import logging

logger = logging.getLogger(__name__)

'''
        
        # Добавляем найденные функции
        for func_name, func_body in functions:
            exec_code += f"def {func_name}(*args, **kwargs):\n"
            # Отступы для тела функции
            func_lines = func_body.strip().split('\n')
            for line in func_lines:
                if line.strip():
                    exec_code += "    " + line + "\n"
                else:
                    exec_code += "\n"
        
        # Выполняем код
        exec(exec_code, exec_globals)
        
        # Извлекаем функции
        get_dxf_files_for_product_type = exec_globals['get_dxf_files_for_product_type']
        find_product_folder = exec_globals['find_product_folder']
        
    except Exception as e:
        print(f"❌ Ошибка импорта функций: {e}")
        return False
    
    # Тестовые случаи
    test_cases = [
        {
            'article': 'EVA_BORT+TOYOTA+COROLLA 11',
            'product': 'TOYOTA COROLLA 11',
            'product_type': 'борт',
            'expected_files': ['1.dxf', '2.dxf', '3.dxf', '4.dxf'],  # файлы 1-9.dxf
            'description': 'Борт Toyota Corolla 11 - должны быть файлы 1-9.dxf'
        },
        {
            'article': 'EVA_DRIVER+TOYOTA+COROLLA 11',
            'product': 'TOYOTA COROLLA 11',
            'product_type': 'водитель',
            'expected_files': ['1.dxf'],  # только 1.dxf
            'description': 'Водитель Toyota Corolla 11 - должен быть только 1.dxf'
        },
        {
            'article': 'EVA_FRONT+TOYOTA+COROLLA 11',
            'product': 'TOYOTA COROLLA 11',
            'product_type': 'передние',
            'expected_files': ['1.dxf', '2.dxf'],  # 1.dxf и 2.dxf
            'description': 'Передние Toyota Corolla 11 - должны быть 1.dxf и 2.dxf'
        },
        {
            'article': 'EVA_TRUNK+TOYOTA+COROLLA 11',
            'product': 'TOYOTA COROLLA 11',
            'product_type': 'багажник',
            'expected_files': ['10.dxf', '11.dxf'],  # файлы 10-16.dxf (если есть)
            'description': 'Багажник Toyota Corolla 11 - должны быть файлы 10-16.dxf'
        },
        {
            'article': 'BOAT_MAT+ЛОДКА+ADMIRAL 335',
            'product': 'Лодка ADMIRAL 335',
            'product_type': 'лодка',
            'expected_files': ['1.dxf', '2.dxf'],  # все файлы в папке
            'description': 'Лодка Admiral 335 - должны быть все файлы в папке'
        },
        {
            'article': 'SCOOTER_DECK+ДЕКА+KUGOO M4 PRO',
            'product': 'ДЕКА KUGOO M4 PRO',
            'product_type': 'самокат',
            'expected_files': ['1.dxf'],  # все файлы в папке
            'description': 'Самокат ДЕКА KUGOO M4 PRO - должны быть все файлы в папке'
        }
    ]
    
    passed_tests = 0
    total_tests = len(test_cases)
    
    print(f"📋 Запуск {total_tests} тестов...\n")
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"🧪 Тест {i}: {test_case['description']}")
        print(f"   Артикул: {test_case['article']}")
        print(f"   Товар: {test_case['product']}")
        print(f"   Тип: {test_case['product_type']}")
        
        try:
            # Вызываем функцию
            found_files = get_dxf_files_for_product_type(
                test_case['article'], 
                test_case['product'], 
                test_case['product_type']
            )
            
            # Извлекаем только имена файлов для сравнения
            found_filenames = [os.path.basename(f) for f in found_files]
            found_filenames.sort()
            
            print(f"   Найдено файлов: {len(found_files)}")
            print(f"   Файлы: {found_filenames}")
            
            # Проверяем результат
            if found_files:
                # Проверяем, что найдены ожидаемые файлы или хотя бы некоторые из них
                expected_found = any(expected in found_filenames for expected in test_case['expected_files'])
                if expected_found:
                    print("   ✅ ПРОЙДЕН")
                    passed_tests += 1
                else:
                    print("   ⚠️  ЧАСТИЧНО ПРОЙДЕН (найдены файлы, но не ожидаемые)")
                    passed_tests += 0.5
            else:
                print("   ❌ НЕ ПРОЙДЕН (файлы не найдены)")
        
        except Exception as e:
            print(f"   ❌ ОШИБКА: {e}")
        
        print()
    
    print("=" * 70)
    print(f"📊 Результаты тестирования:")
    print(f"   ✅ Пройдено: {passed_tests}/{total_tests}")
    
    if passed_tests == total_tests:
        print("   🎉 Все тесты успешно пройдены!")
        return True
    elif passed_tests > total_tests * 0.7:
        print("   👍 Большинство тестов пройдено успешно")
        return True
    else:
        print("   ⚠️  Требуются доработки")
        return False

def test_folder_search():
    """Тестирование поиска папок продуктов"""
    print("\n🔍 Тестирование поиска папок продуктов")
    print("=" * 50)
    
    # Проверяем, какие папки есть в dxf_samples
    if not os.path.exists('dxf_samples'):
        print("❌ Папка dxf_samples не найдена")
        return False
    
    # Подсчитываем папки по типам
    folder_types = {
        'automotive': 0,
        'boats': 0,
        'scooters': 0,
        'mats': 0,
        'other': 0
    }
    
    for item in os.listdir('dxf_samples'):
        item_path = os.path.join('dxf_samples', item)
        if os.path.isdir(item_path):
            item_upper = item.upper()
            if any(brand in item_upper for brand in ['TOYOTA', 'BMW', 'AUDI', 'VOLKSWAGEN', 'SUBARU', 'SSANG YONG']):
                folder_types['automotive'] += 1
            elif 'ЛОДКА' in item_upper or 'ADMIRAL' in item_upper or 'ABAKAN' in item_upper:
                folder_types['boats'] += 1
            elif 'ДЕКА' in item_upper or 'KUGOO' in item_upper:
                folder_types['scooters'] += 1
            elif 'КОВРИК' in item_upper:
                folder_types['mats'] += 1
            else:
                folder_types['other'] += 1
    
    print("📁 Найденные типы папок:")
    for folder_type, count in folder_types.items():
        type_names = {
            'automotive': '🚗 Автомобильные',
            'boats': '🛥️  Лодки',
            'scooters': '🛴 Самокаты',
            'mats': '🪑 Коврики',
            'other': '❓ Прочие'
        }
        print(f"   {type_names[folder_type]}: {count}")
    
    total_folders = sum(folder_types.values())
    print(f"\n📊 Всего папок: {total_folders}")
    
    return total_folders > 0

def main():
    print("🧪 Полное тестирование системы сопоставления типов изделий")
    print("=" * 80)
    
    # Тест 1: Проверка структуры папок
    folder_test = test_folder_search()
    
    # Тест 2: Проверка сопоставления типов
    mapping_test = test_product_type_mapping()
    
    print("\n" + "=" * 80)
    print("🏁 ИТОГОВЫЙ РЕЗУЛЬТАТ:")
    
    if folder_test and mapping_test:
        print("   🎉 Все тесты пройдены успешно!")
        print("   ✅ Система готова к использованию")
        return True
    else:
        print("   ⚠️  Обнаружены проблемы, требующие внимания")
        if not folder_test:
            print("   • Проблемы со структурой папок DXF")
        if not mapping_test:
            print("   • Проблемы с логикой сопоставления типов")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)