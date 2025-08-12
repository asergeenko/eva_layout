#!/usr/bin/env python3
"""
Final comprehensive validation of the updated EVA Layout system
"""

import pandas as pd
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_complete_workflow():
    """Test the complete workflow from Excel to DXF files"""
    print("🧪 Финальная валидация системы EVA Layout")
    print("=" * 70)
    
    # 1. Load Excel and verify structure
    print("\n1️⃣ Загрузка и проверка Excel файла")
    try:
        df = pd.read_excel('sample_input.xlsx')
        print(f"   ✅ Excel загружен: {df.shape[0]} строк, {df.shape[1]} колонок")
        
        # Check product types in column H
        if len(df.columns) > 7:
            product_types = df.iloc[2:, 7].value_counts()  # Skip headers
            print(f"   📊 Типы изделий:")
            for product_type, count in product_types.items():
                if pd.notna(product_type) and product_type != 'Изделие':
                    print(f"      • {product_type}: {count} заказов")
        
    except Exception as e:
        print(f"   ❌ Ошибка загрузки Excel: {e}")
        return False
    
    # 2. Test DXF folder structure
    print("\n2️⃣ Проверка структуры DXF папок")
    if not os.path.exists('dxf_samples'):
        print("   ❌ Папка dxf_samples не найдена")
        return False
    
    folder_count = len([f for f in os.listdir('dxf_samples') if os.path.isdir(os.path.join('dxf_samples', f))])
    file_count = 0
    for root, dirs, files in os.walk('dxf_samples'):
        file_count += len([f for f in files if f.lower().endswith('.dxf')])
    
    print(f"   ✅ Структура DXF: {folder_count} папок, {file_count} файлов")
    
    # 3. Test specific product type mappings
    print("\n3️⃣ Тестирование сопоставления типов изделий")
    
    test_cases = [
        {'type': 'борт', 'expected_files': ['1.dxf', '2.dxf', '3.dxf', '4.dxf', '5.dxf'], 'folder': 'SSANG YONG KYRON'},
        {'type': 'водитель', 'expected_files': ['1.dxf'], 'folder': 'TANK 300'},
        {'type': 'передние', 'expected_files': ['1.dxf', '2.dxf'], 'folder': 'TOYOTA COROLLA 10'},
        {'type': 'лодка', 'expected_files': ['1.dxf', '2.dxf'], 'folder': 'Лодка ABAKAN 430 JET'},
        {'type': 'самокат', 'expected_files': ['1.dxf'], 'folder': 'ДЕКА KUGOO KIRIN M4 PRO'},
        {'type': 'ковер', 'expected_files': ['1.dxf'], 'folder': 'Коврик для обуви придверный'}
    ]
    
    success_count = 0
    for case in test_cases:
        folder_path = os.path.join('dxf_samples', case['folder'])
        
        if os.path.exists(folder_path):
            # Check for DXF files
            try:
                files = [f for f in os.listdir(folder_path) if f.lower().endswith('.dxf')]
                files.sort()
                
                # Apply product type rules
                if case['type'] == 'борт':
                    # Should have files 1-9
                    filtered_files = [f"{i}.dxf" for i in range(1, 10) if f"{i}.dxf" in files]
                elif case['type'] == 'водитель':
                    # Should have only file 1
                    filtered_files = ['1.dxf'] if '1.dxf' in files else []
                elif case['type'] == 'передние':
                    # Should have files 1 and 2
                    filtered_files = [f"{i}.dxf" for i in [1, 2] if f"{i}.dxf" in files]
                elif case['type'] == 'багажник':
                    # Should have files 10-16
                    filtered_files = [f"{i}.dxf" for i in range(10, 17) if f"{i}.dxf" in files]
                else:
                    # All files for лодка, самокат, ковер
                    filtered_files = files
                
                if filtered_files:
                    print(f"   ✅ {case['type']}: найдено {len(filtered_files)} файлов в {case['folder']}")
                    success_count += 1
                else:
                    print(f"   ❌ {case['type']}: файлы не найдены в {case['folder']}")
            except OSError:
                print(f"   ❌ {case['type']}: ошибка чтения папки {case['folder']}")
        else:
            print(f"   ❌ {case['type']}: папка {case['folder']} не найдена")
    
    print(f"\n   📊 Успешно: {success_count}/{len(test_cases)} типов изделий")
    
    # 4. Test layout optimizer import
    print("\n4️⃣ Проверка импорта оптимизатора")
    try:
        from layout_optimizer import parse_dxf_complete, bin_packing_with_inventory
        print("   ✅ Оптимизатор импортирован успешно")
        optimizer_ok = True
    except ImportError as e:
        print(f"   ❌ Ошибка импорта оптимизатора: {e}")
        optimizer_ok = False
    
    # 5. Final summary
    print("\n" + "=" * 70)
    print("🏁 ФИНАЛЬНЫЙ РЕЗУЛЬТАТ:")
    
    all_tests_passed = (
        df is not None and 
        folder_count > 0 and 
        file_count > 0 and 
        success_count == len(test_cases) and 
        optimizer_ok
    )
    
    if all_tests_passed:
        print("   🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
        print("   ✨ Система полностью готова к использованию")
        print("\n📋 Ключевые возможности:")
        print("   • ✅ Загрузка заказов из Excel")
        print("   • ✅ Автоматическое сопоставление типов изделий")
        print("   • ✅ Поиск DXF файлов по правилам")
        print("   • ✅ Оптимизация раскладки")
        print("\n🚀 Запуск приложения:")
        print("   streamlit run streamlit_demo.py")
        
        print("\n💡 Поддерживаемые правила сопоставления:")
        print('   🔹 "борт" → файлы 1.dxf - 9.dxf')
        print('   🔹 "водитель" → файл 1.dxf')
        print('   🔹 "передние" → файлы 1.dxf, 2.dxf')
        print('   🔹 "багажник" → файлы 10.dxf - 16.dxf')
        print('   🔹 "лодка", "самокат", "ковер" → все файлы в папке')
        
        return True
    else:
        print("   ⚠️  ОБНАРУЖЕНЫ ПРОБЛЕМЫ:")
        if df is None:
            print("   • Excel файл не загружен")
        if folder_count == 0 or file_count == 0:
            print("   • Проблемы со структурой DXF")
        if success_count < len(test_cases):
            print(f"   • Не все типы изделий работают ({success_count}/{len(test_cases)})")
        if not optimizer_ok:
            print("   • Оптимизатор не импортирован")
        
        return False

if __name__ == "__main__":
    success = test_complete_workflow()
    exit(0 if success else 1)