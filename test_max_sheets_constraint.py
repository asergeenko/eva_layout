#!/usr/bin/env python3

"""
Test to verify MAX_SHEETS_PER_ORDER constraint is strictly enforced
"""

import logging
from shapely.geometry import Polygon
from layout_optimizer import bin_packing_with_inventory, Carpet

# Включаем DEBUG логирование для отслеживания ограничений
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s - %(message)s')

def create_constraint_violation_test():
    """Create test data that would violate MAX_SHEETS_PER_ORDER without proper checks"""
    
    # Создаем листы с ограниченным местом для принудительного создания многих листов
    available_sheets = []
    
    black_sheet = {
        "name": "Лист 140x200 чёрный", 
        "width": 140, 
        "height": 200,
        "color": "чёрный", 
        "count": 10,  # Много листов, но с небольшим местом
        "used": 0,
    }
    available_sheets.append(black_sheet)
    
    # Создаем заказ с многими полигонами, которые не поместятся в ограничение
    carpets = []
    
    # Заказ SUZUKI_XBEE - тот, который нарушал ограничение
    order_id = "ZAKAZ_row_7"  # SUZUKI XBEE из реального теста
    color = "чёрный"
    
    # Создаем 15 крупных полигонов для этого заказа
    for i in range(15):
        filename = f"suzuki_xbee_{i}.dxf"
        
        # Крупные полигоны ~80x80мм, чтобы на листе помещалось мало
        size = 75 + (i % 3) * 5  # 75-85мм
        polygon = Polygon([(0, 0), (size, 0), (size, size), (0, size)])
        
        carpet = Carpet(
            polygon=polygon,
            filename=filename,
            color=color,
            order_id=order_id,
            priority=1  # Приоритет 1 - из Excel файла
        )
        carpets.append(carpet)
    
    # Добавим еще несколько других заказов для создания помех
    for other_order in range(3):
        other_order_id = f"OTHER_ORDER_{other_order}"
        
        for j in range(5):
            filename = f"other_{other_order}_{j}.dxf"
            size = 60 + j * 5  # 60-80мм
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

def verify_max_sheets_constraint(placed_layouts, max_sheets_per_order):
    """Verify that MAX_SHEETS_PER_ORDER constraint is not violated"""
    
    # Собираем информацию о размещении по заказам
    order_sheets = {}  # order_id -> set of sheet_numbers
    
    for layout in placed_layouts:
        sheet_number = layout["sheet_number"]
        placed_polygons = layout["placed_polygons"]
        
        for placed_tuple in placed_polygons:
            # Извлекаем order_id из размещенного полигона
            if len(placed_tuple) >= 7:
                # Extended format: (polygon, x, y, angle, filename, color, order_id)
                order_id = placed_tuple[6]
            elif len(placed_tuple) >= 4:
                # Standard format: (polygon, filename, color, order_id)
                order_id = placed_tuple[3]
            else:
                continue  # Неопределенный формат
            
            if order_id not in order_sheets:
                order_sheets[order_id] = set()
            order_sheets[order_id].add(sheet_number)
    
    # Проверяем ограничения
    violations = []
    
    for order_id, sheets in order_sheets.items():
        # Пропускаем системные заказы
        if order_id in ["additional", "unknown"] or str(order_id).startswith("group_"):
            continue
        
        sheets_list = sorted(sheets)
        sheets_count = len(sheets_list)
        
        print(f"Заказ {order_id}: листы {sheets_list} (всего {sheets_count})")
        
        if sheets_count > max_sheets_per_order:
            violations.append(f"Заказ {order_id}: {sheets_count} листов > MAX_SHEETS_PER_ORDER={max_sheets_per_order}")
        
        # Проверяем смежность (диапазон не должен превышать MAX_SHEETS_PER_ORDER)
        if sheets_list:
            min_sheet = min(sheets_list)
            max_sheet = max(sheets_list)
            sheet_range = max_sheet - min_sheet + 1
            
            if sheet_range > max_sheets_per_order:
                violations.append(f"Заказ {order_id}: диапазон листов {min_sheet}-{max_sheet} ({sheet_range}) > MAX_SHEETS_PER_ORDER={max_sheets_per_order}")
    
    return violations

def main():
    print("=== ТЕСТ СОБЛЮДЕНИЯ ОГРАНИЧЕНИЯ MAX_SHEETS_PER_ORDER ===")
    
    available_sheets, carpets = create_constraint_violation_test()
    MAX_SHEETS_PER_ORDER = 5
    
    print(f"Создано {len(available_sheets)} типов листов")
    print(f"Создано {len(carpets)} ковров")
    print(f"MAX_SHEETS_PER_ORDER = {MAX_SHEETS_PER_ORDER}")
    
    # Подсчитываем ковры по заказам
    orders = {}
    for carpet in carpets:
        if carpet.order_id not in orders:
            orders[carpet.order_id] = 0
        orders[carpet.order_id] += 1
    
    print(f"\nЗаказы:")
    for order_id, count in orders.items():
        print(f"  {order_id}: {count} ковров")
    
    print(f"\n=== ЗАПУСК ОПТИМИЗАЦИИ ===")
    
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
        
        # Проверяем соблюдение ограничений
        print(f"\n=== ПРОВЕРКА ОГРАНИЧЕНИЙ ===")
        violations = verify_max_sheets_constraint(placed_layouts, MAX_SHEETS_PER_ORDER)
        
        if not violations:
            print("✅ ВСЕ ОГРАНИЧЕНИЯ СОБЛЮДЕНЫ!")
            print("✅ MAX_SHEETS_PER_ORDER работает корректно")
        else:
            print("❌ ОБНАРУЖЕНЫ НАРУШЕНИЯ:")
            for violation in violations:
                print(f"  ❌ {violation}")
            print("\n❌ ТРЕБУЕТСЯ ДОПОЛНИТЕЛЬНОЕ ИСПРАВЛЕНИЕ АЛГОРИТМА")
        
        # Детальная информация по листам
        if placed_layouts:
            print(f"\nДетали по листам:")
            for layout in placed_layouts:
                print(f"  Лист {layout['sheet_number']}: {len(layout['placed_polygons'])} ковров, {layout.get('usage_percent', 0):.1f}%")
        
    except Exception as e:
        print(f"❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()