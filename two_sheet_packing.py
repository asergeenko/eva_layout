"""
Специализированный алгоритм для принудительного размещения на ровно 2 листах.
Цель: достичь 78.1% использования материала на ≤2 листах.
"""

import logging
from typing import List, Tuple
# Import will be done locally to avoid circular imports
import random

logger = logging.getLogger(__name__)

def forced_two_sheet_packing(carpets, available_sheets, verbose: bool = True):
    """Принудительное размещение всех ковриков на ровно 2 листах."""
    
    if not carpets:
        return [], []
    
    # Используем только первый тип листов
    sheet_type = available_sheets[0]
    sheet_size = (sheet_type["width"], sheet_type["height"])
    
    if verbose:
        logger.info(f"🎯 Принудительное размещение {len(carpets)} ковриков на 2 листах {sheet_size}")
    
    # Стратегия 1: Пытаемся разделить ковры пополам по площади
    carpets_sorted = sorted(carpets, key=lambda c: c.polygon.area, reverse=True)
    total_area = sum(c.polygon.area for c in carpets_sorted)
    target_area_per_sheet = total_area / 2
    
    # Разделяем ковры на две примерно равные группы по площади
    group1, group2 = [], []
    group1_area, group2_area = 0, 0
    
    for carpet in carpets_sorted:
        if group1_area <= group2_area:
            group1.append(carpet)
            group1_area += carpet.polygon.area
        else:
            group2.append(carpet)
            group2_area += carpet.polygon.area
    
    if verbose:
        logger.info(f"Группа 1: {len(group1)} ковриков, {group1_area/100:.0f} см²")
        logger.info(f"Группа 2: {len(group2)} ковриков, {group2_area/100:.0f} см²")
    
    # Пытаемся разместить каждую группу на своем листе
    placed_layouts = []
    all_unplaced = []
    
    for group_id, group in enumerate([group1, group2], 1):
        placed, unplaced = bin_packing(group, sheet_size, verbose=False)
        
        if placed:
            layout = {
                "sheet_number": group_id,
                "sheet_type": sheet_type["name"],
                "sheet_color": sheet_type.get("color", "чёрный"),
                "sheet_size": sheet_size,
                "placed_polygons": placed,
                "usage_percent": calculate_usage_percent(placed, sheet_size),
                "orders_on_sheet": list(set(c.order_id for c in group if c not in unplaced))
            }
            placed_layouts.append(layout)
            
            if verbose:
                logger.info(f"Лист {group_id}: {len(placed)} ковриков, {layout['usage_percent']:.1f}% заполнение")
        
        # Если есть неразмещенные в этой группе, попробуем запихнуть на другой лист
        if unplaced:
            if verbose:
                logger.warning(f"Группа {group_id}: {len(unplaced)} неразмещенных, пытаемся на другом листе")
            
            # Находим лист с наименьшим заполнением для дозаполнения
            if placed_layouts:
                best_layout_idx = min(range(len(placed_layouts)), 
                                    key=lambda i: placed_layouts[i]['usage_percent'])
                best_layout = placed_layouts[best_layout_idx]
                
                try:
                    from layout_optimizer import bin_packing_with_existing
                    additional_placed, remaining = bin_packing_with_existing(
                        unplaced, 
                        best_layout['placed_polygons'],
                        best_layout['sheet_size'],
                        verbose=False
                    )
                    
                    if additional_placed:
                        best_layout['placed_polygons'].extend(additional_placed)
                        best_layout['usage_percent'] = calculate_usage_percent(
                            best_layout['placed_polygons'], best_layout['sheet_size']
                        )
                        if verbose:
                            logger.info(f"Дозаполнен лист {best_layout['sheet_number']}: +{len(additional_placed)}")
                        
                        # Обновляем unplaced
                        placed_set = set()
                        for placed_tuple in additional_placed:
                            for carpet in unplaced:
                                if (carpet.polygon, carpet.filename) == (placed_tuple[0], placed_tuple[4]):
                                    placed_set.add(carpet)
                        unplaced = [c for c in unplaced if c not in placed_set]
                        
                except ImportError:
                    pass
            
            all_unplaced.extend(unplaced)
    
    if verbose:
        total_placed = sum(len(layout['placed_polygons']) for layout in placed_layouts)
        total_usage = sum(layout['usage_percent'] for layout in placed_layouts) / len(placed_layouts) if placed_layouts else 0
        logger.info(f"ИТОГО: {len(placed_layouts)} листов, {total_placed} ковриков, {total_usage:.1f}% среднее заполнение")
    
    return placed_layouts, all_unplaced


def iterative_two_sheet_optimization(carpets, available_sheets, verbose: bool = True):
    """Итеративная оптимизация для достижения цели на 2 листах."""
    
    best_layouts = None
    best_unplaced = carpets[:]
    best_usage = 0
    max_attempts = 10
    
    if verbose:
        logger.info(f"🔄 Итеративная оптимизация, {max_attempts} попыток")
    
    for attempt in range(max_attempts):
        # Случайное перемешивание для разных стратегий разбиения
        carpets_shuffled = carpets[:]
        random.seed(42 + attempt)  # Воспроизводимость
        random.shuffle(carpets_shuffled)
        
        layouts, unplaced = forced_two_sheet_packing(carpets_shuffled, available_sheets, verbose=False)
        
        if layouts:
            total_usage = sum(layout['usage_percent'] for layout in layouts) / len(layouts)
            placed_count = sum(len(layout['placed_polygons']) for layout in layouts)
            
            # Критерии лучшего результата: меньше неразмещенных, выше использование
            is_better = (
                len(unplaced) < len(best_unplaced) or
                (len(unplaced) == len(best_unplaced) and total_usage > best_usage)
            )
            
            if is_better:
                best_layouts = layouts
                best_unplaced = unplaced
                best_usage = total_usage
                
                if verbose:
                    logger.info(f"Попытка {attempt+1}: {placed_count} размещено, {len(unplaced)} неразмещено, {total_usage:.1f}% использование")
                    
                # Если все размещены и достигнута высокая плотность - останавливаемся
                if len(unplaced) == 0 and total_usage > 75:
                    break
    
    if verbose and best_layouts:
        total_placed = sum(len(layout['placed_polygons']) for layout in best_layouts)
        logger.info(f"🏆 ЛУЧШИЙ РЕЗУЛЬТАТ: {total_placed} размещено, {len(best_unplaced)} неразмещено, {best_usage:.1f}% использование")
    
    return best_layouts or [], best_unplaced