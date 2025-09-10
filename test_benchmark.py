#!/usr/bin/env python3
"""
Бенчмарк-тест для сравнения алгоритмов размещения.
Тестируем реальный сценарий с тремя группами ковриков BMW и AUDI.
"""

import sys
import os
import time
import logging
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from layout_optimizer import (
    bin_packing_with_inventory, 
    parse_dxf_complete, 
    Carpet,
    USE_IMPROVED_PACKING_BY_DEFAULT
)

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_test_sheets():
    """Создает 5 черных листов 144*200."""
    return [
        {
            "name": "Черный лист 144x200",
            "width": 144,
            "height": 200,
            "color": "чёрный", 
            "count": 5,
            "used": 0
        }
    ]

def load_carpets_from_folder(folder_path: str, group_name: str) -> list[Carpet]:
    """Загружает все DXF файлы из указанной папки."""
    carpets = []
    folder = Path(folder_path)
    
    if not folder.exists():
        logger.error(f"Папка не найдена: {folder_path}")
        return carpets
    
    dxf_files = list(folder.glob("*.dxf"))
    logger.info(f"Найдено {len(dxf_files)} DXF файлов в {folder_path}")
    
    for dxf_file in dxf_files:
        try:
            # Используем verbose=False чтобы избежать Streamlit вызовов
            polygon_data = parse_dxf_complete(str(dxf_file), verbose=False)
            if polygon_data and polygon_data.get("combined_polygon"):
                polygon = polygon_data["combined_polygon"]
                filename = dxf_file.name
                carpets.append(Carpet(polygon, filename, "чёрный", group_name, 1))
                logger.debug(f"Загружен {filename}")
        except Exception as e:
            logger.warning(f"Ошибка загрузки {dxf_file}: {e}")
            continue
    
    logger.info(f"Успешно загружено {len(carpets)} ковриков из {group_name}")
    return carpets

def run_benchmark():
    """Запускает бенчмарк-тест."""
    print("=== БЕНЧМАРК-ТЕСТ АЛГОРИТМОВ РАЗМЕЩЕНИЯ ===")
    print("Клиент утверждает: эти ковры должны поместиться на 2 листа")
    print("Стандартный алгоритм: размещает на 3 листа")
    print("Цель: проверить улучшенный алгоритм\n")
    
    # Создаем листы
    available_sheets = create_test_sheets()
    print(f"📄 Подготовлено: {available_sheets[0]['count']} листов {available_sheets[0]['width']}x{available_sheets[0]['height']} см")
    
    # Загружаем группы ковриков
    carpet_groups = [
        ("dxf_samples/AUDI Q7 (4L) 1", "AUDI_Q7_4L_1"),
        ("dxf_samples/BMW X5 E53 1 и рестайлинг", "BMW_X5_E53_1"),
        ("dxf_samples/BMW X5 G05-G18 4 и рестайлинг", "BMW_X5_G05_G18_4"),
    ]
    
    all_carpets = []
    for folder_path, group_name in carpet_groups:
        carpets = load_carpets_from_folder(folder_path, group_name)
        all_carpets.extend(carpets)
        print(f"✅ {group_name}: {len(carpets)} ковриков")
    
    if not all_carpets:
        print("❌ Не удалось загрузить ковры. Проверьте пути к папкам.")
        return
    
    total_carpets = len(all_carpets)
    print(f"\n📊 Всего ковриков для размещения: {total_carpets}")
    
    # Вычисляем общую площадь
    total_area_mm2 = sum(carpet.polygon.area for carpet in all_carpets)
    sheet_area_mm2 = (available_sheets[0]['width'] * 10) * (available_sheets[0]['height'] * 10)
    theoretical_sheets = total_area_mm2 / sheet_area_mm2
    
    print(f"📐 Общая площадь ковриков: {total_area_mm2/100:.0f} см²")
    print(f"📐 Площадь одного листа: {sheet_area_mm2/100:.0f} см²") 
    print(f"📊 Теоретический минимум: {theoretical_sheets:.2f} листа")
    print(f"🎯 Цель клиента: 2 листа ({(total_area_mm2/(2*sheet_area_mm2))*100:.1f}% загрузка)")
    
    # Проверяем настройки алгоритма
    print(f"\n⚙️  Настройки: USE_IMPROVED_PACKING_BY_DEFAULT = {USE_IMPROVED_PACKING_BY_DEFAULT}")
    
    # Запускаем оптимизацию
    print(f"\n🚀 ЗАПУСК ОПТИМИЗАЦИИ...")
    print("-" * 50)
    
    start_time = time.time()
    
    def progress_callback(percent, status):
        if percent % 10 == 0:  # Показываем каждые 10%
            print(f"   {percent}% - {status}")
    
    try:
        placed_layouts, unplaced = bin_packing_with_inventory(
            all_carpets,
            available_sheets,
            verbose=True,
            progress_callback=progress_callback,
        )
        
        execution_time = time.time() - start_time
        
        print("-" * 50)
        print("📋 РЕЗУЛЬТАТЫ:")
        print(f"   Время выполнения: {execution_time:.1f} секунд")
        print(f"   Использовано листов: {len(placed_layouts)}")
        print(f"   Размещено ковриков: {total_carpets - len(unplaced)}/{total_carpets}")
        print(f"   Не размещено: {len(unplaced)} ковриков")
        
        if placed_layouts:
            # Анализ по листам
            print(f"\n📄 ДЕТАЛИ ПО ЛИСТАМ:")
            total_usage = 0
            for i, layout in enumerate(placed_layouts, 1):
                carpet_count = len(layout['placed_polygons'])
                usage = layout.get('usage_percent', 0)
                total_usage += usage
                print(f"   Лист {i}: {carpet_count} ковриков, {usage:.1f}% заполнение")
            
            avg_usage = total_usage / len(placed_layouts)
            print(f"   Среднее заполнение: {avg_usage:.1f}%")
        
        if unplaced:
            print(f"\n❌ НЕРАЗМЕЩЕННЫЕ КОВРЫ:")
            for carpet in unplaced:
                if hasattr(carpet, 'filename'):
                    bounds = carpet.polygon.bounds
                    size = f"{(bounds[2]-bounds[0])/10:.1f}x{(bounds[3]-bounds[1])/10:.1f}см"
                    print(f"   • {carpet.filename} ({size})")
        
        # Оценка результата
        print(f"\n🎯 ОЦЕНКА РЕЗУЛЬТАТА:")
        if len(placed_layouts) <= 2:
            print("   ✅ ОТЛИЧНО! Уложились в цель клиента (≤2 листа)")
        elif len(placed_layouts) == 3:
            print("   ⚠️  СТАНДАРТНО! Как обычный алгоритм (3 листа)")
        elif len(placed_layouts) > 3:
            print("   ❌ ПЛОХО! Хуже обычного алгоритма (>3 листов)")
        
        if len(unplaced) == 0:
            print("   ✅ Все ковры размещены!")
        else:
            print(f"   ❌ Не размещено {len(unplaced)} ковров")
            
        return {
            'sheets_used': len(placed_layouts),
            'carpets_placed': total_carpets - len(unplaced),
            'execution_time': execution_time,
            'average_usage': avg_usage if placed_layouts else 0,
            'unplaced_count': len(unplaced)
        }
        
    except Exception as e:
        print(f"❌ ОШИБКА при оптимизации: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    result = run_benchmark()
    
    if result:
        print(f"\n{'='*50}")
        print("📊 ИТОГОВЫЙ СЧЕТ:")
        print(f"   Листов использовано: {result['sheets_used']} (цель: ≤2)")
        print(f"   Ковров размещено: {result['carpets_placed']}")
        print(f"   Среднее заполнение: {result['average_usage']:.1f}%")
        print(f"   Время: {result['execution_time']:.1f} сек")
        
        if result['sheets_used'] <= 2 and result['unplaced_count'] == 0:
            print("🏆 АЛГОРИТМ ПРОШЕЛ ТЕСТ!")
        else:
            print("📈 АЛГОРИТМ ТРЕБУЕТ УЛУЧШЕНИЯ")
    
    print(f"\n🏁 Тест завершен")