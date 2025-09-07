#!/usr/bin/env python3
"""
Детальная проверка нарушений MAX_SHEETS_PER_ORDER=5
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from layout_optimizer import bin_packing_with_inventory
from tests.test_streamlit_integration2 import (
    load_sample_input_data, 
    create_available_sheets, 
    process_orders_from_excel, 
    create_priority2_polygons
)

def main():
    print("=== ДЕТАЛЬНАЯ ПРОВЕРКА MAX_SHEETS_PER_ORDER ===")
    
    # Загружаем данные
    df = load_sample_input_data()
    available_sheets = create_available_sheets()
    polygons = process_orders_from_excel(df)
    priority2_polygons = create_priority2_polygons()
    all_polygons = polygons + priority2_polygons
    
    # Запускаем оптимизацию
    MAX_SHEETS_PER_ORDER = 5
    placed_layouts, unplaced = bin_packing_with_inventory(
        all_polygons,
        available_sheets,
        verbose=False,
        max_sheets_per_order=MAX_SHEETS_PER_ORDER,
    )
    
    print(f"\n=== АНАЛИЗ РАЗМЕЩЕНИЯ ЗАКАЗОВ ===")
    print(f"Всего листов: {len(placed_layouts)}")
    print(f"MAX_SHEETS_PER_ORDER: {MAX_SHEETS_PER_ORDER}")
    
    # Собираем информацию о заказах по листам
    order_sheets = {}  # order_id -> set of sheet_numbers
    
    for layout in placed_layouts:
        sheet_num = layout["sheet_number"]
        for poly_tuple in layout["placed_polygons"]:
            # Извлекаем order_id из tuple
            order_id = None
            if len(poly_tuple) >= 7:
                order_id = poly_tuple[6]  # Extended format
            elif len(poly_tuple) >= 4:
                order_id = poly_tuple[3]  # Standard format
            
            if order_id and str(order_id).startswith("ZAKAZ_"):
                order_id = str(order_id)
                if order_id not in order_sheets:
                    order_sheets[order_id] = set()
                order_sheets[order_id].add(sheet_num)
    
    # Проверяем нарушения
    violations = []
    for order_id, sheets in order_sheets.items():
        if len(sheets) > 1:  # Только заказы на нескольких листах
            min_sheet = min(sheets)
            max_sheet = max(sheets)
            sheet_range = max_sheet - min_sheet + 1
            
            sheets_list = sorted(list(sheets))
            
            if sheet_range > MAX_SHEETS_PER_ORDER:
                violations.append({
                    'order_id': order_id,
                    'sheets': sheets_list,
                    'range': sheet_range,
                    'min_sheet': min_sheet,
                    'max_sheet': max_sheet
                })
            
            print(f"  {order_id}: листы {sheets_list}, диапазон {min_sheet}-{max_sheet} = {sheet_range}")
    
    if violations:
        print(f"\n❌ НАЙДЕНЫ НАРУШЕНИЯ MAX_SHEETS_PER_ORDER={MAX_SHEETS_PER_ORDER}:")
        for v in violations:
            print(f"   • {v['order_id']}: листы {v['sheets']}, диапазон {v['range']} > {MAX_SHEETS_PER_ORDER}")
    else:
        print(f"\n✅ Нарушений MAX_SHEETS_PER_ORDER={MAX_SHEETS_PER_ORDER} не найдено")
        
        # Показываем заказы на нескольких листах, но без нарушений
        multi_sheet_orders = [order_id for order_id, sheets in order_sheets.items() if len(sheets) > 1]
        if multi_sheet_orders:
            print(f"\n📊 Заказы на нескольких листах (без нарушений):")
            for order_id in sorted(multi_sheet_orders):
                sheets = sorted(list(order_sheets[order_id]))
                min_sheet = min(sheets)
                max_sheet = max(sheets)
                sheet_range = max_sheet - min_sheet + 1
                print(f"   • {order_id}: листы {sheets}, диапазон {sheet_range}")

if __name__ == "__main__":
    main()