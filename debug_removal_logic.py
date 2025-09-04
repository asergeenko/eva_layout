#!/usr/bin/env python3
"""
Debug script to trace polygon removal logic step by step
"""

import sys
import os
import pandas as pd
import logging
from shapely.geometry import Polygon

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set up detailed logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_problem_polygons():
    """Creates the specific problem polygons mentioned by user"""
    polygons = []
    
    # Create SUZUKI XBEE polygons (ZAKAZ_row_7)
    for i in range(5):
        size = 80 + i * 10
        poly = Polygon([(0, 0), (size, 0), (size, size-20), (0, size-20)])
        filename = f"SUZUKI XBEE_{i+1}.dxf"
        polygons.append((poly, filename, "чёрный", "ZAKAZ_row_7"))
    
    # Create ADMIRAL 335 polygons (ZAKAZ_row_29) 
    for i in range(3):
        size = 90 + i * 15
        poly = Polygon([(0, 0), (size, 0), (size, size-25), (0, size-25)])
        filename = f"Лодка ADMIRAL 335_{i+1}.dxf"
        polygons.append((poly, filename, "чёрный", "ZAKAZ_row_29"))
    
    # Create VOLKSWAGEN TIGUAN 1 polygons (ZAKAZ_row_17)
    for i in range(5):
        size = 85 + i * 12
        poly = Polygon([(0, 0), (size, 0), (size, size-18), (0, size-18)])
        filename = f"VOLKSWAGEN TIGUAN 1_{i+1}.dxf"
        polygons.append((poly, filename, "чёрный", "ZAKAZ_row_17"))
    
    return polygons

def simulate_bin_packing_result(polygons_to_place):
    """Simulates what bin_packing_with_existing returns"""
    # bin_packing_with_existing returns 7-element tuples:
    # (polygon, x_offset, y_offset, angle, filename, color, order_id)
    
    placed = []
    remaining = []
    
    # Simulate placing first 2 polygons from each order
    for poly in polygons_to_place:
        polygon, filename, color, order_id = poly
        
        # Simulate placing some polygons (first 2 from SUZUKI, first 1 from ADMIRAL, first 2 from VW)
        should_place = False
        if "SUZUKI XBEE" in filename and filename in ["SUZUKI XBEE_1.dxf", "SUZUKI XBEE_2.dxf"]:
            should_place = True
        elif "ADMIRAL 335" in filename and filename == "Лодка ADMIRAL 335_1.dxf":
            should_place = True  
        elif "VOLKSWAGEN TIGUAN 1" in filename and filename in ["VOLKSWAGEN TIGUAN 1_1.dxf", "VOLKSWAGEN TIGUAN 1_2.dxf"]:
            should_place = True
            
        if should_place:
            # Create 7-element tuple as bin_packing_with_existing would return
            placed_tuple = (polygon, 10.0, 20.0, 0.0, filename, color, order_id)
            placed.append(placed_tuple)
            logger.info(f"PLACED: {filename} from {order_id} -> 7-element tuple")
        else:
            remaining.append(poly)
            
    return placed, remaining

def simulate_polygon_removal(original_orders, placed_polygons):
    """Simulates the polygon removal logic as implemented"""
    
    logger.info(f"=== СИМУЛЯЦИЯ УДАЛЕНИЯ ПОЛИГОНОВ ===")
    
    # Group original orders by order_id
    remaining_orders = {}
    for poly in original_orders:
        order_id = poly[3]
        if order_id not in remaining_orders:
            remaining_orders[order_id] = []
        remaining_orders[order_id].append(poly)
    
    logger.info(f"Изначальные заказы:")
    for order_id, polys in remaining_orders.items():
        logger.info(f"  {order_id}: {[p[1] for p in polys]}")
    
    # Simulate the removal logic from layout_optimizer.py
    additional_orders_on_sheet = set()
    for placed_poly in placed_polygons:
        if len(placed_poly) > 6:
            order_id = str(placed_poly[6])
            additional_orders_on_sheet.add(order_id)
    
    logger.info(f"Заказы на листе: {additional_orders_on_sheet}")
    
    # Apply the removal logic
    for order_id in list(remaining_orders.keys()):
        if order_id in additional_orders_on_sheet:
            logger.info(f"\n--- ОБРАБОТКА ЗАКАЗА {order_id} ---")
            
            # Find polygons from this order that were placed
            placed_from_order = [p for p in placed_polygons if len(p) > 6 and str(p[6]) == str(order_id)]
            logger.info(f"Размещенных полигонов из заказа {order_id}: {len(placed_from_order)}")
            
            for placed_poly in placed_from_order:
                # Extract info from placed polygon (7-element tuple)
                placed_filename = str(placed_poly[4]) if len(placed_poly) > 4 else str(placed_poly[1])
                placed_color = str(placed_poly[5]) if len(placed_poly) > 5 else ""
                placed_order_id = str(placed_poly[6]) if len(placed_poly) > 6 else str(placed_poly[3])
                
                logger.info(f"  Ищем для удаления: {placed_filename} ({placed_color}) из {placed_order_id}")
                
                # Find matching original polygon
                removed = False
                original_count = len(remaining_orders[order_id])
                
                for orig_tuple in remaining_orders[order_id][:]:
                    # orig_tuple: 4-element (polygon, filename, color, order_id)
                    orig_filename = str(orig_tuple[1]) if len(orig_tuple) > 1 else ""
                    orig_color = str(orig_tuple[2]) if len(orig_tuple) > 2 else ""
                    orig_order_id = str(orig_tuple[3]) if len(orig_tuple) > 3 else ""
                    
                    logger.debug(f"    Сравниваем с: {orig_filename} ({orig_color}) из {orig_order_id}")
                    
                    # Check precise matching
                    filename_match = orig_filename == placed_filename
                    color_match = orig_color == placed_color
                    order_match = orig_order_id == placed_order_id
                    
                    logger.debug(f"      Файл: {filename_match}, Цвет: {color_match}, Заказ: {order_match}")
                    
                    if filename_match and color_match and order_match:
                        logger.info(f"    ✓ УДАЛЯЕМ: {orig_filename}")
                        remaining_orders[order_id].remove(orig_tuple)
                        removed = True
                        break
                
                if not removed:
                    logger.warning(f"    ❌ НЕ НАЙДЕН для удаления: {placed_filename}")
                else:
                    new_count = len(remaining_orders[order_id])
                    logger.info(f"    Полигонов в заказе: {original_count} -> {new_count}")
            
            # Remove empty orders
            if not remaining_orders[order_id]:
                logger.info(f"  Заказ {order_id} полностью размещен")
                del remaining_orders[order_id]
    
    logger.info(f"\nОставшиеся заказы после удаления:")
    for order_id, polys in remaining_orders.items():
        logger.info(f"  {order_id}: {[p[1] for p in polys]}")
    
    return remaining_orders

def main():
    print("=== ОТЛАДКА ЛОГИКИ УДАЛЕНИЯ ПОЛИГОНОВ ===")
    
    # Create problem polygons
    original_polygons = create_problem_polygons()
    
    print(f"Создано {len(original_polygons)} полигонов:")
    for poly in original_polygons:
        filename = poly[1]
        order_id = poly[3]
        print(f"  • {filename} -> {order_id}")
    
    # Simulate placement
    placed, remaining = simulate_bin_packing_result(original_polygons)
    
    print(f"\nРезультат размещения:")
    print(f"  • Размещено: {len(placed)}")
    print(f"  • Осталось: {len(remaining)}")
    
    print(f"\nРазмещенные полигоны (7-элементные кортежи):")
    for placed_poly in placed:
        filename = placed_poly[4]
        color = placed_poly[5] 
        order_id = placed_poly[6]
        print(f"  • {filename} ({color}) из {order_id}")
    
    # Simulate removal logic
    final_remaining = simulate_polygon_removal(original_polygons, placed)
    
    # Check for problems
    print(f"\n=== АНАЛИЗ ПРОБЛЕМ ===")
    
    suzuki_remaining = []
    admiral_remaining = []
    vw_remaining = []
    
    for order_id, polys in final_remaining.items():
        for poly in polys:
            filename = poly[1]
            if "SUZUKI XBEE" in filename:
                suzuki_remaining.append(filename)
            elif "ADMIRAL 335" in filename:
                admiral_remaining.append(filename)
            elif "VOLKSWAGEN TIGUAN 1" in filename:
                vw_remaining.append(filename)
    
    print(f"Оставшиеся SUZUKI XBEE: {suzuki_remaining}")
    print(f"Оставшиеся ADMIRAL 335: {admiral_remaining}")
    print(f"Оставшиеся VOLKSWAGEN TIGUAN 1: {vw_remaining}")
    
    # Check if the specific problem files are still there
    problems = []
    if "SUZUKI XBEE_5.dxf" not in suzuki_remaining:
        problems.append("SUZUKI XBEE_5.dxf был удален, но должен остаться")
    if "SUZUKI XBEE_3.dxf" not in suzuki_remaining:
        problems.append("SUZUKI XBEE_3.dxf был удален, но должен остаться")  
    if "SUZUKI XBEE_4.dxf" not in suzuki_remaining:
        problems.append("SUZUKI XBEE_4.dxf был удален, но должен остаться")
        
    if problems:
        print(f"\n❌ НАЙДЕННЫЕ ПРОБЛЕМЫ:")
        for problem in problems:
            print(f"  • {problem}")
        return False
    else:
        print(f"\n✅ Логика удаления работает корректно")
        return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)