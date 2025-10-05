"""
Оптимизатор для перестановки ковров на листе с целью минимизации запертого пространства.
"""

from layout_optimizer import PlacedCarpet, check_collision, translate_polygon
from shapely.geometry import Polygon


def try_relocate_carpet(
    carpet_index: int,
    placed_carpets: list[PlacedCarpet],
    sheet_width_mm: float,
    sheet_height_mm: float
) -> tuple[PlacedCarpet | None, float]:
    """
    Пробует переместить один ковер в лучшую позицию.
    Возвращает (новый_ковер, улучшение_в_max_height) или (None, 0) если улучшения нет.
    """
    if carpet_index >= len(placed_carpets):
        return None, 0

    carpet = placed_carpets[carpet_index]
    obstacles = [c.polygon for i, c in enumerate(placed_carpets) if i != carpet_index]

    # Текущая максимальная высота
    current_max_height = max(c.polygon.bounds[3] for c in placed_carpets)

    # Пробуем разные позиции
    bounds = carpet.polygon.bounds
    carpet_width = bounds[2] - bounds[0]
    carpet_height = bounds[3] - bounds[1]

    best_improvement = 0
    best_carpet = None

    # Пробуем сетку позиций с шагом 20мм
    for test_x in range(0, int(sheet_width_mm - carpet_width), 20):
        for test_y in range(0, int(sheet_height_mm - carpet_height), 20):
            # Создаем тестовый полигон
            x_shift = test_x - bounds[0]
            y_shift = test_y - bounds[1]
            test_polygon = translate_polygon(carpet.polygon, x_shift, y_shift)

            # Проверяем границы
            test_bounds = test_polygon.bounds
            if (test_bounds[0] < 0 or test_bounds[1] < 0 or
                test_bounds[2] > sheet_width_mm or test_bounds[3] > sheet_height_mm):
                continue

            # Проверяем коллизии
            has_collision = False
            for obstacle in obstacles:
                if check_collision(test_polygon, obstacle, min_gap=2.0):
                    has_collision = True
                    break

            if has_collision:
                continue

            # Вычисляем новую максимальную высоту
            new_max_height = max(
                max(c.polygon.bounds[3] for i, c in enumerate(placed_carpets) if i != carpet_index),
                test_bounds[3]
            )

            # Если это улучшает максимальную высоту
            improvement = current_max_height - new_max_height
            if improvement > best_improvement:
                best_improvement = improvement
                best_carpet = PlacedCarpet(
                    polygon=test_polygon,
                    x_offset=carpet.x_offset + x_shift,
                    y_offset=carpet.y_offset + y_shift,
                    angle=carpet.angle,
                    filename=carpet.filename,
                    color=carpet.color,
                    order_id=carpet.order_id,
                    carpet_id=carpet.carpet_id,
                    priority=carpet.priority,
                )

    return best_carpet, best_improvement


def apply_relocation_optimization(
    placed_carpets: list[PlacedCarpet],
    sheet_width_mm: float,
    sheet_height_mm: float,
    max_iterations: int = 3
) -> list[PlacedCarpet]:
    """
    Пробует переставлять ковры для улучшения упаковки.
    """
    if not placed_carpets or len(placed_carpets) < 2:
        return placed_carpets

    optimized = placed_carpets[:]

    for iteration in range(max_iterations):
        any_improvement = False

        # Сортируем ковры по высоте (верхние сначала - их переставлять эффективнее)
        carpet_indices = sorted(
            range(len(optimized)),
            key=lambda i: optimized[i].polygon.bounds[3],
            reverse=True
        )

        # Пробуем переставить первые 3 ковра
        for idx in carpet_indices[:3]:
            new_carpet, improvement = try_relocate_carpet(
                idx, optimized, sheet_width_mm, sheet_height_mm
            )

            if new_carpet and improvement > 5:  # Минимум 5мм улучшения
                optimized[idx] = new_carpet
                any_improvement = True

        if not any_improvement:
            break

    return optimized
