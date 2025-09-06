#!/usr/bin/env python3

"""
Test with LARGE polygons that MUST create multiple sheets to test MAX_SHEETS_PER_ORDER
"""

import logging
from shapely.geometry import Polygon
from layout_optimizer import bin_packing_with_inventory, Carpet

# Включаем INFO логирование для видимости процесса
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')

def create_multi_sheet_test():
    """Create test with large polygons that require multiple sheets"""
    
    # Маленькие листы для принуждения к созданию многих листов
    available_sheets = []
    
    black_sheet = {
        "name": "Лист 140x200 чёрный", 
        "width": 140,  # 140cm = 1400mm
        "height": 200, # 200cm = 2000mm
        "color": "чёрный", 
        "count": 20,  # Много листов доступно
        "used": 0,
    }
    available_sheets.append(black_sheet)
    
    carpets = []
    
    # Заказ SUZUKI_XBEE - должен помещаться в MAX_SHEETS_PER_ORDER=5
    order_id = "ZAKAZ_row_7"
    color = "чёрный"
    
    # Создаем 20 ОЧЕНЬ КРУПНЫХ полигонов - по ~800x800мм каждый
    # На лист 1400x2000мм поместится максимум 2-3 таких полигона
    for i in range(20):
        filename = f"huge_suzuki_{i}.dxf"
        
        # Огромные полигоны 800x800мм - должны принудить к созданию многих листов
        size = 800  # 800мм = 80см - очень крупные
        polygon = Polygon([(0, 0), (size, 0), (size, size), (0, size)])
        
        carpet = Carpet(
            polygon=polygon,
            filename=filename,
            color=color,
            order_id=order_id,
            priority=1
        )
        carpets.append(carpet)
    
    # Добавим другие заказы для создания реалистичной обстановки
    for other_order in range(2):
        other_order_id = f"OTHER_LARGE_{other_order}"
        
        for j in range(8):  # По 8 крупных ковров
            filename = f"other_large_{other_order}_{j}.dxf"
            size = 750  # 750мм
            polygon = Polygon([(0, 0), (size, 0), (size, size), (0, size)])
            
            carpet = Carpet(
                polygon=polygon,
                filename=filename,
                color=color,
                order_id=other_order_id,
                priority=1
            )
            carpets.append(carpet)
    
    return available_sheets, carpets

def verify_max_sheets_constraint_detailed(placed_layouts, max_sheets_per_order):
    """Detailed verification of MAX_SHEETS_PER_ORDER constraint"""
    
    order_sheets = {}
    
    for layout in placed_layouts:
        sheet_number = layout["sheet_number"]
        placed_polygons = layout["placed_polygons"]
        
        print(f"Лист {sheet_number}: {len(placed_polygons)} полигонов")
        
        for placed_tuple in placed_polygons:
            if len(placed_tuple) >= 7:
                order_id = placed_tuple[6]
                filename = placed_tuple[4]
            elif len(placed_tuple) >= 4:
                order_id = placed_tuple[3]
                filename = placed_tuple[1]
            else:
                continue
            
            if order_id not in order_sheets:
                order_sheets[order_id] = set()
            order_sheets[order_id].add(sheet_number)
            
            print(f"  - {filename} (заказ {order_id})")
    
    print(f"\n=== АНАЛИЗ СОБЛЮДЕНИЯ ОГРАНИЧЕНИЙ ===")
    violations = []
    
    for order_id, sheets in order_sheets.items():
        if order_id in ["additional", "unknown"] or str(order_id).startswith("group_"):
            continue
        
        sheets_list = sorted(sheets)
        min_sheet = min(sheets_list)
        max_sheet = max(sheets_list)
        sheet_range = max_sheet - min_sheet + 1
        
        print(f"Заказ {order_id}:")
        print(f"  Листы: {sheets_list}")
        print(f"  Диапазон: {min_sheet}-{max_sheet} ({sheet_range} листов)")
        
        if sheet_range > max_sheets_per_order:
            violation = f"Заказ {order_id}: диапазон {min_sheet}-{max_sheet} ({sheet_range}) > MAX_SHEETS_PER_ORDER={max_sheets_per_order}"
            violations.append(violation)
            print(f"  ❌ НАРУШЕНИЕ: {violation}")
        else:
            print(f"  ✅ СОБЛЮДЕНО: диапазон {sheet_range} <= {max_sheets_per_order}")
    
    return violations

def main():
    print("=== ТЕСТ С КРУПНЫМИ ПОЛИГОНАМИ (ПРИНУДИТЕЛЬНОЕ СОЗДАНИЕ МНОГИХ ЛИСТОВ) ===")
    
    available_sheets, carpets = create_multi_sheet_test()
    MAX_SHEETS_PER_ORDER = 5
    
    print(f"Создано {len(available_sheets)} типов листов (140x200 см)")
    print(f"Создано {len(carpets)} ковров (каждый ~80x80 см)")
    print(f"MAX_SHEETS_PER_ORDER = {MAX_SHEETS_PER_ORDER}")
    
    # Подсчитываем ковры по заказам
    orders = {}
    for carpet in carpets:
        if carpet.order_id not in orders:
            orders[carpet.order_id] = 0
        orders[carpet.order_id] += 1
    
    print(f"\nЗаказы:")
    for order_id, count in orders.items():
        print(f"  {order_id}: {count} крупных ковров (~80x80см каждый)")
    
    print(f"\nОжидаем: каждый лист вместит ~2-3 крупных ковра")
    print(f"Ожидаем: заказ ZAKAZ_row_7 (20 ковров) займет ~7-10 листов")
    print(f"КРИТИЧНО: Если займет >5 листов, должно быть нарушение!\n")
    
    try:
        placed_layouts, unplaced_carpets = bin_packing_with_inventory(
            carpets,
            available_sheets,
            verbose=False,
            max_sheets_per_order=MAX_SHEETS_PER_ORDER,
        )
        
        print(f"\n=== РЕЗУЛЬТАТЫ ===")
        print(f"Размещенных листов: {len(placed_layouts)}")
        print(f"Неразмещенных ковров: {len(unplaced_carpets)}")
        
        if unplaced_carpets:
            print(f"\nНеразмещенные ковры:")
            for carpet in unplaced_carpets[:10]:  # Показываем первые 10
                if hasattr(carpet, 'filename'):
                    print(f"  - {carpet.filename} (заказ {carpet.order_id})")
            if len(unplaced_carpets) > 10:
                print(f"  ... еще {len(unplaced_carpets) - 10} ковров")
        
        # Детальная проверка ограничений
        violations = verify_max_sheets_constraint_detailed(placed_layouts, MAX_SHEETS_PER_ORDER)
        
        print(f"\n=== ИТОГОВАЯ ОЦЕНКА ===")
        if not violations:
            print("✅ ВСЕ ОГРАНИЧЕНИЯ СОБЛЮДЕНЫ!")
            print("✅ MAX_SHEETS_PER_ORDER работает корректно даже с крупными полигонами")
        else:
            print("❌ ОБНАРУЖЕНЫ КРИТИЧЕСКИЕ НАРУШЕНИЯ:")
            for violation in violations:
                print(f"  ❌ {violation}")
            print("\n❌❌ АЛГОРИТМ ТРЕБУЕТ ДОПОЛНИТЕЛЬНОГО ИСПРАВЛЕНИЯ!")
        
    except Exception as e:
        print(f"❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()