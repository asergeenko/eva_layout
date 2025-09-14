"""Helper functions for EVA mat nesting optimization."""

# Version for cache busting
__version__ = "1.5.0"

import numpy as np

from shapely.geometry import Polygon
from shapely import affinity
import streamlit as st
import logging

from carpet import Carpet, PlacedCarpet, UnplacedCarpet, PlacedSheet

# Настройка логирования
logger = logging.getLogger(__name__)


logging.getLogger("ezdxf").setLevel(logging.ERROR)

__all__ = [
    "rotate_polygon",
    "translate_polygon",
    "place_polygon_at_origin",
    "check_collision",
    "bin_packing_with_inventory",
    "calculate_usage_percent",
    "bin_packing",
]


def apply_tetris_gravity(placed_carpets: list[PlacedCarpet], sheet_width_mm: float, sheet_height_mm: float) -> list[PlacedCarpet]:
    """
    ИСПРАВЛЕННЫЙ ТЕТРИС-ДВИЖОК: Применяет гравитацию осторожно, не ломая существующее размещение.
    Ковры падают вниз только если это безопасно и улучшает размещение.
    """
    if not placed_carpets or len(placed_carpets) < 2:
        return placed_carpets

    # Создаем копии для безопасности
    gravity_carpets = []
    for carpet in placed_carpets:
        gravity_carpets.append(PlacedCarpet(
            polygon=carpet.polygon,
            x_offset=carpet.x_offset,
            y_offset=carpet.y_offset,
            angle=carpet.angle,
            filename=carpet.filename,
            color=carpet.color,
            order_id=carpet.order_id,
            carpet_id=carpet.carpet_id,
            priority=carpet.priority
        ))

    # Сортируем по высоте (сверху вниз) - верхние ковры пытаемся опустить
    gravity_carpets.sort(key=lambda c: c.polygon.bounds[3], reverse=True)  # По верхнему краю

    movements_made = 0
    max_movements = len(gravity_carpets) // 2  # Ограничиваем количество движений

    # Применяем гравитацию осторожно к верхним коврам
    for i, carpet in enumerate(gravity_carpets):
        if movements_made >= max_movements:
            break

        # Препятствия = все остальные ковры (не обновляем в процессе)
        obstacles = [other.polygon for j, other in enumerate(gravity_carpets) if j != i]

        # Текущие границы ковра
        current_bounds = carpet.polygon.bounds
        current_y = current_bounds[1]

        # КОНСЕРВАТИВНАЯ ГРАВИТАЦИЯ: пробуем только небольшие улучшения
        best_y = current_y
        improvement_found = False

        # Пробуем опуститься максимум на 50мм за раз
        max_drop = min(50, current_y)  # Не больше 5см и не ниже 0

        for drop_distance in [5, 10, 15, 20, 25, 30, 40, 50]:
            if drop_distance > max_drop:
                break

            test_y = current_y - drop_distance
            if test_y < 0:
                continue

            # Создаем тестовую позицию
            y_offset_change = test_y - current_bounds[1]
            test_polygon = translate_polygon(carpet.polygon, 0, y_offset_change)

            # Проверяем границы листа
            test_bounds = test_polygon.bounds
            if test_bounds[1] < -1 or test_bounds[3] > sheet_height_mm + 1:
                continue

            # Проверяем коллизии с другими коврами
            collision = False
            for obstacle in obstacles:
                if test_polygon.intersects(obstacle):
                    intersection = test_polygon.intersection(obstacle)
                    if intersection.area > 50:  # Более консервативный порог
                        collision = True
                        break

            if not collision:
                best_y = test_y
                improvement_found = True
            else:
                break  # Встретили коллизию, дальше не пробуем

        # Применяем улучшение если найдено
        if improvement_found and best_y < current_y - 3:  # Минимум 3мм улучшения
            y_offset_change = best_y - current_bounds[1]
            carpet.polygon = translate_polygon(carpet.polygon, 0, y_offset_change)
            carpet.y_offset += y_offset_change
            movements_made += 1

    return gravity_carpets


def apply_tetris_right_compaction(placed_carpets: list[PlacedCarpet], sheet_width_mm: float, sheet_height_mm: float) -> list[PlacedCarpet]:
    """
    НОВАЯ TETRIS-ФУНКЦИЯ: Сжимает ковры к правому краю для освобождения пространства.
    Это позволяет верхним коврам упасть вниз, как в настоящем Тетрисе.
    """
    if not placed_carpets or len(placed_carpets) < 2:
        return placed_carpets

    # Создаем копии для безопасности
    compacted_carpets = []
    for carpet in placed_carpets:
        compacted_carpets.append(PlacedCarpet(
            polygon=carpet.polygon,
            x_offset=carpet.x_offset,
            y_offset=carpet.y_offset,
            angle=carpet.angle,
            filename=carpet.filename,
            color=carpet.color,
            order_id=carpet.order_id,
            carpet_id=carpet.carpet_id,
            priority=carpet.priority
        ))

    # Сортируем по расстоянию от правого края (дальние сначала)
    compacted_carpets.sort(key=lambda c: sheet_width_mm - c.polygon.bounds[2], reverse=True)

    movements_made = 0
    max_movements = min(5, len(compacted_carpets))  # Ограничиваем количество движений

    # Применяем сжатие к правому краю
    for i, carpet in enumerate(compacted_carpets):
        if movements_made >= max_movements:
            break

        # Препятствия = все остальные ковры
        obstacles = [other.polygon for j, other in enumerate(compacted_carpets) if j != i]

        # Текущие границы ковра
        current_bounds = carpet.polygon.bounds
        current_right = current_bounds[2]
        carpet_width = current_bounds[2] - current_bounds[0]
        carpet_height = current_bounds[3] - current_bounds[1]

        # Максимально возможный сдвиг вправо
        max_right_x = sheet_width_mm - carpet_width
        current_left = current_bounds[0]

        if current_right >= sheet_width_mm - 10:  # Уже у правого края
            continue

        # Пробуем сдвинуть вправо
        best_x = current_left
        improvement_found = False

        # Шагаем вправо с шагом 5мм
        for test_right_x in range(int(current_right) + 5, int(sheet_width_mm), 5):
            test_left_x = test_right_x - carpet_width

            if test_left_x < 0 or test_right_x > sheet_width_mm:
                break

            # Создаем тестовый полигон
            x_shift = test_left_x - current_bounds[0]
            y_shift = 0  # Не двигаем по Y
            test_polygon = translate_polygon(carpet.polygon, x_shift, y_shift)

            # Проверяем границы листа
            test_bounds = test_polygon.bounds
            if (test_bounds[0] < 0 or test_bounds[1] < 0 or
                test_bounds[2] > sheet_width_mm or test_bounds[3] > sheet_height_mm):
                break

            # Проверяем коллизии
            collision = False
            for obstacle in obstacles:
                if check_collision(test_polygon, obstacle, min_gap=2.0):
                    collision = True
                    break

            if not collision:
                best_x = test_left_x
                improvement_found = True
            else:
                break  # Натолкнулись на препятствие, дальше не двигаемся

        # Применяем улучшение
        if improvement_found and best_x > current_left + 3:  # Минимум 3мм улучшения
            x_shift = best_x - current_bounds[0]
            new_polygon = translate_polygon(carpet.polygon, x_shift, 0)

            # Обновляем ковер
            compacted_carpets[i] = PlacedCarpet(
                polygon=new_polygon,
                x_offset=carpet.x_offset + x_shift,
                y_offset=carpet.y_offset,
                angle=carpet.angle,
                filename=carpet.filename,
                color=carpet.color,
                order_id=carpet.order_id,
                carpet_id=carpet.carpet_id,
                priority=carpet.priority
            )
            movements_made += 1

    return compacted_carpets


def calculate_trapped_space(placed_carpets: list[PlacedCarpet], sheet_width_mm: float, sheet_height_mm: float) -> float:
    """
    🔍 АНАЛИЗ ЗАПЕРНЫХ ЗОН: Вычисляет площадь пространства, заперного коврами.
    Заперное пространство = недоступно для будущих ковров из-за размещения текущих.
    """
    if not placed_carpets:
        return 0

    from shapely.geometry import box
    from shapely.ops import unary_union

    # Создаем прямоугольник листа
    sheet_box = box(0, 0, sheet_width_mm, sheet_height_mm)

    # Объединяем все размещенные ковры
    placed_union = unary_union([carpet.polygon for carpet in placed_carpets])

    # Находим свободное пространство
    free_space = sheet_box.difference(placed_union)

    # Анализируем связность свободных областей
    if hasattr(free_space, 'geoms'):  # MultiPolygon
        free_polygons = list(free_space.geoms)
    else:  # Single Polygon
        free_polygons = [free_space] if free_space.area > 0 else []

    # Вычисляем "заперность" каждой свободной области
    trapped_area = 0
    min_useful_area = 200 * 200  # 20x20см - минимальный полезный размер

    for poly in free_polygons:
        if poly.area < min_useful_area:
            continue  # Слишком маленькие не считаем

        bounds = poly.bounds
        width = bounds[2] - bounds[0]
        height = bounds[3] - bounds[1]

        # Область считается "заперной" если она:
        # 1. Окружена коврами с нескольких сторон
        # 2. Имеет неправильную форму (низкий коэффициент прямоугольности)
        rectangularity = poly.area / (width * height)

        if rectangularity < 0.7:  # Менее 70% прямоугольности (более строгий критерий)
            trapped_area += poly.area * (1.2 - rectangularity)  # Увеличенный штраф за неправильность

        # Дополнительный штраф за области далеко от краев листа
        center_x = (bounds[0] + bounds[2]) / 2
        center_y = (bounds[1] + bounds[3]) / 2

        distance_from_edges = min(
            center_x,  # От левого края
            sheet_width_mm - center_x,  # От правого края
            center_y,  # От нижнего края
            sheet_height_mm - center_y  # От верхнего края
        )

        if distance_from_edges > 200:  # Больше 20см от краев
            isolation_penalty = (distance_from_edges - 200) / 100
            trapped_area += poly.area * isolation_penalty * 0.1

    return trapped_area


def analyze_placement_blocking(placed_carpets: list[PlacedCarpet], sheet_width_mm: float, sheet_height_mm: float) -> dict:
    """
    🧠 АНАЛИЗ БЛОКИРОВКИ: Анализирует как размещенные ковры блокируют пространство для будущих ковров.
    Возвращает рекомендации по улучшению размещения.
    """
    analysis = {
        'total_trapped_area': 0,
        'blocking_carpets': [],  # Ковры, создающие много блокировки
        'improvement_suggestions': []
    }

    if len(placed_carpets) < 2:
        return analysis

    # Базовая заперность
    base_trapped = calculate_trapped_space(placed_carpets, sheet_width_mm, sheet_height_mm)
    analysis['total_trapped_area'] = base_trapped

    # Анализируем вклад каждого ковра в блокировку
    for i, carpet in enumerate(placed_carpets):
        # Убираем этот ковер и смотрим, как изменится заперность
        temp_placed = [c for j, c in enumerate(placed_carpets) if j != i]
        trapped_without = calculate_trapped_space(temp_placed, sheet_width_mm, sheet_height_mm)

        blocking_contribution = base_trapped - trapped_without

        if blocking_contribution > 3000:  # Больше 300 см² блокировки (более агрессивный порог)
            analysis['blocking_carpets'].append({
                'carpet': carpet,
                'blocking_amount': blocking_contribution,
                'carpet_index': i
            })

            # Предлагаем попробовать поворот
            analysis['improvement_suggestions'].append({
                'type': 'rotation',
                'carpet_index': i,
                'reason': f'Блокирует {blocking_contribution/100:.0f} см² пространства'
            })

    return analysis


def post_placement_optimize_aggressive(placed_carpets: list[PlacedCarpet], sheet_width_mm: float, sheet_height_mm: float, remaining_carpets: list[Carpet] = None) -> list[PlacedCarpet]:
    """
    🚀 АГРЕССИВНАЯ POST-PLACEMENT OPTIMIZATION: Полностью переразмещает проблемные ковры.
    Не просто поворачивает на месте, а находит НОВЫЕ позиции с учетом будущих ковров.
    """
    if len(placed_carpets) < 2:
        return placed_carpets

    # Анализируем проблемы
    blocking_analysis = analyze_placement_blocking(placed_carpets, sheet_width_mm, sheet_height_mm)

    if not blocking_analysis['blocking_carpets']:
        return placed_carpets

    # Сортируем по степени блокировки (худшие первые)
    blocking_carpets = sorted(
        blocking_analysis['blocking_carpets'],
        key=lambda x: x['blocking_amount'],
        reverse=True
    )

    optimized_carpets = [
        PlacedCarpet(
            polygon=c.polygon,
            x_offset=c.x_offset,
            y_offset=c.y_offset,
            angle=c.angle,
            filename=c.filename,
            color=c.color,
            order_id=c.order_id,
            carpet_id=c.carpet_id,
            priority=c.priority
        ) for c in placed_carpets
    ]

    improvements_made = 0
    max_improvements = 2  # Агрессивно переразмещаем максимум 2 худших ковра

    for blocker_info in blocking_carpets[:max_improvements]:
        carpet_idx = blocker_info['carpet_index']
        current_carpet = optimized_carpets[carpet_idx]

        print(f"🔄 Переразмещаем {current_carpet.filename} (блокирует {blocker_info['blocking_amount']/100:.0f} см²)")

        # Создаем исходный полигон ковра (без поворотов)
        original_bounds = current_carpet.polygon.bounds

        # Восстанавливаем исходную форму ковра
        original_polygon = rotate_polygon(current_carpet.polygon, -current_carpet.angle)

        # Получаем все остальные ковры как препятствия
        obstacles = [c.polygon for i, c in enumerate(optimized_carpets) if i != carpet_idx]

        current_trapped = calculate_trapped_space(optimized_carpets, sheet_width_mm, sheet_height_mm)
        best_improvement = 0
        best_placement = None

        # АГРЕССИВНАЯ СТРАТЕГИЯ: Пробуем ВСЕ ориентации + ВСЕ позиции
        for test_angle in [0, 90, 180, 270]:
            rotated_polygon = rotate_polygon(original_polygon, test_angle) if test_angle != 0 else original_polygon
            rot_bounds = rotated_polygon.bounds
            rot_width = rot_bounds[2] - rot_bounds[0]
            rot_height = rot_bounds[3] - rot_bounds[1]

            # Проверяем границы листа
            if rot_width > sheet_width_mm or rot_height > sheet_height_mm:
                continue

            # Пробуем МНОЖЕСТВО позиций, не только bottom-left
            test_positions = []

            # Bottom-left позиции
            from layout_optimizer import find_bottom_left_position_with_obstacles
            best_x, best_y = find_bottom_left_position_with_obstacles(
                rotated_polygon, obstacles, sheet_width_mm, sheet_height_mm
            )
            if best_x is not None:
                test_positions.append((best_x, best_y))

            # Дополнительные стратегические позиции
            step_x, step_y = max(50, rot_width // 4), max(50, rot_height // 4)

            for test_x in range(0, int(sheet_width_mm - rot_width), int(step_x)):
                for test_y in range(0, int(sheet_height_mm - rot_height), int(step_y)):
                    test_positions.append((test_x, test_y))
                    if len(test_positions) > 20:  # Ограничиваем количество тестов
                        break
                if len(test_positions) > 20:
                    break

            # Тестируем каждую позицию
            for test_x, test_y in test_positions:
                # Создаем тестовый полигон
                test_polygon = translate_polygon(
                    rotated_polygon,
                    test_x - rot_bounds[0],
                    test_y - rot_bounds[1]
                )

                # Проверяем коллизии
                collision = False
                for obstacle in obstacles:
                    if test_polygon.intersects(obstacle):
                        intersection = test_polygon.intersection(obstacle)
                        if intersection.area > 100:
                            collision = True
                            break

                if not collision:
                    # Тестируем заперность с новым размещением
                    test_carpets = optimized_carpets.copy()
                    test_carpets[carpet_idx] = PlacedCarpet(
                        polygon=test_polygon,
                        x_offset=test_x - rot_bounds[0],
                        y_offset=test_y - rot_bounds[1],
                        angle=test_angle,
                        filename=current_carpet.filename,
                        color=current_carpet.color,
                        order_id=current_carpet.order_id,
                        carpet_id=current_carpet.carpet_id,
                        priority=current_carpet.priority
                    )

                    test_trapped = calculate_trapped_space(test_carpets, sheet_width_mm, sheet_height_mm)
                    improvement = current_trapped - test_trapped

                    if improvement > best_improvement:
                        best_improvement = improvement
                        best_placement = {
                            'polygon': test_polygon,
                            'x_offset': test_x - rot_bounds[0],
                            'y_offset': test_y - rot_bounds[1],
                            'angle': test_angle
                        }

        # Применяем лучшее размещение если оно значимо лучше
        if best_placement and best_improvement > 500:  # Минимум 50 см² улучшения
            print(f"✅ Найдено лучшее размещение: освобождает {best_improvement/100:.0f} см²")

            optimized_carpets[carpet_idx] = PlacedCarpet(
                polygon=best_placement['polygon'],
                x_offset=best_placement['x_offset'],
                y_offset=best_placement['y_offset'],
                angle=best_placement['angle'],
                filename=current_carpet.filename,
                color=current_carpet.color,
                order_id=current_carpet.order_id,
                carpet_id=current_carpet.carpet_id,
                priority=current_carpet.priority
            )
            improvements_made += 1
        else:
            print(f"❌ Лучшее размещение не найдено (улучшение: {best_improvement/100:.0f} см²)")

    if improvements_made > 0:
        print(f"🎊 Агрессивная оптимизация улучшила {improvements_made} ковров!")

    return optimized_carpets


def post_placement_optimize(placed_carpets: list[PlacedCarpet], sheet_width_mm: float, sheet_height_mm: float) -> list[PlacedCarpet]:
    """
    🚀 POST-PLACEMENT OPTIMIZATION: Революционная система переразмещения.
    После размещения анализирует и улучшает позиции ковров для минимизации заперных зон.
    """
    if len(placed_carpets) < 2:
        return placed_carpets

    # Анализируем текущую блокировку
    blocking_analysis = analyze_placement_blocking(placed_carpets, sheet_width_mm, sheet_height_mm)

    if not blocking_analysis['blocking_carpets']:
        return placed_carpets  # Нет проблемных ковров

    optimized_carpets = [
        PlacedCarpet(
            polygon=c.polygon,
            x_offset=c.x_offset,
            y_offset=c.y_offset,
            angle=c.angle,
            filename=c.filename,
            color=c.color,
            order_id=c.order_id,
            carpet_id=c.carpet_id,
            priority=c.priority
        ) for c in placed_carpets
    ]

    improvements_made = 0
    max_improvements = min(5, len(blocking_analysis['blocking_carpets']))  # Увеличили лимит улучшений

    # Оптимизируем самые проблемные ковры
    for suggestion in blocking_analysis['improvement_suggestions'][:max_improvements]:
        if suggestion['type'] == 'rotation':
            carpet_idx = suggestion['carpet_index']
            current_carpet = optimized_carpets[carpet_idx]

            # Пробуем все возможные повороты
            current_trapped = calculate_trapped_space(optimized_carpets, sheet_width_mm, sheet_height_mm)
            best_improvement = 0
            best_rotation = None

            for test_angle in [0, 90, 180, 270]:
                if test_angle == current_carpet.angle:
                    continue

                # Создаем тестовый ковер с новым углом
                original_polygon = rotate_polygon(current_carpet.polygon, -current_carpet.angle)  # Возвращаем к 0°
                rotated_polygon = rotate_polygon(original_polygon, test_angle)

                # Пробуем разместить в той же позиции
                bounds = rotated_polygon.bounds
                rotated_width = bounds[2] - bounds[0]
                rotated_height = bounds[3] - bounds[1]

                # Проверяем, помещается ли в лист
                if rotated_width > sheet_width_mm or rotated_height > sheet_height_mm:
                    continue

                # Создаем тестовое размещение
                test_x, test_y = current_carpet.polygon.bounds[0], current_carpet.polygon.bounds[1]
                test_polygon = translate_polygon(rotated_polygon, test_x - bounds[0], test_y - bounds[1])

                # Проверяем коллизии с другими коврами
                collision = False
                for j, other_carpet in enumerate(optimized_carpets):
                    if j == carpet_idx:
                        continue
                    if test_polygon.intersects(other_carpet.polygon):
                        intersection = test_polygon.intersection(other_carpet.polygon)
                        if intersection.area > 100:
                            collision = True
                            break

                if not collision:
                    # Тестируем заперность с новым поворотом
                    test_carpets = optimized_carpets.copy()
                    test_carpets[carpet_idx] = PlacedCarpet(
                        polygon=test_polygon,
                        x_offset=current_carpet.x_offset,
                        y_offset=current_carpet.y_offset,
                        angle=test_angle,
                        filename=current_carpet.filename,
                        color=current_carpet.color,
                        order_id=current_carpet.order_id,
                        carpet_id=current_carpet.carpet_id,
                        priority=current_carpet.priority
                    )

                    test_trapped = calculate_trapped_space(test_carpets, sheet_width_mm, sheet_height_mm)
                    improvement = current_trapped - test_trapped

                    if improvement > best_improvement and improvement > 1000:  # Минимум 100 см² улучшения (более чувствительный)
                        best_improvement = improvement
                        best_rotation = (test_angle, test_polygon)

            # Применяем лучший поворот
            if best_rotation:
                optimized_carpets[carpet_idx] = PlacedCarpet(
                    polygon=best_rotation[1],
                    x_offset=current_carpet.x_offset,
                    y_offset=current_carpet.y_offset,
                    angle=best_rotation[0],
                    filename=current_carpet.filename,
                    color=current_carpet.color,
                    order_id=current_carpet.order_id,
                    carpet_id=current_carpet.carpet_id,
                    priority=current_carpet.priority
                )
                improvements_made += 1

    return optimized_carpets


def calculate_free_top_space(placed_carpets: list[PlacedCarpet], sheet_width_mm: float, sheet_height_mm: float) -> float:
    """
    Вычисляет площадь свободного пространства сверху (идеально для следующих ковров).
    Это ключевая метрика для Тетрис-оптимизации.
    """
    if not placed_carpets:
        return sheet_width_mm * sheet_height_mm

    # Находим максимальную высоту занятого пространства
    max_occupied_y = max(carpet.polygon.bounds[3] for carpet in placed_carpets)

    # Свободное пространство сверху
    free_height = sheet_height_mm - max_occupied_y
    if free_height <= 0:
        return 0

    return sheet_width_mm * free_height


def find_available_sheet_of_color(color, sheet_inventory):
    """Find an available sheet of the specified color."""
    for sheet_type in sheet_inventory:
        if (
            sheet_type.get("color", "серый") == color
            and sheet_type["count"] - sheet_type["used"] > 0
        ):
            return sheet_type
    return None


def create_new_sheet(sheet_type, sheet_number, color) -> PlacedSheet:
    """Create a new sheet layout."""
    sheet_size = (sheet_type["width"], sheet_type["height"])
    return PlacedSheet(
        sheet_number=sheet_number,
        sheet_type=sheet_type["name"],
        sheet_color=color,
        sheet_size=sheet_size,
        placed_polygons=[],
        usage_percent=0.0,
        orders_on_sheet=[],
    )


def rotate_polygon(polygon: Polygon, angle: float) -> Polygon:
    """Rotate a polygon by a given angle (in degrees) around its centroid.

    Using centroid rotation for better stability and predictable results.
    """
    if angle == 0:
        return polygon

    # Use centroid as rotation origin for better stability
    centroid = polygon.centroid
    rotation_origin = (centroid.x, centroid.y)

    # Rotate around centroid instead of corner to avoid positioning issues
    rotated = affinity.rotate(polygon, angle, origin=rotation_origin)

    # Ensure the rotated polygon is valid
    if not rotated.is_valid:
        try:
            # Try to fix invalid geometry
            rotated = rotated.buffer(0)
        except Exception:
            # If fixing fails, return original polygon
            return polygon

    return rotated


def translate_polygon(polygon: Polygon, x: float, y: float) -> Polygon:
    """Translate a polygon to a new position."""
    return affinity.translate(polygon, xoff=x, yoff=y)


def place_polygon_at_origin(polygon: Polygon) -> Polygon:
    """Move polygon so its bottom-left corner is at (0,0)."""
    bounds = polygon.bounds
    return translate_polygon(polygon, -bounds[0], -bounds[1])


def apply_placement_transform(
    polygon: Polygon, x_offset: float, y_offset: float, rotation_angle: float
) -> Polygon:
    """Apply the same transformation sequence used in bin_packing.

    This ensures consistency between visualization and DXF output.

    Args:
        polygon: Original polygon
        x_offset: X translation offset
        y_offset: Y translation offset
        rotation_angle: Rotation angle in degrees

    Returns:
        Transformed polygon
    """
    # Step 1: Move to origin
    bounds = polygon.bounds
    normalized = translate_polygon(polygon, -bounds[0], -bounds[1])

    # Step 2: Rotate around centroid if needed
    if rotation_angle != 0:
        rotated = rotate_polygon(normalized, rotation_angle)
    else:
        rotated = normalized

    # Step 3: Apply final translation
    # Note: x_offset and y_offset already account for the original bounds
    final_polygon = translate_polygon(
        rotated, x_offset + bounds[0], y_offset + bounds[1]
    )

    return final_polygon


def check_collision_fast(
    polygon1: Polygon, polygon2: Polygon, min_gap: float = 0.1
) -> bool:
    """FIXED fast collision check - PRIORITY: Accuracy over speed."""
    # Fast validity check
    if not (polygon1.is_valid and polygon2.is_valid):
        return True

    try:
        # CRITICAL FIX: Always check intersection first - this catches overlapping polygons
        if polygon1.intersects(polygon2):
            return True

        # SPEED OPTIMIZATION: Only use bbox pre-filter for distant objects
        bounds1 = polygon1.bounds
        bounds2 = polygon2.bounds

        # Calculate minimum possible distance between bounding boxes
        dx = max(0, max(bounds1[0] - bounds2[2], bounds2[0] - bounds1[2]))
        dy = max(0, max(bounds1[1] - bounds2[3], bounds2[1] - bounds1[3]))
        bbox_min_distance = (dx * dx + dy * dy) ** 0.5

        # SAFE EARLY EXIT: Only skip geometric check if bounding boxes are clearly far apart
        if bbox_min_distance > min_gap + 50:  # Conservative 50mm safety margin
            return False

        # ALWAYS do accurate geometric distance check for close/potentially colliding objects
        geometric_distance = polygon1.distance(polygon2)
        return geometric_distance < min_gap

    except Exception:
        # Be conservative on errors
        return True


def check_collision(polygon1: Polygon, polygon2: Polygon, min_gap: float = 0.1) -> bool:
    """Check if two polygons collide using TRUE GEOMETRIC distance with speed optimization."""
    return check_collision_fast(polygon1, polygon2, min_gap)


# @profile
def bin_packing_with_existing(
    polygons: list[Carpet],
    existing_placed: list[PlacedCarpet],
    sheet_size: tuple[float, float],
    verbose: bool = True,
    tighten=True,
) -> tuple[list[PlacedCarpet], list[UnplacedCarpet]]:
    """Bin packing that considers already placed polygons on the sheet."""
    # Convert sheet size from cm to mm to match DXF polygon units
    sheet_width_mm, sheet_height_mm = sheet_size[0] * 10, sheet_size[1] * 10

    placed = []
    unplaced = []

    # Start with existing placed polygons as obstacles
    obstacles = [placed_tuple.polygon for placed_tuple in existing_placed]

    if verbose:
        st.info(
            f"Дозаполняем лист с {len(obstacles)} существующими деталями, добавляем {len(polygons)} новых"
        )

    # IMPROVEMENT 1: Sort polygons by area and perimeter for better packing
    def get_polygon_priority(polygon_tuple: Carpet):
        polygon = polygon_tuple.polygon
        # Combine area and perimeter for better sorting (larger, more complex shapes first)
        area = polygon.area
        bounds = polygon.bounds
        perimeter_approx = 2 * ((bounds[2] - bounds[0]) + (bounds[3] - bounds[1]))
        return area + perimeter_approx * 0.1

    sorted_polygons = sorted(polygons, key=get_polygon_priority, reverse=True)

    for i, carpet in enumerate(sorted_polygons):
        # ПРОФИЛИРОВАНИЕ: Измеряем время обработки каждого полигона
        import time

        polygon_start_time = time.time()

        polygon = carpet.polygon
        file_name = carpet.filename
        color = carpet.color
        order_id = carpet.order_id

        placed_successfully = False

        # Check if polygon is too large for the sheet
        bounds = polygon.bounds
        poly_width = bounds[2] - bounds[0]
        poly_height = bounds[3] - bounds[1]

        if poly_width > sheet_width_mm or poly_height > sheet_height_mm:
            unplaced.append((polygon, file_name, color, order_id))
            continue

        # REVOLUTIONARY: Try all rotations with TETRIS PRIORITY (bottom-left first)
        best_placement = None
        best_priority = float("inf")  # Lower is better (Y*1000 + X)

        # Only allowed rotation angles for cutting machines
        rotation_angles = [0, 90, 180, 270]

        for angle in rotation_angles:
            rotated = rotate_polygon(polygon, angle) if angle != 0 else polygon
            rotated_bounds = rotated.bounds
            rotated_width = rotated_bounds[2] - rotated_bounds[0]
            rotated_height = rotated_bounds[3] - rotated_bounds[1]

            # Skip if doesn't fit
            if rotated_width > sheet_width_mm or rotated_height > sheet_height_mm:
                continue

            # Find position using Tetris gravity algorithm
            best_x, best_y = find_bottom_left_position_with_obstacles(
                rotated, obstacles, sheet_width_mm, sheet_height_mm
            )

            if best_x is not None and best_y is not None:
                # TETRIS STRATEGY: Prioritize orientations that create more space

                # Base position score (prefer bottom-left)
                position_score = best_y * 10 + best_x * 100

                # УЛУЧШЕННЫЙ ТЕТРИС: Более чувствительная оценка aspect ratio
                shape_bonus = 0
                aspect_ratio = rotated_width / rotated_height if rotated_height > 0 else 1

                # Bonus for longest side horizontal (along bottom/top edges)
                if aspect_ratio > 1.05:  # Даже слегка широкие получают бонус
                    # Прогрессивный бонус в зависимости от степени "широкости"
                    width_bonus = min(2000, int((aspect_ratio - 1) * 2000))
                    shape_bonus -= width_bonus

                    # Extra bonus if touching bottom edge (creating clean horizontal line)
                    if best_y < 5:  # Within 5mm of bottom
                        shape_bonus -= 3000  # Увеличенный бонус за касание низа

                    # Extra bonus if touching left edge (creating clean vertical line)
                    if best_x < 5:  # Within 5mm of left
                        shape_bonus -= 2000  # Увеличенный бонус за касание левого края

                # Penalty for tall orientations (мы хотим горизонтальные)
                elif aspect_ratio < 0.95:  # Высокие получают штраф
                    height_penalty = min(1000, int((1 - aspect_ratio) * 1000))
                    shape_bonus += height_penalty  # Штраф вместо бонуса

                # 🎯 МАКСИМИЗАЦИЯ ВЕРХНЕГО ПРОСТРАНСТВА: Стратегия для existing carpets
                # Симулируем размещение с учетом существующих ковров
                all_test_placed = existing_placed + placed + [PlacedCarpet(
                    translate_polygon(rotated, best_x - rotated_bounds[0], best_y - rotated_bounds[1]),
                    0, 0, angle, "test", "test", "test", 0, 1
                )]

                # Находим максимальную высоту после размещения
                max_height_after = max(c.polygon.bounds[3] for c in all_test_placed) if all_test_placed else 0

                # Вычисляем площадь свободного пространства сверху
                free_top_area = sheet_width_mm * (sheet_height_mm - max_height_after)

                # МЕГА-БОНУС за максимизацию верхнего пространства
                if free_top_area > 50000:  # Больше 500 см² свободного места сверху
                    tetris_super_bonus = min(12000, int(free_top_area / 120))
                    shape_bonus -= tetris_super_bonus

                # Бонус за размещение в нижней части листа
                height_from_bottom = best_y
                if height_from_bottom < sheet_height_mm * 0.4:  # В нижних 40% листа
                    low_placement_bonus = int((sheet_height_mm * 0.4 - height_from_bottom) * 3)
                    shape_bonus -= low_placement_bonus

                total_score = position_score + shape_bonus

                if total_score < best_priority:
                    best_priority = total_score
                    translated = translate_polygon(
                        rotated, best_x - rotated_bounds[0], best_y - rotated_bounds[1]
                    )
                    best_placement = {
                        "polygon": translated,
                        "x_offset": best_x - rotated_bounds[0],
                        "y_offset": best_y - rotated_bounds[1],
                        "angle": angle,
                    }

        # Apply best placement if found
        if best_placement:
            placed.append(
                PlacedCarpet(
                    best_placement["polygon"],
                    best_placement["x_offset"],
                    best_placement["y_offset"],
                    best_placement["angle"],
                    file_name,
                    color,
                    order_id,
                    carpet.carpet_id,
                    carpet.priority,

                )
            )

            # 🚀 РЕВОЛЮЦИОННАЯ TETRIS-ОПТИМИЗАЦИЯ: Гравитация + Сжатие к краям
            if len(placed) > 1:  # Несколько новых ковров
                try:
                    # Этап 1: Гравитация
                    gravity_placed = apply_tetris_gravity(placed, sheet_width_mm, sheet_height_mm)

                    # Этап 2: Сжатие к правому краю
                    right_placed = apply_tetris_right_compaction(gravity_placed, sheet_width_mm, sheet_height_mm)

                    # Этап 3: Финальная гравитация
                    improved_placed = apply_tetris_gravity(right_placed, sheet_width_mm, sheet_height_mm)

                    # КРИТИЧНО: Ультра-строгая проверка коллизий
                    safe = True
                    for i in range(len(improved_placed)):
                        for j in range(i+1, len(improved_placed)):
                            if check_collision(
                                improved_placed[i].polygon,
                                improved_placed[j].polygon,
                                min_gap=2.0  # Строгий 2мм зазор
                            ):
                                safe = False
                                break
                        if not safe:
                            break

                    # Проверяем коллизии с существующими коврами
                    if safe:
                        for new_carpet in improved_placed:
                            for existing_carpet in existing_placed:
                                if new_carpet.polygon.intersects(existing_carpet.polygon):
                                    intersection = new_carpet.polygon.intersection(existing_carpet.polygon)
                                    if intersection.area > 50:
                                        safe = False
                                        break
                            if not safe:
                                break

                    if safe:
                        placed = improved_placed

                except Exception:
                    pass  # Игнорируем ошибки гравитации

            # Добавляем как препятствие для следующих ковров
            obstacles.append(best_placement["polygon"])

            placed_successfully = True

        if not placed_successfully:
            unplaced.append(UnplacedCarpet.from_carpet(carpet))

        # ПРОФИЛИРОВАНИЕ: Логируем время обработки медленных полигонов
        polygon_elapsed = time.time() - polygon_start_time
        if polygon_elapsed > 2.0:  # Логируем полигоны, обрабатывающиеся дольше 2 секунд
            logger.warning(
                f"⏱️ Медленный полигон {file_name}: {polygon_elapsed:.2f}s, размещен={placed_successfully}"
            )

    # FAST OPTIMIZATION for existing sheets
    if tighten and len(placed) <= 5:  # Very conservative optimization
        # Apply simple compaction only for tiny sets
        placed = simple_compaction(placed, sheet_size)

        # Light tightening with obstacles
        all_obstacles = existing_placed + placed
        placed = tighten_layout_with_obstacles(placed, all_obstacles, sheet_size, min_gap=1.0)

    return placed, unplaced


def ultra_left_compaction(
    placed: list[PlacedCarpet],
    sheet_size: tuple[float, float],
    target_width_fraction: float = 0.7  # Try to fit everything in 70% of sheet width
) -> list[PlacedCarpet]:
    """ULTRA-AGGRESSIVE left compaction - squeeze everything to the left side."""
    if not placed:
        return placed

    sheet_width_mm = sheet_size[0] * 10
    sheet_height_mm = sheet_size[1] * 10
    target_width = sheet_width_mm * target_width_fraction

    current_polys = [item.polygon for item in placed]
    meta = placed[:]
    n = len(current_polys)

    # Ultra-aggressive left push - try to fit all in left portion
    for iteration in range(3):  # Multiple passes for maximum effect
        moved_any = False

        # Sort by current X position (process rightmost first)
        x_order = sorted(range(n), key=lambda i: -current_polys[i].bounds[0])

        for i in x_order:
            poly = current_polys[i]
            bounds = poly.bounds

            # Calculate how far left we can push this polygon
            current_right = bounds[2]
            desired_right = target_width  # Want to fit in target area

            if current_right > desired_right:
                # Calculate how much we need to move left
                required_move = current_right - desired_right
                max_possible_move = bounds[0]  # Can't go beyond left edge

                # Try to move as much as needed, but not beyond possible
                move_distance = min(required_move, max_possible_move)

                # Try progressive distances
                for distance in [move_distance, move_distance * 0.75, move_distance * 0.5, move_distance * 0.25, 10.0, 5.0, 2.0, 1.0]:
                    if distance < 0.5:
                        continue

                    test = translate_polygon(poly, -distance, 0)
                    if test.bounds[0] < 0:  # Don't go beyond left edge
                        continue

                    # Check collisions
                    collision = False
                    for j in range(n):
                        if j != i and test.intersects(current_polys[j]):
                            collision = True
                            break

                    if not collision:
                        current_polys[i] = test
                        moved_any = True
                        break

        if not moved_any:
            break

    # Create result
    new_placed = []
    for i in range(n):
        new_poly = current_polys[i]
        orig_poly = placed[i].polygon

        dx_total = new_poly.bounds[0] - orig_poly.bounds[0]
        dy_total = new_poly.bounds[1] - orig_poly.bounds[1]

        item = meta[i]
        new_placed.append(
            PlacedCarpet(
                new_poly,
                item.x_offset + dx_total,
                item.y_offset + dy_total,
                item.angle,
                item.filename,
                item.color,
                item.order_id,
                item.carpet_id,
                item.priority,
            )
        )

    return new_placed


def simple_compaction(
    placed: list[PlacedCarpet],
    sheet_size: tuple[float, float],
    min_gap: float = 0.5
) -> list[PlacedCarpet]:
    """FAST Simple compaction - just basic left+down movement."""
    if not placed or len(placed) > 35:  # Allow processing of larger sets
        return placed

    sheet_width_mm = sheet_size[0] * 10
    sheet_height_mm = sheet_size[1] * 10

    current_polys = [item.polygon for item in placed]
    meta = placed[:]
    n = len(current_polys)

    moved_any = True
    max_passes = 2  # Very limited passes

    for pass_num in range(max_passes):
        if not moved_any:
            break
        moved_any = False

        # Simple down movement
        for i in range(n):
            poly = current_polys[i]
            step = 2.0  # Large steps for speed

            while True:
                test = translate_polygon(poly, 0, -step)
                if test.bounds[1] < 0:
                    break

                # Quick collision check - only intersections
                collision = False
                for j in range(n):
                    if j != i and test.intersects(current_polys[j]):
                        collision = True
                        break

                if collision:
                    break

                current_polys[i] = test
                poly = test
                moved_any = True

        # AGGRESSIVE LEFT MOVEMENT - push as far left as possible
        x_order = sorted(range(n), key=lambda i: current_polys[i].bounds[0])  # Process left to right

        for i in x_order:
            poly = current_polys[i]
            bounds = poly.bounds

            # Calculate maximum possible left movement
            max_left_move = bounds[0]  # Distance to left edge

            # Try to move maximum distance first, then smaller steps
            for left_distance in [max_left_move, max_left_move * 0.75, max_left_move * 0.5, max_left_move * 0.25, 5.0, 2.0, 1.0]:
                if left_distance < 0.5:  # Skip tiny movements
                    continue

                test = translate_polygon(poly, -left_distance, 0)
                if test.bounds[0] < 0:  # Don't go beyond left edge
                    continue

                collision = False
                for j in range(n):
                    if j != i and test.intersects(current_polys[j]):
                        collision = True
                        break

                if not collision:
                    current_polys[i] = test
                    moved_any = True
                    break  # Found best position, move to next polygon

    # Create result
    new_placed = []
    for i in range(n):
        new_poly = current_polys[i]
        orig_poly = placed[i].polygon

        dx_total = new_poly.bounds[0] - orig_poly.bounds[0]
        dy_total = new_poly.bounds[1] - orig_poly.bounds[1]

        item = meta[i]
        new_placed.append(
            PlacedCarpet(
                new_poly,
                item.x_offset + dx_total,
                item.y_offset + dy_total,
                item.angle,
                item.filename,
                item.color,
                item.order_id,
                item.carpet_id,
                item.priority,
            )
        )

    return new_placed


def fast_edge_snap(
    placed: list[PlacedCarpet],
    sheet_size: tuple[float, float],
    min_gap: float = 1.0
) -> list[PlacedCarpet]:
    """FAST edge snapping - just basic left/bottom movement."""
    if not placed or len(placed) > 25:  # Allow larger sets for better optimization
        return placed

    sheet_width_mm = sheet_size[0] * 10
    sheet_height_mm = sheet_size[1] * 10

    current_polys = [item.polygon for item in placed]
    meta = placed[:]
    n = len(current_polys)

    max_iterations = 2  # Very limited iterations

    for iteration in range(max_iterations):
        moved_any = False

        # Simple movement - try to move each polygon left and down
        for i in range(n):
            poly = current_polys[i]

            # Try to move down
            step = 5.0  # Large step for speed
            test = translate_polygon(poly, 0, -step)
            if test.bounds[1] >= 0:
                # Quick collision check - only intersections
                collision = False
                for j in range(n):
                    if j != i and test.intersects(current_polys[j]):
                        collision = True
                        break

                if not collision:
                    current_polys[i] = test
                    moved_any = True
                    poly = test

            # AGGRESSIVE LEFT PUSH - move as far left as possible
            bounds = poly.bounds
            max_left = bounds[0]  # Maximum distance we can move left

            # Try progressively smaller left movements for maximum compaction
            for left_distance in [max_left, max_left * 0.75, max_left * 0.5, max_left * 0.25, step, step/2]:
                if left_distance < 0.5:
                    continue

                test = translate_polygon(poly, -left_distance, 0)
                if test.bounds[0] < 0:
                    continue

                collision = False
                for j in range(n):
                    if j != i and test.intersects(current_polys[j]):
                        collision = True
                        break

                if not collision:
                    current_polys[i] = test
                    moved_any = True
                    break  # Found best left position

        if not moved_any:
            break

    # Create result list
    new_placed: list[PlacedCarpet] = []

    for i in range(n):
        new_poly = current_polys[i]
        orig_poly = placed[i].polygon

        # Calculate total displacement
        dx_total = new_poly.bounds[0] - orig_poly.bounds[0]
        dy_total = new_poly.bounds[1] - orig_poly.bounds[1]

        item = meta[i]
        new_x_off = item.x_offset + dx_total
        new_y_off = item.y_offset + dy_total

        new_placed.append(
            PlacedCarpet(
                new_poly,
                new_x_off,
                new_y_off,
                item.angle,
                item.filename,
                item.color,
                item.order_id,
                item.carpet_id,
                item.priority,
            )
        )

    return new_placed


def bin_packing(
    polygons: list[Carpet],
    sheet_size: tuple[float, float],
    verbose: bool = True,
    max_processing_time: float = 60.0,  # Reduced to 1 minute timeout
    progress_callback=None,  # Callback function for progress updates
) -> tuple[list[PlacedCarpet], list[UnplacedCarpet]]:
    """Optimize placement of complex polygons on a sheet with ultra-dense/polygonal/improved algorithms."""
    import time

    start_time = time.time()

    # Convert sheet size from cm to mm to match DXF polygon units
    sheet_width_mm, sheet_height_mm = sheet_size[0] * 10, sheet_size[1] * 10

    placed: list[PlacedCarpet] = []
    unplaced: list[UnplacedCarpet] = []

    if verbose:
        st.info(
            f"Начинаем стандартную упаковку {len(polygons)} полигонов на листе {sheet_size[0]}x{sheet_size[1]} см"
        )

    # IMPROVEMENT 1: Enhanced polygon sorting for optimal packing density
    def get_polygon_priority(carpet: Carpet):
        polygon = carpet.polygon
        area = polygon.area
        bounds = polygon.bounds
        width = bounds[2] - bounds[0]
        height = bounds[3] - bounds[1]

        # Multi-factor scoring for better packing:
        # 1. Area (larger first)
        # 2. Aspect ratio (irregular shapes first)
        # 3. Compactness (less regular shapes first)
        aspect_ratio = (
            max(width / height, height / width) if min(width, height) > 0 else 1
        )
        compactness = area / (width * height) if width * height > 0 else 0
        perimeter_approx = 2 * (width + height)

        # Prioritize larger, more irregular shapes for better space utilization
        return (
            area * 1.0
            + (aspect_ratio - 1) * area * 0.3
            + (1 - compactness) * area * 0.2
            + perimeter_approx * 0.05
        )

    sorted_polygons = sorted(polygons, key=get_polygon_priority, reverse=True)

    # Set dataset size context for adaptive algorithms
    find_bottom_left_position._dataset_size = len(sorted_polygons)

    if verbose:
        st.info("✨ Сортировка полигонов по площади (сначала крупные)")

    for i, carpet in enumerate(sorted_polygons):
        # Check timeout
        if time.time() - start_time > max_processing_time:
            if verbose:
                st.warning(
                    f"⏰ Превышено время обработки ({max_processing_time}s), остальные полигоны добавлены в неразмещенные"
                )
            unplaced.extend(
                UnplacedCarpet.from_carpet(carpet)
                for carpet in sorted_polygons[i:]
            )
            break

        placed_successfully = False

        # Check if polygon is too large for the sheet
        bounds = carpet.polygon.bounds
        poly_width = bounds[2] - bounds[0]
        poly_height = bounds[3] - bounds[1]

        if poly_width > sheet_width_mm or poly_height > sheet_height_mm:
            if verbose:
                st.warning(
                    f"Полигон из {carpet.filename} слишком большой: {poly_width/10:.1f}x{poly_height/10:.1f} см > {sheet_size[0]}x{sheet_size[1]} см"
                )
            unplaced.append(UnplacedCarpet.from_carpet(carpet))
            continue

        # REVOLUTIONARY TETRIS ROTATION STRATEGY: Optimize for space liberation
        best_placement = None
        best_score = float("inf")  # Lower is better

        rotation_angles = [0, 90, 180, 270]

        for angle in rotation_angles:
            rotated = (
                rotate_polygon(carpet.polygon, angle) if angle != 0 else carpet.polygon
            )
            rotated_bounds = rotated.bounds
            rotated_width = rotated_bounds[2] - rotated_bounds[0]
            rotated_height = rotated_bounds[3] - rotated_bounds[1]

            # Skip if doesn't fit
            if rotated_width > sheet_width_mm or rotated_height > sheet_height_mm:
                continue

            # Use Tetris gravity algorithm for placement
            best_x, best_y = find_bottom_left_position(
                rotated, placed, sheet_width_mm, sheet_height_mm
            )

            if best_x is not None and best_y is not None:
                # TETRIS STRATEGY: Prioritize orientations that create more space

                # Base position score (prefer bottom-left)
                position_score = best_y * 10 + best_x * 100

                # УЛУЧШЕННЫЙ ТЕТРИС: Более чувствительная оценка aspect ratio
                shape_bonus = 0
                aspect_ratio = rotated_width / rotated_height if rotated_height > 0 else 1

                # Bonus for longest side horizontal (along bottom/top edges)
                if aspect_ratio > 1.05:  # Даже слегка широкие получают бонус
                    # Прогрессивный бонус в зависимости от степени "широкости"
                    width_bonus = min(2000, int((aspect_ratio - 1) * 2000))
                    shape_bonus -= width_bonus

                    # Extra bonus if touching bottom edge (creating clean horizontal line)
                    if best_y < 5:  # Within 5mm of bottom
                        shape_bonus -= 3000  # Увеличенный бонус за касание низа

                    # Extra bonus if touching left edge (creating clean vertical line)
                    if best_x < 5:  # Within 5mm of left
                        shape_bonus -= 2000  # Увеличенный бонус за касание левого края

                # Penalty for tall orientations (мы хотим горизонтальные)
                elif aspect_ratio < 0.95:  # Высокие получают штраф
                    height_penalty = min(1000, int((1 - aspect_ratio) * 1000))
                    shape_bonus += height_penalty  # Штраф вместо бонуса

                # 🎯 МАКСИМИЗАЦИЯ ВЕРХНЕГО ПРОСТРАНСТВА: Ключевая Тетрис-стратегия
                # Предпочитаем ориентации которые максимизируют непрерывное свободное пространство сверху

                # Симулируем размещение этого ковра и вычисляем будущую максимальную высоту
                test_placed = placed + [PlacedCarpet(
                    translate_polygon(rotated, best_x - rotated_bounds[0], best_y - rotated_bounds[1]),
                    0, 0, angle, "test", "test", "test", 0, 1
                )]

                # Находим максимальную высоту после размещения
                max_height_after = max(c.polygon.bounds[3] for c in test_placed) if test_placed else 0

                # Вычисляем площадь свободного пространства сверху
                free_top_area = sheet_width_mm * (sheet_height_mm - max_height_after)

                # МЕГА-БОНУС за максимизацию верхнего пространства
                if free_top_area > 100000:  # Больше 1000 см² свободного места сверху
                    tetris_super_bonus = min(15000, int(free_top_area / 150))  # До -15000 очков!
                    shape_bonus -= tetris_super_bonus

                # Дополнительный бонус за низкое размещение (ближе к низу)
                height_from_bottom = best_y
                if height_from_bottom < sheet_height_mm * 0.3:  # В нижних 30% листа
                    low_placement_bonus = int((sheet_height_mm * 0.3 - height_from_bottom) * 5)
                    shape_bonus -= low_placement_bonus

                total_score = position_score + shape_bonus

                if total_score < best_score:
                    best_score = total_score
                    translated = translate_polygon(
                        rotated, best_x - rotated_bounds[0], best_y - rotated_bounds[1]
                    )
                    best_placement = {
                        "polygon": translated,
                        "x_offset": best_x - rotated_bounds[0],
                        "y_offset": best_y - rotated_bounds[1],
                        "angle": angle,
                    }

        # Apply best placement if found
        if best_placement:
            placed.append(
                PlacedCarpet(
                    best_placement["polygon"],
                    best_placement["x_offset"],
                    best_placement["y_offset"],
                    best_placement["angle"],
                    carpet.filename,
                    carpet.color,
                    carpet.order_id,
                    carpet.carpet_id,
                    carpet.priority,
                )
            )

            # 🚀 РЕВОЛЮЦИОННАЯ POST-PLACEMENT OPTIMIZATION
            if len(placed) >= 2:  # Применяем только если есть что оптимизировать
                try:
                    # Этап 1: АГРЕССИВНАЯ Post-Placement оптимизация (полное переразмещение проблемных ковров)
                    post_optimized = post_placement_optimize_aggressive(placed, sheet_width_mm, sheet_height_mm)

                    # Этап 2: Гравитация для финальной компактификации
                    gravity_optimized = apply_tetris_gravity(post_optimized, sheet_width_mm, sheet_height_mm)

                    # Этап 3: НОВОЕ! Сжатие к правому краю (как в настоящем Тетрисе)
                    right_compacted = apply_tetris_right_compaction(gravity_optimized, sheet_width_mm, sheet_height_mm)

                    # Этап 4: Финальная гравитация после сжатия к правому краю
                    final_optimized = apply_tetris_gravity(right_compacted, sheet_width_mm, sheet_height_mm)

                    # КРИТИЧНО: Проверяем безопасность финального результата с ультра-строгим контролем
                    collision_found = False
                    for i in range(len(final_optimized)):
                        for j in range(i+1, len(final_optimized)):
                            if check_collision(
                                final_optimized[i].polygon,
                                final_optimized[j].polygon,
                                min_gap=2.0  # Строгий 2мм зазор
                            ):
                                collision_found = True
                                break
                        if collision_found:
                            break

                    if not collision_found:
                        # Вычисляем улучшения
                        original_trapped = calculate_trapped_space(placed, sheet_width_mm, sheet_height_mm)
                        optimized_trapped = calculate_trapped_space(final_optimized, sheet_width_mm, sheet_height_mm)

                        trapped_improvement = original_trapped - optimized_trapped

                        placed = final_optimized  # Применяем полную оптимизацию

                        if verbose and trapped_improvement > 5000:  # Больше 500 см² улучшения
                            st.success(f"🎯 Post-Placement оптимизация освободила {trapped_improvement/100:.0f} см² заперного пространства!")

                        # Дополнительная информация о верхнем пространстве
                        free_top_area = calculate_free_top_space(placed, sheet_width_mm, sheet_height_mm)
                        if verbose and free_top_area > 50000:  # Больше 500 см²
                            st.info(f"🏞️ Свободно сверху: {free_top_area/10000:.0f} см²")

                    elif verbose:
                        st.warning("⚠️ Post-Placement оптимизация отменена - обнаружены коллизии")

                except Exception as e:
                    if verbose:
                        st.error(f"❌ Ошибка Post-Placement оптимизации: {e}")
                        # Продолжаем с исходным размещением

            placed_successfully = True
            if verbose:
                st.success(
                    f"✅ Размещен {carpet.filename} (угол: {best_placement['angle']}°)"
                )
        else:
            # Fallback to original grid method if no bottom-left position found
            simple_bounds = carpet.polygon.bounds
            simple_width = simple_bounds[2] - simple_bounds[0]
            simple_height = simple_bounds[3] - simple_bounds[1]

            # Optimized grid placement as fallback with timeout
            max_grid_attempts = (
                5 if len(placed) > 10 else 10
            )  # Further reduced for many obstacles
            if sheet_width_mm > simple_width:
                x_positions = np.linspace(
                    0, sheet_width_mm - simple_width, max_grid_attempts
                )
            else:
                x_positions = [0]

            if sheet_height_mm > simple_height:
                y_positions = np.linspace(
                    0, sheet_height_mm - simple_height, max_grid_attempts
                )
            else:
                y_positions = [0]

            for grid_x in x_positions:
                for grid_y in y_positions:
                    x_offset = grid_x - simple_bounds[0]
                    y_offset = grid_y - simple_bounds[1]

                    # Fast bounds check with minimal tolerance for tight packing
                    test_bounds = (
                        simple_bounds[0] + x_offset,
                        simple_bounds[1] + y_offset,
                        simple_bounds[2] + x_offset,
                        simple_bounds[3] + y_offset,
                    )

                    if not (
                        test_bounds[0] >= -0.01
                        and test_bounds[1] >= -0.01
                        and test_bounds[2] <= sheet_width_mm + 0.01
                        and test_bounds[3] <= sheet_height_mm + 0.01
                    ):
                        continue

                    # Skip ALL bounding box checks - use only true geometric collision
                    translated = translate_polygon(carpet.polygon, x_offset, y_offset)

                    # Final precise collision check
                    collision = False
                    for placed_poly in placed:
                        if check_collision(translated, placed_poly.polygon):
                            collision = True
                            break

                    if not collision:
                        placed.append(
                            PlacedCarpet(
                                translated,
                                x_offset,
                                y_offset,
                                0,
                                carpet.filename,
                                carpet.color,
                                carpet.order_id,
                                carpet.carpet_id,
                                carpet.priority
                            )
                        )
                        placed_successfully = True
                        if verbose:
                            st.success(
                                f"✅ Размещен {carpet.filename} (сетчатое размещение)"
                            )
                        break

                if placed_successfully:
                    break

        if not placed_successfully:
            if verbose:
                st.warning(f"❌ Не удалось разместить полигон из {carpet.filename}")
            unplaced.append(
                UnplacedCarpet(
                    carpet.polygon, carpet.filename, carpet.color, carpet.order_id
                )
            )

    # ULTRA-AGGRESSIVE LEFT COMPACTION - always apply for maximum density
    if len(placed) <= 20:  # Optimize most reasonable sets
        # Ultra-aggressive left compaction to squeeze everything left
        placed = ultra_left_compaction(placed, sheet_size, target_width_fraction=0.4)

        # Simple compaction with aggressive left push
        placed = simple_compaction(placed, sheet_size)

        # Additional edge snapping for maximum left compaction
        placed = fast_edge_snap(placed, sheet_size)

        # Final ultra-left compaction
        placed = ultra_left_compaction(placed, sheet_size, target_width_fraction=0.5)

        # Light tightening to clean up
        placed = tighten_layout(placed, sheet_size, min_gap=0.5, step=2.0, max_passes=1)
    elif len(placed) <= 35:  # For larger sets, still do aggressive compaction
        placed = ultra_left_compaction(placed, sheet_size, target_width_fraction=0.6)
        placed = simple_compaction(placed, sheet_size)
        placed = fast_edge_snap(placed, sheet_size)
    # No optimization for very large sets

    if verbose:
        usage_percent = calculate_usage_percent(placed, sheet_size)
        st.info(
            f"🏁 Упаковка завершена: {len(placed)} размещено, {len(unplaced)} не размещено, использование: {usage_percent:.1f}%"
        )
    return placed, unplaced


def find_contour_following_position(
    polygon: Polygon, obstacles: list[Polygon], sheet_width: float, sheet_height: float
) -> tuple[float | None, float | None]:
    """Find position using TRUE CONTOUR-FOLLOWING - shapes can nestle into concave areas!"""
    bounds = polygon.bounds
    poly_width = bounds[2] - bounds[0]
    poly_height = bounds[3] - bounds[1]

    candidates = []

    # REVOLUTIONARY: Follow actual shape contours, not bounding boxes
    for obstacle in obstacles[:8]:  # Limit for performance
        # Get the actual boundary coordinates of the obstacle
        if hasattr(obstacle.exterior, "coords"):
            contour_points = list(obstacle.exterior.coords)

            # Generate positions along the actual contour with minimal gaps
            for i, (cx, cy) in enumerate(
                contour_points[:-1]
            ):  # Skip last duplicate point
                # Try positioning our polygon at various points along this contour
                test_positions = [
                    # Right of this contour point
                    (cx + 0.1, cy - poly_height / 2),
                    (cx + 0.1, cy),
                    (cx + 0.1, cy - poly_height),
                    # Above this contour point
                    (cx - poly_width / 2, cy + 0.1),
                    (cx, cy + 0.1),
                    (cx - poly_width, cy + 0.1),
                ]

                for test_x, test_y in test_positions:
                    if (
                        0 <= test_x <= sheet_width - poly_width
                        and 0 <= test_y <= sheet_height - poly_height
                    ):
                        candidates.append((test_x, test_y))

    # Add sheet edges
    step = max(1.0, min(poly_width, poly_height) / 10)  # Adaptive step
    for x in np.arange(0, sheet_width - poly_width + 1, step):
        candidates.append((x, 0))
    for y in np.arange(0, sheet_height - poly_height + 1, step):
        candidates.append((0, y))

    # Sort by bottom-left preference and limit candidates
    candidates = list(set(candidates))  # Remove duplicates
    candidates.sort(key=lambda pos: (pos[1], pos[0]))
    candidates = candidates[: min(1000, len(candidates))]  # Performance limit

    # Test each position using true geometric collision detection
    for x, y in candidates:
        x_offset = x - bounds[0]
        y_offset = y - bounds[1]
        test_polygon = translate_polygon(polygon, x_offset, y_offset)

        # Use our new TRUE GEOMETRIC collision check (no bounding box constraints!)
        collision = False
        for obstacle in obstacles:
            if check_collision(test_polygon, obstacle, min_gap=0.1):  # Ultra-tight
                collision = True
                break

        if not collision:
            return x, y

    return None, None


def find_ultra_tight_position(
    polygon: Polygon, obstacles: list[Polygon], sheet_width: float, sheet_height: float
) -> tuple[float | None, float | None]:
    """Find ultra-tight position using contour-following for maximum density."""

    # Try new contour-following algorithm first
    result = find_contour_following_position(
        polygon, obstacles, sheet_width, sheet_height
    )
    if result[0] is not None:
        return result

    # Fallback to grid-based approach
    bounds = polygon.bounds
    poly_width = bounds[2] - bounds[0]
    poly_height = bounds[3] - bounds[1]

    # Use fine grid for small number of obstacles
    step_size = 1.0 if len(obstacles) <= 5 else 2.0
    candidates = []

    # Grid search with no bounding box prefiltering
    for x in np.arange(0, sheet_width - poly_width + 1, step_size):
        for y in np.arange(0, sheet_height - poly_height + 1, step_size):
            candidates.append((x, y))
            if len(candidates) >= 500:  # Performance limit
                break
        if len(candidates) >= 500:
            break

    # Test positions using pure geometric collision detection
    for x, y in candidates:
        x_offset = x - bounds[0]
        y_offset = y - bounds[1]
        test_polygon = translate_polygon(polygon, x_offset, y_offset)

        collision = False
        for obstacle in obstacles:
            if check_collision(test_polygon, obstacle, min_gap=0.1):
                collision = True
                break

        if not collision:
            return x, y

    return None, None


def find_bottom_left_position_with_obstacles(
    polygon: Polygon, obstacles: list[Polygon], sheet_width: float, sheet_height: float
) -> tuple[float | None, float | None]:
    """Find the bottom-left position for a polygon using ultra-tight packing algorithm."""
    # Try ultra-tight algorithm first
    result = find_ultra_tight_position(polygon, obstacles, sheet_width, sheet_height)
    if result[0] is not None:
        return result

    # Fallback to improved algorithm
    bounds = polygon.bounds
    bounds = polygon.bounds
    poly_width = bounds[2] - bounds[0]
    poly_height = bounds[3] - bounds[1]

    # Try positions along bottom and left edges first
    candidate_positions = []

    # ОПТИМИЗАЦИЯ: Увеличиваем шаг сетки для ускорения поиска
    grid_step = 15  # Увеличено с 5mm до 15mm для 3x ускорения

    # Bottom edge positions
    for x in np.arange(0, sheet_width - poly_width + 1, grid_step):
        candidate_positions.append((x, 0))

    # Left edge positions
    for y in np.arange(0, sheet_height - poly_height + 1, grid_step):
        candidate_positions.append((0, y))

    # Positions based on existing obstacles (bottom-left principle)
    for obstacle in obstacles:
        obstacle_bounds = obstacle.bounds

        # Try position to the right of existing obstacle
        x = obstacle_bounds[2] + 3  # 3mm gap for safety
        if x + poly_width <= sheet_width:
            candidate_positions.append((x, obstacle_bounds[1]))  # Same Y as existing
            candidate_positions.append((x, 0))  # Bottom edge

        # Try position above existing obstacle
        y = obstacle_bounds[3] + 3  # 3mm gap for safety
        if y + poly_height <= sheet_height:
            candidate_positions.append((obstacle_bounds[0], y))  # Same X as existing
            candidate_positions.append((0, y))  # Left edge

    # ОПТИМИЗАЦИЯ: Ограничиваем количество кандидатов для предотвращения взрывного роста
    candidate_positions = list(set(candidate_positions))  # Удаляем дубликаты
    candidate_positions.sort(
        key=lambda pos: (pos[1], pos[0])
    )  # Sort by bottom-left preference

    # Ограничиваем до 100 лучших позиций для ускорения
    # max_candidates = 100
    # if len(candidate_positions) > max_candidates:
    #    candidate_positions = candidate_positions[:max_candidates]

    # Test each position
    for x, y in candidate_positions:
        # OPTIMIZATION: Fast boundary pre-check without polygon creation
        if x + poly_width > sheet_width + 0.1 or y + poly_height > sheet_height + 0.1:
            continue
        if x < -0.1 or y < -0.1:
            continue

        # OPTIMIZATION: Pre-calculate translation offset
        x_offset = x - bounds[0]
        y_offset = y - bounds[1]

        # OPTIMIZATION: Check if bounds would be valid after translation
        test_bounds = (
            bounds[0] + x_offset,
            bounds[1] + y_offset,
            bounds[2] + x_offset,
            bounds[3] + y_offset,
        )
        if (
            test_bounds[0] < -0.1
            or test_bounds[1] < -0.1
            or test_bounds[2] > sheet_width + 0.1
            or test_bounds[3] > sheet_height + 0.1
        ):
            continue

        # Only create translated polygon if all checks pass
        test_polygon = translate_polygon(polygon, x_offset, y_offset)

        # OPTIMIZATION: Early exit on first collision
        collision = False
        for obstacle in obstacles:
            if check_collision(test_polygon, obstacle):
                collision = True
                break

        if not collision:
            return x, y

    return None, None


def find_quick_position(
    polygon: Polygon, placed_polygons, sheet_width: float, sheet_height: float
) -> tuple[float | None, float | None]:
    """Quick position finding for scenarios with many obstacles."""
    bounds = polygon.bounds
    poly_width = bounds[2] - bounds[0]
    poly_height = bounds[3] - bounds[1]

    # Use reasonable steps for balance of speed and density
    step_size = 2.0  # Reduced from 5.0 for better placement options
    max_positions = 200  # Increased from 100 for better coverage

    # Generate minimal candidate set
    candidates = []

    # Bottom edge with large steps
    for x in np.arange(0, sheet_width - poly_width + 1, step_size):
        candidates.append((x, 0))
        if len(candidates) >= max_positions:
            break

    # Left edge with large steps
    for y in np.arange(0, sheet_height - poly_height + 1, step_size):
        candidates.append((0, y))
        if len(candidates) >= max_positions:
            break

    # Test positions quickly
    for x, y in candidates:
        if x + poly_width <= sheet_width and y + poly_height <= sheet_height:
            x_offset = x - bounds[0]
            y_offset = y - bounds[1]
            test_polygon = translate_polygon(polygon, x_offset, y_offset)

            # Quick collision check with looser tolerance
            collision = False
            for placed_poly in placed_polygons:
                if check_collision(
                    test_polygon, placed_poly.polygon, min_gap=2.0
                ):  # Looser gap
                    collision = True
                    break

            if not collision:
                return x, y

    return None, None


def find_bottom_left_position(
    polygon: Polygon, placed_polygons, sheet_width: float, sheet_height: float
):
    """FAST Simple bottom-left placement - prioritize speed over perfect density."""

    # First placement - always bottom-left corner
    if not placed_polygons:
        return 0, 0

    bounds = polygon.bounds
    poly_width = bounds[2] - bounds[0]
    poly_height = bounds[3] - bounds[1]

    # FAST SCAN: Use large steps for speed
    step = max(10.0, min(poly_width, poly_height) / 3)  # Large adaptive step for speed

    best_y = None
    best_positions = []

    # PRIORITY LEFT SCAN - try left positions first for maximum compaction
    # Create X positions with strong preference for left side
    x_positions = []
    for x in range(0, int(sheet_width - poly_width), max(5, int(step))):
        x_positions.append(x)

    # Sort to prioritize leftmost positions
    x_positions.sort()

    for test_x in x_positions[:15]:  # Limit for speed but favor left

        # Test only a few Y positions per X for speed
        test_y_positions = [0]  # Always try bottom

        # Add positions based on existing polygons (very limited)
        for placed_poly in placed_polygons[:2]:  # Only first 2 polygons for speed
            other_bounds = placed_poly.polygon.bounds
            test_y_positions.append(other_bounds[3] + 2.0)  # Above with 2mm gap

        # Test positions
        for test_y in sorted(set(test_y_positions)):
            if test_y < 0 or test_y + poly_height > sheet_height:
                continue

            # Quick test
            x_offset = test_x - bounds[0]
            y_offset = test_y - bounds[1]
            test_polygon = translate_polygon(polygon, x_offset, y_offset)

            # Simple bounds check
            test_bounds = test_polygon.bounds
            if (test_bounds[0] < 0 or test_bounds[1] < 0 or
                test_bounds[2] > sheet_width or test_bounds[3] > sheet_height):
                continue

            # CRITICAL FIX: Use proper collision detection with minimum gap
            collision = False
            for placed_poly in placed_polygons:
                if check_collision(test_polygon, placed_poly.polygon, min_gap=2.0):  # 2mm minimum gap
                    collision = True
                    break

            if not collision:
                if best_y is None or test_y < best_y:
                    best_y = test_y
                    best_positions = [(test_x, test_y)]
                elif test_y == best_y:
                    best_positions.append((test_x, test_y))
                break

    # Return leftmost position
    if best_positions:
        best_positions.sort()
        return best_positions[0]

    # Simple fallback - try grid positions
    for y in range(0, int(sheet_height - poly_height), 20):
        for x in range(0, int(sheet_width - poly_width), 20):
            x_offset = x - bounds[0]
            y_offset = y - bounds[1]
            test_polygon = translate_polygon(polygon, x_offset, y_offset)

            collision = False
            for placed_poly in placed_polygons:
                if check_collision(test_polygon, placed_poly.polygon, min_gap=2.0):  # 2mm minimum gap
                    collision = True
                    break

            if not collision:
                return x, y

    return None, None


def calculate_placement_waste(
    polygon: Polygon, placed_polygons: list[PlacedCarpet], sheet_width, sheet_height
):
    """Calculate waste/inefficiency for a polygon placement."""
    bounds = polygon.bounds

    # Calculate compactness - how close polygon is to other polygons and edges
    edge_distance = min(bounds[0], bounds[1])  # Distance to bottom-left corner

    # Distance to other polygons
    min_neighbor_distance = float("inf")
    for placed_tuple in placed_polygons:
        placed_polygon = placed_tuple.polygon
        placed_bounds = placed_polygon.bounds

        # Calculate minimum distance between bounding boxes
        dx = max(0, max(bounds[0] - placed_bounds[2], placed_bounds[0] - bounds[2]))
        dy = max(0, max(bounds[1] - placed_bounds[3], placed_bounds[1] - bounds[3]))
        distance = (dx**2 + dy**2) ** 0.5

        min_neighbor_distance = min(min_neighbor_distance, distance)

    if min_neighbor_distance == float("inf"):
        min_neighbor_distance = 0  # First polygon

    # Waste = edge_distance + average neighbor distance (lower is better)
    waste = edge_distance + min_neighbor_distance * 0.5
    return waste


def smart_bin_packing(
    carpets: list[Carpet],
    sheet_size: tuple[float, float],
    verbose: bool = False,
    progress_callback=None,
) -> tuple[list[PlacedCarpet], list[UnplacedCarpet]]:
    """Optimized single-pass bin packing with smart sorting."""
    if not carpets:
        return [], []
    
    # Smart sorting: prioritize area and width for better packing
    def get_smart_score(carpet: Carpet):
        bounds = carpet.polygon.bounds
        area = carpet.polygon.area
        width = bounds[2] - bounds[0]
        height = bounds[3] - bounds[1]
        
        # Combined score: large area + good aspect ratio
        aspect_penalty = abs(width - height) / max(width, height) if max(width, height) > 0 else 0
        return area * (1.0 + 0.2 * aspect_penalty)  # Slightly prefer more regular shapes
    
    smart_sorted = sorted(carpets, key=get_smart_score, reverse=True)
    
    # Use enhanced bin packing with tighter gap settings
    placed, unplaced = bin_packing(smart_sorted, sheet_size, verbose=verbose)
    
    return placed, unplaced


def consolidate_sheets_aggressive(
    placed_layouts: list[PlacedSheet]
) -> list[PlacedSheet]:
    """Aggressive sheet consolidation - try multiple strategies to reduce sheet count."""
    if len(placed_layouts) <= 1:
        return placed_layouts
    
    logger.info(f"Starting aggressive consolidation of {len(placed_layouts)} sheets")
    
    # Group sheets by color
    sheets_by_color = {}
    for layout in placed_layouts:
        color = layout.sheet_color
        if color not in sheets_by_color:
            sheets_by_color[color] = []
        sheets_by_color[color].append(layout)
    
    optimized_layouts = []
    
    for color, color_sheets in sheets_by_color.items():
        if len(color_sheets) <= 1:
            optimized_layouts.extend(color_sheets)
            continue
            
        logger.info(f"Consolidating {len(color_sheets)} sheets of color {color}")
        
        # Sort sheets by usage (least filled first, so we try to empty them)
        color_sheets.sort(key=lambda s: s.usage_percent)
        
        # Try to move carpets from the least filled sheets to more filled ones
        consolidated_sheets = []
        
        for target_sheet in color_sheets:
            if not target_sheet.placed_polygons:  # Skip empty sheets
                continue
                
            # Convert placed carpets back to Carpet objects
            target_carpets = []
            for placed_carpet in target_sheet.placed_polygons:
                carpet = Carpet(
                    placed_carpet.polygon,
                    placed_carpet.filename,
                    placed_carpet.color,
                    placed_carpet.order_id,
                    priority=1
                )
                target_carpets.append(carpet)
            
            # Try to fit these carpets on existing consolidated sheets
            placed_successfully = False
            
            for existing_sheet_idx, existing_sheet in enumerate(consolidated_sheets):
                if existing_sheet.usage_percent >= 95:  # Skip very full sheets
                    continue
                
                try:
                    # Try to add all carpets from target sheet to existing sheet
                    additional_placed, remaining_unplaced = bin_packing_with_existing(
                        target_carpets,
                        existing_sheet.placed_polygons,
                        existing_sheet.sheet_size,
                        verbose=False,
                    )
                    
                    if len(remaining_unplaced) == 0:  # All carpets fit!
                        # CRITICAL: Verify no overlaps before accepting consolidation
                        existing_polygons = [p.polygon for p in existing_sheet.placed_polygons]
                        new_polygons = [p.polygon for p in additional_placed]
                        
                        has_overlap = False
                        for new_poly in new_polygons:
                            for existing_poly in existing_polygons:
                                if check_collision(new_poly, existing_poly, min_gap=0.05):
                                    logger.error(f"Overlap detected during consolidation - rejecting")
                                    has_overlap = True
                                    break
                            if has_overlap:
                                break
                        
                        if not has_overlap:
                            consolidated_sheets[existing_sheet_idx].placed_polygons.extend(additional_placed)
                            consolidated_sheets[existing_sheet_idx].usage_percent = calculate_usage_percent(
                                consolidated_sheets[existing_sheet_idx].placed_polygons, 
                                existing_sheet.sheet_size
                            )
                            placed_successfully = True
                            logger.info(f"Consolidated entire sheet into sheet #{existing_sheet.sheet_number}")
                            break
                        else:
                            logger.warning(f"Consolidation rejected due to overlaps")
                        
                except Exception as e:
                    logger.debug(f"Failed to consolidate sheet: {e}")
                    continue
            
            if not placed_successfully:
                # Couldn't consolidate - keep as separate sheet
                consolidated_sheets.append(target_sheet)
        
        optimized_layouts.extend(consolidated_sheets)
    
    # Renumber sheets
    for i, layout in enumerate(optimized_layouts):
        layout.sheet_number = i + 1
    
    logger.info(f"Consolidation complete: {len(placed_layouts)} → {len(optimized_layouts)} sheets")
    return optimized_layouts


def simple_sheet_consolidation(
    placed_layouts: list[PlacedSheet]
) -> list[PlacedSheet]:
    """Simple sheet consolidation - try to move carpets from last sheet to previous ones."""
    if len(placed_layouts) <= 1:
        return placed_layouts
        
    logger.info("Attempting simple sheet consolidation")
    
    # Try to consolidate the last sheet (often the least filled)
    last_sheet = placed_layouts[-1]
    remaining_sheets = placed_layouts[:-1]
    
    carpets_to_move = []
    for placed_carpet in last_sheet.placed_polygons:
        carpet = Carpet(
            placed_carpet.polygon,
            placed_carpet.filename,
            placed_carpet.color,
            placed_carpet.order_id,
            priority=1
        )
        carpets_to_move.append(carpet)
    
    # Try to fit these carpets on existing sheets
    successfully_moved = 0
    for carpet in carpets_to_move:
        for layout_idx, layout in enumerate(remaining_sheets):
            if layout.sheet_color != carpet.color:
                continue
                
            if layout.usage_percent >= 90:  # Skip very full sheets
                continue
            
            try:
                additional_placed, remaining_unplaced = bin_packing_with_existing(
                    [carpet],
                    layout.placed_polygons,
                    layout.sheet_size,
                    verbose=False,
                )
                
                if additional_placed:
                    # Successfully moved!
                    remaining_sheets[layout_idx].placed_polygons.extend(additional_placed)
                    remaining_sheets[layout_idx].usage_percent = calculate_usage_percent(
                        remaining_sheets[layout_idx].placed_polygons, layout.sheet_size
                    )
                    successfully_moved += 1
                    logger.info(f"Moved carpet {carpet.filename} to sheet #{layout.sheet_number}")
                    break
                    
            except Exception as e:
                continue
    
    if successfully_moved == len(carpets_to_move):
        # All carpets moved successfully - remove last sheet
        logger.info(f"Successfully consolidated last sheet - moved {successfully_moved} carpets")
        return remaining_sheets
    else:
        # Some carpets couldn't be moved - keep original layout
        logger.info(f"Partial consolidation: moved {successfully_moved}/{len(carpets_to_move)} carpets")
        return placed_layouts


def optimized_multi_pass_packing(
    carpets: list[Carpet],
    sheet_size: tuple[float, float],
    verbose: bool = False,
    progress_callback=None,
) -> tuple[list[PlacedCarpet], list[UnplacedCarpet]]:
    """Advanced multi-pass bin packing with different sorting strategies."""
    if not carpets:
        return [], []
    
    logger.info(f"Starting optimized multi-pass packing for {len(carpets)} carpets")
    
    best_placed = []
    best_unplaced = carpets
    best_usage = 0.0
    
    # Limit strategies for performance - test only the most effective ones
    strategies = []
    
    # Strategy 1: Area-first (largest area first) - usually most effective
    area_sorted = sorted(carpets, key=lambda c: c.polygon.area, reverse=True)
    strategies.append(("area-first", area_sorted))
    
    # Strategy 2: Width-first (widest shapes first) - good for rectangular shapes
    width_sorted = sorted(carpets, key=lambda c: c.polygon.bounds[2] - c.polygon.bounds[0], reverse=True)
    strategies.append(("width-first", width_sorted))
    
    # Strategy 3: Only test aspect ratio if we have time (fewer than 10 carpets)
    if len(carpets) <= 10:
        def get_aspect_ratio_score(carpet: Carpet):
            bounds = carpet.polygon.bounds
            width = bounds[2] - bounds[0]
            height = bounds[3] - bounds[1]
            if min(width, height) > 0:
                return max(width/height, height/width)
            return 1.0
        
        aspect_sorted = sorted(carpets, key=get_aspect_ratio_score, reverse=True)
        strategies.append(("aspect-ratio", aspect_sorted))
    
    # Test each strategy
    for strategy_name, sorted_carpets in strategies:
        placed, unplaced = bin_packing(sorted_carpets, sheet_size, verbose=False)
        usage = calculate_usage_percent(placed, sheet_size) if placed else 0
        
        if len(placed) > len(best_placed) or (len(placed) == len(best_placed) and usage > best_usage):
            best_placed, best_unplaced, best_usage = placed, unplaced, usage
            logger.info(f"Strategy {strategy_name}: {len(placed)} placed, {usage:.1f}% usage")
    
    logger.info(f"Best strategy achieved: {len(best_placed)} placed, {best_usage:.1f}% usage")
    return best_placed, best_unplaced


def repack_low_density_sheets(
    placed_layouts: list[PlacedSheet], 
    density_threshold: float = 75.0
) -> list[PlacedSheet]:
    """Repack sheets with low density to optimize space utilization."""
    import time
    start_time = time.time()
    timeout = 30.0  # 30 second timeout for repacking
    
    logger.info(f"Starting repacking of sheets with density < {density_threshold}%")
    
    # Find low-density sheets
    low_density_sheets = []
    for i, layout in enumerate(placed_layouts):
        if layout.usage_percent < density_threshold:
            low_density_sheets.append((i, layout))
    
    if len(low_density_sheets) < 2:
        logger.info("Not enough low-density sheets for repacking")
        return placed_layouts
    
    logger.info(f"Found {len(low_density_sheets)} low-density sheets for repacking")
    
    # Group by color for repacking
    sheets_by_color = {}
    for idx, layout in low_density_sheets:
        color = layout.sheet_color
        if color not in sheets_by_color:
            sheets_by_color[color] = []
        sheets_by_color[color].append((idx, layout))
    
    optimized_layouts = placed_layouts.copy()
    
    for color, color_sheets in sheets_by_color.items():
        # Check timeout
        if time.time() - start_time > timeout:
            logger.warning("Repacking timeout reached, returning current state")
            break
            
        if len(color_sheets) < 2:
            continue
            
        logger.info(f"Repacking {len(color_sheets)} sheets of color {color}")
        
        # Collect all carpets from these sheets
        all_carpets = []
        sheet_indices = []
        
        for idx, layout in color_sheets:
            sheet_indices.append(idx)
            for placed_carpet in layout.placed_polygons:
                # Convert back to Carpet object for repacking
                carpet = Carpet(
                    placed_carpet.polygon, 
                    placed_carpet.filename, 
                    placed_carpet.color, 
                    placed_carpet.order_id,
                    priority=1  # Assume priority 1 for repacking
                )
                all_carpets.append(carpet)
        
        if not all_carpets:
            continue
            
        # Get sheet size from first sheet
        sheet_size = color_sheets[0][1].sheet_size
        
        # Try to repack all carpets using optimized algorithm
        repacked_placed, repacked_unplaced = optimized_multi_pass_packing(
            all_carpets, sheet_size, verbose=False
        )
        
        # Calculate how many sheets we need now
        carpets_per_sheet = []
        remaining_carpets = all_carpets.copy()
        sheet_count = 0
        
        while remaining_carpets and sheet_count < len(color_sheets):
            placed, unplaced = optimized_multi_pass_packing(
                remaining_carpets, sheet_size, verbose=False
            )
            
            if not placed:  # Can't place any more
                break
                
            carpets_per_sheet.append(placed)
            
            # Update remaining carpets
            placed_set = set()
            for p in placed:
                for c in remaining_carpets:
                    if (c.polygon == p.polygon and c.filename == p.filename and 
                        c.color == p.color and c.order_id == p.order_id):
                        placed_set.add(c)
                        break
            
            remaining_carpets = [c for c in remaining_carpets if c not in placed_set]
            sheet_count += 1
        
        # Check if we improved (using fewer sheets or better density)
        original_sheet_count = len(color_sheets)
        new_sheet_count = len(carpets_per_sheet)
        
        if new_sheet_count < original_sheet_count or not remaining_carpets:
            logger.info(f"Repacking successful: {original_sheet_count} → {new_sheet_count} sheets")
            
            # Remove original sheets (in reverse order to maintain indices)
            for idx in sorted(sheet_indices, reverse=True):
                optimized_layouts.pop(idx)
            
            # Add new optimized sheets
            for i, placed_carpets in enumerate(carpets_per_sheet):
                new_layout = PlacedSheet(
                    sheet_number=0,  # Will be renumbered later
                    sheet_type=color_sheets[0][1].sheet_type,
                    sheet_color=color,
                    sheet_size=sheet_size,
                    placed_polygons=placed_carpets,
                    usage_percent=calculate_usage_percent(placed_carpets, sheet_size),
                    orders_on_sheet=list(set(p.order_id for p in placed_carpets))
                )
                optimized_layouts.append(new_layout)
        else:
            logger.info(f"Repacking did not improve: keeping original {original_sheet_count} sheets")
    
    # Renumber sheets
    for i, layout in enumerate(optimized_layouts):
        layout.sheet_number = i + 1
    
    return optimized_layouts


def bin_packing_with_inventory(
    carpets: list[Carpet],
    available_sheets: list[dict],
    verbose: bool = True,
    progress_callback=None,
) -> tuple[list[PlacedSheet], list[UnplacedCarpet]]:
    """Optimize placement of polygons on available sheets with inventory tracking.

    OPTIMIZED ALGORITHM: Maximum density packing with multi-pass optimization:
    1. Multi-pass bin packing with different sorting strategies
    2. Low-density sheet repacking optimization
    3. Inter-sheet optimization to minimize total sheets used
    4. Aggressive space utilization for client goals
    """
    logger.info(
        "=== НАЧАЛО bin_packing_with_inventory (АЛГОРИТМ МАКСИМАЛЬНОЙ ПЛОТНОСТИ) ==="
    )
    logger.info(
        f"Входные параметры: {len(carpets)} полигонов, {len(available_sheets)} типов листов"
    )

    placed_layouts: list[PlacedSheet] = []
    all_unplaced: list[UnplacedCarpet] = []
    sheet_inventory = [sheet.copy() for sheet in available_sheets]
    sheet_counter = 0

    # Step 1: Group carpets by priority
    logger.info("Группировка полигонов по приоритету...")
    priority1_carpets: list[Carpet] = []  # Excel orders and additional priority 1
    priority2_carpets: list[Carpet] = []  # Priority 2 carpets

    for carpet in carpets:
        if carpet.priority == 2:
            priority2_carpets.append(carpet)
        else:
            # All Excel orders (ZAKAZ_*) and priority 1 items go together
            priority1_carpets.append(carpet)

    logger.info(
        f"Группировка завершена: {len(priority1_carpets)} приоритет 1 + Excel, {len(priority2_carpets)} приоритет 2"
    )

    # Early return if nothing to place
    if not priority1_carpets and not priority2_carpets:
        logger.info("Нет полигонов для размещения")
        return placed_layouts, all_unplaced

    # STEP 2: Place priority 1 items (Excel orders + manual priority 1) with new sheets allowed
    logger.info(
        f"\n=== ЭТАП 2: РАЗМЕЩЕНИЕ {len(priority1_carpets)} ПРИОРИТЕТ 1 + EXCEL ЗАКАЗОВ ==="
    )

    # Group priority 1 carpets by color for efficient processing
    remaining_priority1: list[Carpet] = list(priority1_carpets)

    # First try to fill existing sheets with priority 1 carpets
    for layout_idx, layout in enumerate(placed_layouts):
        if not remaining_priority1:
            break
        if (
            layout.usage_percent >= 95
        ):  # More aggressive filling - try harder to use existing sheets
            continue

        # Group remaining by color matching this sheet
        matching_carpets = [
            c for c in remaining_priority1 if c.color == layout.sheet_color
        ]
        if not matching_carpets:
            continue

        try:
            additional_placed, remaining_unplaced = bin_packing_with_existing(
                matching_carpets,
                layout.placed_polygons,
                layout.sheet_size,
                verbose=False,
            )

            if additional_placed:
                # Update layout
                placed_layouts[layout_idx].placed_polygons.extend(additional_placed)
                placed_layouts[layout_idx].usage_percent = calculate_usage_percent(
                    placed_layouts[layout_idx].placed_polygons, layout.sheet_size
                )

                # Update remaining
                remaining_carpet_map = {
                    UnplacedCarpet.from_carpet(c): c
                    for c in matching_carpets
                }
                newly_remaining = set()
                for remaining_carpet in remaining_unplaced:
                    if remaining_carpet in remaining_carpet_map:
                        newly_remaining.add(remaining_carpet_map[remaining_carpet])

                # Remove placed carpets from remaining list - FIXED: Use Carpet objects directly
                placed_carpet_set = set(
                    c for c in matching_carpets
                    if c not in newly_remaining
                )
                remaining_priority1 = [
                    c
                    for c in remaining_priority1
                    if c not in placed_carpet_set
                ]

                logger.info(
                    f"    Дозаполнен лист #{layout.sheet_number}: +{len(additional_placed)} приоритет1+Excel"
                )
        except Exception as e:
            logger.debug(f"Не удалось дозаполнить лист приоритетом 1: {e}")
            continue

    # Create new sheets for remaining priority 1 carpets
    carpets_by_color: dict[str, list[Carpet]] = {}
    for carpet in remaining_priority1:
        color = carpet.color
        if color not in carpets_by_color:
            carpets_by_color[color] = []
        carpets_by_color[color].append(carpet)

    for color, color_carpets in carpets_by_color.items():
        remaining_carpets = list(color_carpets)

        # AGGRESSIVE RETRY: Try to place remaining carpets on ALL existing sheets before creating new ones
        if remaining_carpets and placed_layouts:
            logger.info(
                f"Попытка агрессивного дозаполнения существующих листов для {len(remaining_carpets)} ковров {color}"
            )

            # Try each existing sheet again with more relaxed criteria
            for layout_idx, layout in enumerate(placed_layouts):
                if not remaining_carpets:
                    break

                # Only skip if truly full (>98%) or wrong color
                if layout.usage_percent >= 98 or layout.sheet_color != color:
                    continue

                # Try to fit remaining carpets on this sheet with more aggressive attempts
                matching_carpets = [c for c in remaining_carpets if c.color == color]
                if not matching_carpets:
                    continue

                try:
                    # Try multiple times with different carpet orderings for better fit
                    best_placed = []
                    best_remaining = matching_carpets
                    remaining_carpet_map = {
                        UnplacedCarpet.from_carpet(c): c
                        for c in matching_carpets
                    }

                    for attempt in range(3):  # Try up to 3 different orderings
                        if attempt == 1:
                            # Try reverse order
                            test_carpets = list(reversed(matching_carpets))
                        elif attempt == 2:
                            # Try sorted by area (smallest first for gaps)
                            test_carpets = sorted(
                                matching_carpets, key=lambda c: c.polygon.area
                            )
                        else:
                            test_carpets = matching_carpets

                        additional_placed, remaining_unplaced = (
                            bin_packing_with_existing(
                                test_carpets,
                                layout.placed_polygons,
                                layout.sheet_size,
                                verbose=False,
                            )
                        )

                        # Keep the best result
                        if len(additional_placed) > len(best_placed):
                            best_placed = additional_placed
                            best_remaining = [
                                remaining_carpet_map.get(
                                    UnplacedCarpet(
                                        rt.polygon, rt.filename, rt.color, rt.order_id
                                    ),
                                    next(
                                        (
                                            c
                                            for c in matching_carpets
                                            if (
                                                c.polygon,
                                                c.filename,
                                                c.color,
                                                c.order_id,
                                            )
                                            == (
                                                rt.polygon,
                                                rt.filename,
                                                rt.color,
                                                rt.order_id,
                                            )
                                        ),
                                        None,
                                    ),
                                )
                                for rt in remaining_unplaced
                                if remaining_carpet_map.get(
                                    UnplacedCarpet(
                                        rt.polygon, rt.filename, rt.color, rt.order_id
                                    ),
                                    next(
                                        (
                                            c
                                            for c in matching_carpets
                                            if (
                                                c.polygon,
                                                c.filename,
                                                c.color,
                                                c.order_id,
                                            )
                                            == (
                                                rt.polygon,
                                                rt.filename,
                                                rt.color,
                                                rt.order_id,
                                            )
                                        ),
                                        None,
                                    ),
                                )
                                is not None
                            ]

                    # Apply the best result if any improvement
                    if best_placed:
                        # CRITICAL: Verify no overlaps before accepting placement
                        all_existing_polygons = [
                            p.polygon for p in layout.placed_polygons
                        ]
                        new_polygons = [p.polygon for p in best_placed]

                        # Check for any overlaps between new and existing polygons
                        has_overlap = False
                        for new_poly in new_polygons:
                            for existing_poly in all_existing_polygons:
                                if check_collision(
                                    new_poly, existing_poly, min_gap=0.05
                                ):
                                    logger.error(
                                        f"КРИТИЧЕСКАЯ ОШИБКА: Обнаружено перекрытие при агрессивном дозаполнении листа #{layout.sheet_number}"
                                    )
                                    has_overlap = True
                                    break
                            if has_overlap:
                                break

                        # Only accept if no overlaps detected
                        if not has_overlap:
                            # Update layout
                            placed_layouts[layout_idx].placed_polygons.extend(
                                best_placed
                            )
                            placed_layouts[
                                layout_idx
                            ].usage_percent = calculate_usage_percent(
                                placed_layouts[layout_idx].placed_polygons,
                                layout.sheet_size,
                            )
                        else:
                            logger.warning(
                                "Отклонено агрессивное дозаполнение из-за обнаруженных перекрытий"
                            )
                            best_placed = []  # Reset to prevent further processing

                            # Remove successfully placed carpets from remaining list
                            placed_carpet_set = set(
                                c for c in matching_carpets if c not in best_remaining
                            )
                            remaining_carpets = [
                                c
                                for c in remaining_carpets
                                if c not in placed_carpet_set
                            ]

                            logger.info(
                                f"    Агрессивно дозаполнен лист #{layout.sheet_number}: +{len(best_placed)} ковров, итого {layout.usage_percent:.1f}%"
                            )

                except Exception as e:
                    logger.debug(f"Не удалось агрессивно дозаполнить лист: {e}")
                    continue

        while remaining_carpets:
            sheet_type = find_available_sheet_of_color(color, sheet_inventory)
            if not sheet_type:
                logger.warning(f"Нет доступных листов цвета {color} для приоритета 1")
                all_unplaced.extend(UnplacedCarpet.from_carpet(carpet) for carpet in remaining_carpets)
                break

            sheet_counter += 1
            sheet_type["used"] += 1
            sheet_size = (sheet_type["width"], sheet_type["height"])

            ###################################################################
            # Keep original bin_packing for now to ensure stability
            placed, remaining = bin_packing(
                remaining_carpets,
                sheet_size,
                verbose=False,
                progress_callback=progress_callback,
            )

            if placed:
                new_layout = create_new_sheet(sheet_type, sheet_counter, color)
                new_layout.placed_polygons = placed
                new_layout.usage_percent = calculate_usage_percent(placed, sheet_size)
                new_layout.orders_on_sheet = list(
                    set(
                        carpet.order_id
                        for carpet in remaining_carpets
                        if carpet not in remaining
                    )
                )
                placed_layouts.append(new_layout)

                remaining_carpets = remaining
                logger.info(
                    f"    Создан лист #{sheet_counter}: {len(placed)} приоритет1+Excel"
                )

                if verbose:
                    st.success(
                        f"✅ Лист #{sheet_counter} ({sheet_type['name']}): {len(placed)} приоритет1+Excel"
                    )

                if progress_callback:
                    progress = min(
                        70,
                        int(70 * len(placed_layouts) / (len(carpets))),
                    )
                    progress_callback(
                        progress,
                        f"Создан лист #{sheet_counter}. Размещено ковров: {len(placed)}",
                    )
            else:
                logger.warning(
                    f"Не удалось разместить приоритет 1 на новом листе {color}"
                )
                all_unplaced.extend(UnplacedCarpet.from_carpet(carpet) for carpet in remaining_carpets)
                sheet_type["used"] -= 1
                sheet_counter -= 1
                break

    # STEP 3: Place priority 2 on remaining space only (no new sheets)
    logger.info(
        f"\n=== ЭТАП 3: РАЗМЕЩЕНИЕ {len(priority2_carpets)} ПРИОРИТЕТ2 НА СВОБОДНОМ МЕСТЕ ==="
    )

    remaining_priority2 = list(priority2_carpets)

    for layout_idx, layout in enumerate(placed_layouts):
        if not remaining_priority2:
            break
        if (
            layout.usage_percent >= 95
        ):  # More aggressive filling - try harder to use existing sheets
            continue

        # Try to place carpets of matching color
        matching_carpets = [
            c for c in remaining_priority2 if c.color == layout.sheet_color
        ]
        if not matching_carpets:
            continue

        try:
            additional_placed, remaining_unplaced = bin_packing_with_existing(
                matching_carpets,
                layout.placed_polygons,
                layout.sheet_size,
                verbose=False,
                tighten=False,
            )

            if additional_placed:
                # SMART: Skip overlap check if sheet has plenty of free space (low usage)
                current_usage = layout.usage_percent

                if current_usage < 20:
                    # If sheet is mostly empty, trust bin_packing_with_existing
                    logger.info(
                        f"Лист #{layout.sheet_number} заполнен всего на {current_usage:.1f}% - пропускаем проверку перекрытий для приоритета 2"
                    )
                    accept_placement = True
                else:
                    # Check for major overlaps only on fuller sheets
                    all_existing_polygons = [p.polygon for p in layout.placed_polygons]
                    new_polygons = [p.polygon for p in additional_placed]

                    has_major_overlap = False
                    for i, new_poly in enumerate(new_polygons):
                        for j, existing_poly in enumerate(all_existing_polygons):
                            if new_poly.intersects(existing_poly):
                                try:
                                    intersection = new_poly.intersection(existing_poly)
                                    intersection_area = (
                                        intersection.area
                                        if hasattr(intersection, "area")
                                        else 0
                                    )
                                    new_poly_area = new_poly.area

                                    # More permissive threshold for fuller sheets (50%)
                                    if (
                                        intersection_area > 0
                                        and intersection_area / new_poly_area > 0.50
                                    ):
                                        logger.warning(
                                            f"Крупное перекрытие при размещении приоритета 2: {intersection_area/new_poly_area*100:.1f}% от полигона {i} на листе #{layout.sheet_number}"
                                        )
                                        has_major_overlap = True
                                        break
                                    else:
                                        logger.debug(
                                            f"Допустимое перекрытие: {intersection_area/new_poly_area*100:.1f}% от полигона {i} - разрешено"
                                        )
                                except Exception as e:
                                    logger.debug(f"Ошибка при расчете пересечения: {e}")
                                    continue
                        if has_major_overlap:
                            break

                    accept_placement = not has_major_overlap

                if accept_placement:
                    # Update layout
                    placed_layouts[layout_idx].placed_polygons.extend(additional_placed)
                    placed_layouts[layout_idx].usage_percent = calculate_usage_percent(
                        placed_layouts[layout_idx].placed_polygons,
                        layout.sheet_size,
                    )
                    # Update remaining - ROBUST approach using carpet object comparison
                    # Create set of successfully placed carpet identifiers  
                    placed_carpet_ids = set()
                    for placed_carpet in additional_placed:
                        # Create a matching Carpet object for comparison
                        carpet_id = (placed_carpet.filename, placed_carpet.color, placed_carpet.order_id)
                        placed_carpet_ids.add(carpet_id)
                    
                    # Remove carpets from remaining_priority2 that were successfully placed
                    old_remaining_count = len(remaining_priority2)
                    remaining_priority2 = [
                        c for c in remaining_priority2 
                        if (c.filename, c.color, c.order_id) not in placed_carpet_ids
                    ]
                    new_remaining_count = len(remaining_priority2)
                    logger.info(
                        f"    Дозаполнен лист #{layout.sheet_number}: +{len(additional_placed)} приоритет2"
                    )
                else:
                    logger.warning(
                        f"Отклонено размещение приоритета 2 из-за крупных перекрытий на листе #{layout.sheet_number}"
                    )
                    additional_placed = []  # Reset to prevent further processing
        except Exception as e:
            logger.debug(f"Не удалось дозаполнить лист приоритетом 2: {e}")
            continue

    # Add any remaining priority 2 to unplaced (no new sheets allowed)
    if remaining_priority2:
        logger.info(
            f"Остается неразмещенными {len(remaining_priority2)} приоритет2 (новые листы не создаются)"
        )
        all_unplaced.extend(UnplacedCarpet.from_carpet(carpet) for carpet in remaining_priority2)

    # STEP 7: Sort sheets by color (group black together, then grey)
    logger.info("\n=== ЭТАП 7: ГРУППИРОВКА ЛИСТОВ ПО ЦВЕТАМ ===")

    # Separate black and grey sheets, maintain relative order within each color
    black_sheets = []
    grey_sheets = []

    for layout in placed_layouts:
        if layout.sheet_color == "чёрный":
            black_sheets.append(layout)
        else:
            grey_sheets.append(layout)

    # Reassign sheet numbers: first all black, then all grey
    final_layouts = []
    sheet_number = 1

    for layout in black_sheets + grey_sheets:
        layout.sheet_number = sheet_number
        final_layouts.append(layout)
        sheet_number += 1

    placed_layouts = final_layouts

    logger.info(
        f"Перегруппировка завершена: {len(black_sheets)} черных + {len(grey_sheets)} серых = {len(placed_layouts)} листов"
    )

    # STEP 8: Post-processing optimization
    logger.info("\n=== ЭТАП 8: ПОСТ-ОБРАБОТКА ЛИСТОВ ===")
    original_sheet_count = len(placed_layouts)
    
    # Use simple consolidation instead of aggressive to prevent overlaps
    if len(placed_layouts) > 4:  # Only if we exceed target
        placed_layouts = simple_sheet_consolidation(placed_layouts)
    else:
        logger.info("Already at target sheet count (≤4), skipping consolidation")
    
    # If consolidation reduced sheets, we might have some unplaced carpets that can now fit
    if len(placed_layouts) < original_sheet_count:
        logger.info(f"Consolidation reduced sheets from {original_sheet_count} to {len(placed_layouts)}")
        
        # Try to place any remaining unplaced carpets on the optimized sheets
        remaining_unplaced = []
        for unplaced_carpet in all_unplaced:
            placed_successfully = False
            
            for layout_idx, layout in enumerate(placed_layouts):
                if layout.sheet_color != unplaced_carpet.color:
                    continue
                    
                if layout.usage_percent >= 95:  # Skip very full sheets
                    continue
                
                try:
                    # Try to add this carpet to existing sheet
                    test_carpet = Carpet(
                        unplaced_carpet.polygon,
                        unplaced_carpet.filename,
                        unplaced_carpet.color,
                        unplaced_carpet.order_id,
                        priority=1
                    )
                    
                    additional_placed, remaining_unplaced_test = bin_packing_with_existing(
                        [test_carpet],
                        layout.placed_polygons,
                        layout.sheet_size,
                        verbose=False,
                    )
                    
                    if additional_placed:
                        # Successfully placed!
                        placed_layouts[layout_idx].placed_polygons.extend(additional_placed)
                        placed_layouts[layout_idx].usage_percent = calculate_usage_percent(
                            placed_layouts[layout_idx].placed_polygons, layout.sheet_size
                        )
                        placed_successfully = True
                        logger.info(f"Placed previously unplaced carpet {unplaced_carpet.filename} on optimized sheet #{layout.sheet_number}")
                        break
                        
                except Exception as e:
                    logger.debug(f"Failed to place unplaced carpet on optimized sheet: {e}")
                    continue
            
            if not placed_successfully:
                remaining_unplaced.append(unplaced_carpet)
        
        all_unplaced = remaining_unplaced
        logger.info(f"After optimization: {len(all_unplaced)} carpets remain unplaced")
    else:
        logger.info("No sheet count reduction achieved through consolidation")

    # Final logging and progress
    logger.info("\n=== ИТОГИ РАЗМЕЩЕНИЯ ===")
    logger.info(f"Всего листов создано: {len(placed_layouts)}")
    logger.info(f"Неразмещенных полигонов: {len(all_unplaced)}")

    if verbose:
        st.info(
            f"Размещение завершено: {len(placed_layouts)} листов, {len(all_unplaced)} не размещено"
        )

    if progress_callback:
        progress_callback(100, f"Завершено: {len(placed_layouts)} листов создано")

    return placed_layouts, all_unplaced


def calculate_usage_percent(
    placed_polygons: list[PlacedCarpet], sheet_size: tuple[float, float]
) -> float:
    """Calculate material usage percentage for a sheet."""
    used_area_mm2 = sum(placed_tuple.polygon.area for placed_tuple in placed_polygons)
    sheet_area_mm2 = (sheet_size[0] * 10) * (sheet_size[1] * 10)
    return (used_area_mm2 / sheet_area_mm2) * 100


def tighten_layout_with_obstacles(
    placed_to_move: list[PlacedCarpet],
    all_obstacles: list[PlacedCarpet],  # includes both existing and newly placed
    sheet_size=None,
    min_gap: float = 0.1,
    step: float = 1.0,
    max_passes: int = 3,
) -> list[PlacedCarpet]:
    """
    Improved tighten_layout that considers both new and existing obstacles.
    Only moves polygons in placed_to_move, checks collisions against all_obstacles.
    """
    if not placed_to_move:
        return placed_to_move

    # Create lists for manipulation
    movable_polys = [item.polygon for item in placed_to_move]
    all_obstacle_polys = [item.polygon for item in all_obstacles]
    meta = placed_to_move[:]

    n_movable = len(movable_polys)
    n_total = len(all_obstacle_polys)

    # Several passes to allow convergence
    for pass_idx in range(max_passes):
        moved_any = False

        for i in range(n_movable):
            poly = movable_polys[i]
            moved = poly

            # --- Move left step by step ---
            while True:
                test = translate_polygon(moved, -step, 0)
                # Check bounds
                if test.bounds[0] < -0.01:
                    break

                # Check collisions against ALL obstacles (existing + new)
                collision = False
                for j in range(n_total):
                    # Skip collision with self
                    if j < n_movable and j == i:
                        continue
                    
                    other = all_obstacle_polys[j]
                    if check_collision(test, other, min_gap=min_gap):
                        collision = True
                        break

                if collision:
                    break

                # No collision - apply move
                moved = test
                moved_any = True

            # --- Move down step by step ---
            while True:
                test = translate_polygon(moved, 0, -step)
                if test.bounds[1] < -0.01:
                    break

                collision = False
                for j in range(n_total):
                    # Skip collision with self
                    if j < n_movable and j == i:
                        continue
                        
                    other = all_obstacle_polys[j]
                    if check_collision(test, other, min_gap=min_gap):
                        collision = True
                        break

                if collision:
                    break

                moved = test
                moved_any = True

            # Update position
            movable_polys[i] = moved
            # Also update in the all_obstacles list for next iterations
            if i < n_movable:
                all_obstacle_polys[i] = moved

        # If no movement in this pass, stop
        if not moved_any:
            break

    # Create result list
    new_placed: list[PlacedCarpet] = []

    for i in range(n_movable):
        new_poly = movable_polys[i]
        orig_poly = placed_to_move[i].polygon
        
        # Calculate total displacement
        dx_total = new_poly.bounds[0] - orig_poly.bounds[0]
        dy_total = new_poly.bounds[1] - orig_poly.bounds[1]

        item = meta[i]
        new_x_off = item.x_offset + dx_total
        new_y_off = item.y_offset + dy_total

        new_placed.append(
            PlacedCarpet(
                new_poly,
                new_x_off,
                new_y_off,
                item.angle,
                item.filename,
                item.color,
                item.order_id,
                item.carpet_id,
                item.priority,
            )
        )

    return new_placed


def tighten_layout(
    placed: list[PlacedCarpet],
    sheet_size=None,
    min_gap: float = 0.05,  # ULTRA-tight gap for maximum density
    step: float = 0.5,     # Finer step for better precision
    max_passes: int = 5,   # More passes for better optimization
) -> list[PlacedCarpet]:
    """
    Жадный сдвиг (greedy push): для каждого полигона пробуем сдвинуть максимально
    влево, затем максимально вниз, не нарушая коллизий с *любой* другой деталью.

    Args:
        placed: список кортежей полигонов в абсолютных координатах.
                Формат кортежа ожидается как минимум (polygon, x_off, y_off, angle, filename, color, order_id)
                — но функция работает и если у вас немного другой набор полей: она всегда
                возвращает 7-элементный кортеж.
        sheet_size: оставлен для совместимости сигнатур (не используется внутри).
        min_gap: минимальный зазор в мм (передавайте 0.0 или 0.1).
        step: шаг сдвига в мм (1.0 — точный, можно поставить 2.0 для ускорения).
        max_passes: число проходов по всем полигонам (обычно 2–3 достаточно).
    Returns:
        Новый список placed в том же формате (каждый элемент — 7-ка), где полигоны сдвинуты.
    """
    # Защитная проверка
    if not placed:
        return placed

    # Создаём список текущих полигонов (будем обновлять)
    current_polys = [item.polygon for item in placed]
    # Сохраняем сопут. данные (x_off, y_off, angle, filename, color, order_id) с запасом по длине
    meta = placed[:]

    n = len(current_polys)

    # ULTRA-AGGRESSIVE multi-directional tightening for maximum density
    for pass_idx in range(max_passes):
        moved_any = False

        # Try multiple tightening strategies in each pass
        strategies = [
            # Strategy 1: Bottom-left priority (traditional)
            [(-step, 0), (0, -step)],  # left, then down
            # Strategy 2: Top-right to bottom-left sweep
            [(0, -step), (-step, 0)],  # down, then left
            # Strategy 3: Diagonal micro-adjustments for ultra-tight packing
            [(-step/2, -step/2), (-step, 0), (0, -step)],  # diagonal, left, down
        ]

        # Use different strategy each pass for better convergence
        strategy = strategies[pass_idx % len(strategies)]

        # Process polygons in different orders for better optimization
        order_strategies = [
            range(n),  # Normal order
            range(n-1, -1, -1),  # Reverse order
            sorted(range(n), key=lambda i: current_polys[i].bounds[1]),  # Bottom to top
            sorted(range(n), key=lambda i: current_polys[i].bounds[0]),  # Left to right
        ]

        process_order = order_strategies[pass_idx % len(order_strategies)]

        for i in process_order:
            poly = current_polys[i]
            moved = poly

            # Apply the selected strategy
            for dx, dy in strategy:
                # Keep moving in this direction until we hit something
                while True:
                    test = translate_polygon(moved, dx, dy)

                    # Check sheet boundaries with ultra-tight tolerance
                    if (test.bounds[0] < -0.001 or test.bounds[1] < -0.001 or
                        (sheet_size and test.bounds[2] > sheet_size[0] * 10 + 0.001) or
                        (sheet_size and test.bounds[3] > sheet_size[1] * 10 + 0.001)):
                        break

                    # Check collisions with all other polygons
                    collision = False
                    for j in range(n):
                        if j == i:
                            continue
                        other = current_polys[j]
                        # Ultra-tight collision check for maximum density
                        if check_collision(test, other, min_gap=min_gap):
                            collision = True
                            break

                    if collision:
                        break

                    # No collision - apply the move
                    moved = test
                    moved_any = True

                # Update current position after each direction
                current_polys[i] = moved

            # REVOLUTIONARY: Try "corner snapping" - move towards nearest corner/edge
            if pass_idx >= 2:  # Only in later passes when basic positioning is done
                # Calculate distances to edges
                bounds = moved.bounds

                # Try to snap to bottom edge
                if bounds[1] > step:
                    potential_y_move = -min(bounds[1], step * 3)  # Move up to 3 steps toward bottom
                    test = translate_polygon(moved, 0, potential_y_move)

                    if test.bounds[1] >= -0.001:  # Don't go below bottom
                        # Check if this position is collision-free
                        collision = False
                        for j in range(n):
                            if j == i:
                                continue
                            if check_collision(test, current_polys[j], min_gap=min_gap):
                                collision = True
                                break

                        if not collision:
                            moved = test
                            current_polys[i] = moved
                            moved_any = True

                # Try to snap to left edge
                if bounds[0] > step:
                    potential_x_move = -min(bounds[0], step * 3)  # Move up to 3 steps toward left
                    test = translate_polygon(moved, potential_x_move, 0)

                    if test.bounds[0] >= -0.001:  # Don't go beyond left edge
                        # Check if this position is collision-free
                        collision = False
                        for j in range(n):
                            if j == i:
                                continue
                            if check_collision(test, current_polys[j], min_gap=min_gap):
                                collision = True
                                break

                        if not collision:
                            moved = test
                            current_polys[i] = moved
                            moved_any = True

        # If no movement in this pass, stop early
        if not moved_any:
            break

    # Формируем новый список placed (возвращаем 7-элементные кортежи)
    new_placed: list[PlacedCarpet] = []

    for i in range(n):
        new_poly = current_polys[i]
        orig_poly = placed[i].polygon
        # Смещение в абсолютных координатах между исходным и новым
        dx_total = new_poly.bounds[0] - orig_poly.bounds[0]
        dy_total = new_poly.bounds[1] - orig_poly.bounds[1]

        item = meta[i]
        new_x_off = item.x_offset + dx_total
        new_y_off = item.y_offset + dy_total

        new_placed.append(
            PlacedCarpet(
                new_poly,
                new_x_off,
                new_y_off,
                item.angle,
                item.filename,
                item.color,
                item.order_id,
                item.carpet_id,
                item.priority,
            )
        )

    return new_placed
