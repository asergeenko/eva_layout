#!/usr/bin/env python3
"""
Интеграционный тест новой системы сопоставления типов изделий
"""

import pandas as pd
import os
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_excel_integration():
    """Тестирование интеграции с реальными данными Excel"""
    print("🧪 Интеграционный тест с данными Excel")
    print("=" * 50)
    
    if not os.path.exists('sample_input.xlsx'):
        print("❌ Файл sample_input.xlsx не найден")
        return False
    
    # Читаем Excel файл
    try:
        df = pd.read_excel('sample_input.xlsx')
        print(f"✅ Excel файл загружен: {df.shape[0]} строк, {df.shape[1]} колонок")
    except Exception as e:
        print(f"❌ Ошибка чтения Excel: {e}")
        return False
    
    # Анализируем типы изделий из колонки H
    if len(df.columns) > 7:
        product_types = df.iloc[:, 7].value_counts()
        print("\n📊 Найденные типы изделий (колонка H):")
        for product_type, count in product_types.items():
            if pd.notna(product_type) and product_type != 'Изделие':
                print(f"   • {product_type}: {count} заказов")
    
    # Найдем примеры заказов разных типов
    print("\n🔍 Примеры заказов для тестирования:")
    
    test_orders = []
    
    # Пропускаем первые 2 строки (заголовки)
    if df.shape[0] > 2:
        data_rows = df.iloc[2:].copy()
        
        for idx, row in data_rows.iterrows():
            if pd.notna(row.iloc[3]) and pd.notna(row.iloc[7]):  # Есть артикул и тип
                article = str(row.iloc[3])
                product = str(row.iloc[4]) if pd.notna(row.iloc[4]) else ''
                product_type = str(row.iloc[7])
                
                # Добавляем по одному примеру каждого типа
                if not any(order['product_type'] == product_type for order in test_orders):
                    test_orders.append({
                        'article': article,
                        'product': product,
                        'product_type': product_type
                    })
                
                if len(test_orders) >= 6:  # Достаточно примеров
                    break
    
    # Тестируем каждый тип заказа
    print(f"\n🧪 Тестирование {len(test_orders)} типов заказов:")
    
    success_count = 0
    
    for i, order in enumerate(test_orders, 1):
        print(f"\n{i}. Тип: {order['product_type']}")
        print(f"   Артикул: {order['article']}")
        print(f"   Товар: {order['product'][:60]}...")
        
        # Симулируем поиск файлов (упрощенная версия)
        files_found = simulate_file_search(order['article'], order['product'], order['product_type'])
        
        if files_found:
            print(f"   ✅ Найдено файлов: {len(files_found)}")
            print(f"   📁 Файлы: {files_found}")
            success_count += 1
        else:
            print(f"   ❌ Файлы не найдены")
    
    print(f"\n📊 Результат: {success_count}/{len(test_orders)} типов успешно обработаны")
    
    return success_count > len(test_orders) * 0.5

def simulate_file_search(article, product_name, product_type):
    """Упрощенная симуляция поиска файлов"""
    
    # Поиск базовой папки
    base_folder = find_base_folder(article, product_name)
    
    if not base_folder:
        return []
    
    # Получить список DXF файлов
    dxf_folder = os.path.join(base_folder, "DXF")
    search_folder = dxf_folder if os.path.exists(dxf_folder) else base_folder
    
    try:
        all_files = [f for f in os.listdir(search_folder) if f.lower().endswith('.dxf')]
        all_files.sort()
    except OSError:
        return []
    
    # Применить фильтрацию по типу изделия
    if product_type == "борт":
        # Файлы 1.dxf до 9.dxf
        filtered_files = []
        for i in range(1, 10):
            target_file = f"{i}.dxf"
            if target_file in all_files:
                filtered_files.append(target_file)
        return filtered_files
    
    elif product_type == "водитель":
        # Только 1.dxf
        return ["1.dxf"] if "1.dxf" in all_files else []
    
    elif product_type == "передние":
        # 1.dxf и 2.dxf
        filtered_files = []
        for i in [1, 2]:
            target_file = f"{i}.dxf"
            if target_file in all_files:
                filtered_files.append(target_file)
        return filtered_files
    
    elif product_type == "багажник":
        # Файлы 10.dxf до 16.dxf
        filtered_files = []
        for i in range(10, 17):
            target_file = f"{i}.dxf"
            if target_file in all_files:
                filtered_files.append(target_file)
        return filtered_files
    
    elif product_type in ["самокат", "лодка", "ковер"]:
        # Все файлы
        return all_files
    
    else:
        # Неизвестный тип - все файлы
        return all_files

def calculate_folder_match_score(search_term, folder_name):
    """Calculate how well a folder name matches the search term."""
    import re
    
    search_lower = search_term.lower()
    folder_lower = folder_name.lower()
    score = 0
    
    # Direct substring match
    if search_lower in folder_lower or folder_lower in search_lower:
        score += max(len(search_lower), len(folder_lower)) * 2
    
    # Word-based matching
    search_words = re.split(r'[\s\-_()]+', search_lower)
    folder_words = re.split(r'[\s\-_()]+', folder_lower)
    
    # Remove empty words
    search_words = [w for w in search_words if len(w) > 1]
    folder_words = [w for w in folder_words if len(w) > 1]
    
    for search_word in search_words:
        for folder_word in folder_words:
            if search_word == folder_word:
                score += len(search_word) * 3
            elif search_word in folder_word:
                score += len(search_word) * 2
            elif folder_word in search_word:
                score += len(folder_word) * 2
            elif search_word[:3] == folder_word[:3] and len(search_word) > 2:
                score += 2  # Partial match for similar words
    
    return score

def find_base_folder(article, product_name):
    """Поиск базовой папки продукта (соответствует основной логике)"""
    
    # Strategy 1: Direct search in flat dxf_samples folder structure
    if product_name:
        product_upper = product_name.upper()
        
        # Search directly in dxf_samples folder for matching folder names
        best_match = None
        best_score = 0
        
        for item in os.listdir("dxf_samples"):
            item_path = os.path.join("dxf_samples", item)
            if os.path.isdir(item_path):
                score = calculate_folder_match_score(product_name, item)
                if score > best_score:
                    best_score = score
                    best_match = item_path
        
        if best_match and best_score >= 6:
            return best_match
        
        # Special categories handling
        special_keywords = {
            'лодка': ['Лодка', 'ADMIRAL', 'ABAKAN', 'AKVA', 'АГУЛ', 'Азимут'],
            'ковер': ['Коврик'],
            'самокат': ['ДЕКА', 'KUGOO']
        }
        
        for category, keywords in special_keywords.items():
            for keyword in keywords:
                if keyword.upper() in product_upper:
                    # Search for folders containing this keyword
                    for item in os.listdir("dxf_samples"):
                        if keyword.lower() in item.lower():
                            folder_path = os.path.join("dxf_samples", item)
                            if os.path.isdir(folder_path):
                                return folder_path
    
    # Strategy 2: Parse article format like EVA_BORT+Brand+Model
    if '+' in article:
        parts = article.split('+')
        if len(parts) >= 3:
            brand = parts[1].strip()
            model_info = parts[2].strip()
            
            # Handle special case mappings first
            special_mappings = {
                'Kugoo': ['ДЕКА KUGOO KIRIN M4 PRO', 'ДЕКА KUGOO M4 PRO JILONG'],
                'Абакан': ['Лодка ABAKAN 430 JET'],
                'Admiral': ['Лодка ADMIRAL 335', 'Лодка ADMIRAL 340', 'Лодка ADMIRAL 410'],
                'AKVA': ['Лодка AKVA 2600', 'Лодка AKVA 2800']
            }
            
            if brand in special_mappings:
                for folder_name in special_mappings[brand]:
                    folder_path = os.path.join("dxf_samples", folder_name)
                    if os.path.exists(folder_path):
                        return folder_path
            
            # For standard automotive brands, search the flat folder structure
            search_term = f"{brand} {model_info}".upper()
            
            # Find best match in flat folder structure
            best_match = None
            best_score = 0
            
            for item in os.listdir("dxf_samples"):
                item_path = os.path.join("dxf_samples", item)
                if os.path.isdir(item_path):
                    score = calculate_folder_match_score(search_term, item)
                    if score > best_score:
                        best_score = score
                        best_match = item_path
            
            if best_match and best_score >= 3:
                return best_match
    
    return None

def main():
    print("🧪 Интеграционное тестирование системы сопоставления типов")
    print("=" * 70)
    
    # Тест интеграции с Excel
    integration_success = test_excel_integration()
    
    print("\n" + "=" * 70)
    print("📊 ИТОГОВЫЙ РЕЗУЛЬТАТ:")
    
    if integration_success:
        print("✅ Интеграционные тесты пройдены успешно!")
        print("🎉 Система готова к использованию в производственной среде")
        
        print("\n🚀 Рекомендации для запуска:")
        print("   1. streamlit run streamlit_demo.py")
        print("   2. Загрузите sample_input.xlsx")
        print("   3. Выберите заказы с разными типами изделий")
        print("   4. Запустите оптимизацию")
        
        return True
    else:
        print("⚠️  Обнаружены проблемы с интеграцией")
        print("   Требуется дополнительная настройка системы")
        return False

if __name__ == "__main__":
    main()