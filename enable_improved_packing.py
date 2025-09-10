#!/usr/bin/env python3
"""
Скрипт для включения улучшенного алгоритма размещения.
Используйте этот скрипт если нужна максимальная плотность размещения
и скорость не критична.
"""

import sys
import os

def enable_improved_packing():
    """Включает улучшенный алгоритм размещения."""
    
    layout_optimizer_path = "layout_optimizer.py"
    
    if not os.path.exists(layout_optimizer_path):
        print("❌ Файл layout_optimizer.py не найден!")
        return False
    
    # Читаем содержимое файла
    with open(layout_optimizer_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Заменяем настройку
    old_setting = "USE_IMPROVED_PACKING_BY_DEFAULT = False"
    new_setting = "USE_IMPROVED_PACKING_BY_DEFAULT = True"
    
    if old_setting in content:
        new_content = content.replace(old_setting, new_setting)
        
        # Записываем обратно
        with open(layout_optimizer_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        print("✅ Улучшенный алгоритм размещения ВКЛЮЧЕН!")
        print("   Теперь программа будет использовать более точный алгоритм.")
        print("   Это может замедлить работу, но улучшить плотность размещения.")
        return True
    
    elif new_setting in content:
        print("ℹ️  Улучшенный алгоритм уже включен.")
        return True
    
    else:
        print("❌ Не удалось найти настройку в файле.")
        return False

def disable_improved_packing():
    """Отключает улучшенный алгоритм размещения."""
    
    layout_optimizer_path = "layout_optimizer.py"
    
    if not os.path.exists(layout_optimizer_path):
        print("❌ Файл layout_optimizer.py не найден!")
        return False
    
    # Читаем содержимое файла
    with open(layout_optimizer_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Заменяем настройку
    old_setting = "USE_IMPROVED_PACKING_BY_DEFAULT = True"
    new_setting = "USE_IMPROVED_PACKING_BY_DEFAULT = False"
    
    if old_setting in content:
        new_content = content.replace(old_setting, new_setting)
        
        # Записываем обратно
        with open(layout_optimizer_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        print("✅ Улучшенный алгоритм размещения ОТКЛЮЧЕН!")
        print("   Теперь программа будет использовать стандартный быстрый алгоритм.")
        return True
    
    elif new_setting in content:
        print("ℹ️  Улучшенный алгоритм уже отключен.")
        return True
    
    else:
        print("❌ Не удалось найти настройку в файле.")
        return False

def check_current_setting():
    """Проверяет текущую настройку алгоритма."""
    
    layout_optimizer_path = "layout_optimizer.py"
    
    if not os.path.exists(layout_optimizer_path):
        print("❌ Файл layout_optimizer.py не найден!")
        return None
    
    try:
        # Импортируем настройки
        sys.path.insert(0, os.path.dirname(os.path.abspath(layout_optimizer_path)))
        from layout_optimizer import (
            USE_IMPROVED_PACKING_BY_DEFAULT, IMPROVED_PACKING_AVAILABLE,
            USE_POLYGONAL_PACKING_BY_DEFAULT, POLYGONAL_PACKING_AVAILABLE
        )
        
        print("📊 ТЕКУЩИЕ НАСТРОЙКИ АЛГОРИТМОВ РАЗМЕЩЕНИЯ:")
        print(f"   Стандартный алгоритм: ✅ Всегда доступен")
        print(f"   Улучшенный алгоритм: {'✅ Да' if IMPROVED_PACKING_AVAILABLE else '❌ Нет'}")
        print(f"   Полигональный алгоритм: {'✅ Да' if POLYGONAL_PACKING_AVAILABLE else '❌ Нет'}")
        print()
        print(f"   Использовать улучшенный по умолчанию: {'✅ Да' if USE_IMPROVED_PACKING_BY_DEFAULT else '❌ Нет'}")
        print(f"   Использовать полигональный по умолчанию: {'✅ Да' if USE_POLYGONAL_PACKING_BY_DEFAULT else '❌ Нет'}")
        
        if POLYGONAL_PACKING_AVAILABLE and USE_POLYGONAL_PACKING_BY_DEFAULT:
            print("\n🔷 Активен: ПОЛИГОНАЛЬНЫЙ алгоритм")
            print("   • Истинно геометрический подход")  
            print("   • No-Fit Polygon технологии")
            print("   • Максимальная плотность размещения")
        elif IMPROVED_PACKING_AVAILABLE and USE_IMPROVED_PACKING_BY_DEFAULT:
            print("\n🚀 Активен: УЛУЧШЕННЫЙ алгоритм")
            print("   • Более точное размещение")  
            print("   • Лучшая плотность раскладки")
            print("   • Медленнее работает")
        else:
            print("\n⚡ Активен: СТАНДАРТНЫЙ алгоритм")
            print("   • Быстрая работа")
            print("   • Хорошее качество размещения")
        
        return {
            'improved': USE_IMPROVED_PACKING_BY_DEFAULT,
            'polygonal': USE_POLYGONAL_PACKING_BY_DEFAULT
        }
        
    except ImportError as e:
        print(f"❌ Ошибка импорта настроек: {e}")
        return None

if __name__ == "__main__":
    print("=== НАСТРОЙКА АЛГОРИТМА РАЗМЕЩЕНИЯ КОВРИКОВ ===\n")
    
    if len(sys.argv) < 2:
        print("Использование:")
        print("  python enable_improved_packing.py status   - показать текущие настройки")
        print("  python enable_improved_packing.py enable   - включить улучшенный алгоритм") 
        print("  python enable_improved_packing.py disable  - отключить улучшенный алгоритм")
        print()
        check_current_setting()
        sys.exit(0)
    
    command = sys.argv[1].lower()
    
    if command == "status":
        check_current_setting()
    elif command == "enable":
        enable_improved_packing()
    elif command == "disable": 
        disable_improved_packing()
    else:
        print(f"❌ Неизвестная команда: {command}")
        sys.exit(1)