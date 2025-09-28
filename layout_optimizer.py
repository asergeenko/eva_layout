"""Helper functions for EVA mat nesting optimization."""

# Version for cache busting
__version__ = "1.5.0"

import numpy as np
import time

from shapely.geometry import Polygon, Point
import streamlit as st
import logging

from carpet import Carpet, PlacedCarpet, UnplacedCarpet, PlacedSheet
from geometry_utils import translate_polygon, rotate_polygon

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

# Глобальные кэши для оптимизации поворотов ковров
_rotation_cache: dict[
    int, dict[int, Polygon]
] = {}  # carpet_id -> {angle: rotated_polygon}
_original_polygons: dict[int, Polygon] = {}  # carpet_id -> original_polygon


def clear_optimization_caches():
    """Очистить все кэши оптимизации."""
    global _rotation_cache, _original_polygons, _trapped_space_cache, _spatial_index
    _rotation_cache.clear()
    _original_polygons.clear()


def cache_original_polygons(carpets: list[Carpet]) -> None:
    """Кэшировать оригинальные полигоны ДО любых трансформаций."""
    logger.info(
        f"🏁 Начинаем кэширование оригинальных полигонов для {len(carpets)} ковров"
    )
    for carpet in carpets:
        carpet_id = carpet.carpet_id
        if carpet_id not in _original_polygons:
            # Создаем копию полигона, чтобы избежать проблем со ссылками
            original_bounds = carpet.polygon.bounds
            _original_polygons[carpet_id] = Polygon(carpet.polygon.exterior.coords)
            logger.info(
                f"💾 Сохранен оригинальный полигон для carpet={carpet}, filename={carpet.filename}, bounds={original_bounds}"
            )
        else:
            logger.info(f"⚠️ Полигон для carpet={carpet} уже в кэше - пропускаем")

    logger.info(
        f"✅ Кэширование завершено, всего оригиналов в кэше: {len(_original_polygons)}"
    )


def get_original_polygon(carpet_id: int) -> Polygon | None:
    if carpet_id in _original_polygons:
        return _original_polygons[carpet_id]
    return None


def get_cached_rotation(
    carpet: Carpet | PlacedCarpet | UnplacedCarpet, angle: int
) -> Polygon:
    """Получить кэшированный поворот полигона от ОРИГИНАЛЬНОЙ геометрии."""
    # Проверяем, что у нас есть оригинальный полигон
    carpet_id = carpet.carpet_id
    if carpet_id not in _original_polygons:
        # ОШИБКА: оригинальный полигон должен быть закэширован заранее!
        logger.warning(f"❌ Оригинальный полигон для carpet={carpet} не найден в кэше!")
        # Fallback: используем текущий полигон (может быть уже трансформированным)
        _original_polygons[carpet_id] = Polygon(carpet.polygon.exterior.coords)

    if carpet not in _rotation_cache:
        _rotation_cache[carpet_id] = {}

    if angle not in _rotation_cache[carpet_id]:
        # Вычисляем поворот от ОРИГИНАЛЬНОГО полигона
        original_polygon = _original_polygons[carpet_id]
        rotated = (
            rotate_polygon(original_polygon, angle) if angle != 0 else original_polygon
        )
        _rotation_cache[carpet_id][angle] = rotated

    return _rotation_cache[carpet_id][angle]


def apply_tetris_gravity(
    placed_carpets: list[PlacedCarpet], sheet_width_mm: float, sheet_height_mm: float
) -> list[PlacedCarpet]:
    """
    ИСПРАВЛЕННЫЙ ТЕТРИС-ДВИЖОК: Применяет гравитацию осторожно, не ломая существующее размещение.
    Ковры падают вниз только если это безопасно и улучшает размещение.
    """
    if not placed_carpets or len(placed_carpets) < 2:
        return placed_carpets

    # Создаем копии для безопасности
    gravity_carpets = []
    for carpet in placed_carpets:
        gravity_carpets.append(
            PlacedCarpet(
                polygon=carpet.polygon,
                x_offset=carpet.x_offset,
                y_offset=carpet.y_offset,
                angle=carpet.angle,
                filename=carpet.filename,
                color=carpet.color,
                order_id=carpet.order_id,
                carpet_id=carpet.carpet_id,
                priority=carpet.priority,
            )
        )

    # Сортируем по высоте (сверху вниз) - верхние ковры пытаемся опустить
    gravity_carpets.sort(
        key=lambda c: c.polygon.bounds[3], reverse=True
    )  # По верхнему краю

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


def apply_tetris_right_compaction(
    placed_carpets: list[PlacedCarpet], sheet_width_mm: float, sheet_height_mm: float
) -> list[PlacedCarpet]:
    """
    НОВАЯ TETRIS-ФУНКЦИЯ: Сжимает ковры к правому краю для освобождения пространства.
    Это позволяет верхним коврам упасть вниз, как в настоящем Тетрисе.
    """
    if not placed_carpets or len(placed_carpets) < 2:
        return placed_carpets

    # Создаем копии для безопасности
    compacted_carpets = []
    for carpet in placed_carpets:
        compacted_carpets.append(
            PlacedCarpet(
                polygon=carpet.polygon,
                x_offset=carpet.x_offset,
                y_offset=carpet.y_offset,
                angle=carpet.angle,
                filename=carpet.filename,
                color=carpet.color,
                order_id=carpet.order_id,
                carpet_id=carpet.carpet_id,
                priority=carpet.priority,
            )
        )

    # Сортируем по расстоянию от правого края (дальние сначала)
    compacted_carpets.sort(
        key=lambda c: sheet_width_mm - c.polygon.bounds[2], reverse=True
    )

    movements_made = 0
    max_movements = min(5, len(compacted_carpets))  # Ограничиваем количество движений

    # Применяем сжатие к правому краю
    for i, carpet in enumerate(compacted_carpets):
        if movements_made >= max_movements:
            break

        # Препятствия = все остальные ковры
        obstacles = [
            other.polygon for j, other in enumerate(compacted_carpets) if j != i
        ]

        # Текущие границы ковра
        current_bounds = carpet.polygon.bounds
        current_right = current_bounds[2]
        carpet_width = current_bounds[2] - current_bounds[0]

        # Максимально возможный сдвиг вправо
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
            if (
                test_bounds[0] < 0
                or test_bounds[1] < 0
                or test_bounds[2] > sheet_width_mm
                or test_bounds[3] > sheet_height_mm
            ):
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
                priority=carpet.priority,
            )
            movements_made += 1

    return compacted_carpets


def calculate_trapped_space(
    placed_carpets: list[PlacedCarpet], sheet_width_mm: float, sheet_height_mm: float
) -> float:
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
    if hasattr(free_space, "geoms"):  # MultiPolygon
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
            trapped_area += poly.area * (
                1.2 - rectangularity
            )  # Увеличенный штраф за неправильность

        # Дополнительный штраф за области далеко от краев листа
        center_x = (bounds[0] + bounds[2]) / 2
        center_y = (bounds[1] + bounds[3]) / 2

        distance_from_edges = min(
            center_x,  # От левого края
            sheet_width_mm - center_x,  # От правого края
            center_y,  # От нижнего края
            sheet_height_mm - center_y,  # От верхнего края
        )

        if distance_from_edges > 200:  # Больше 20см от краев
            isolation_penalty = (distance_from_edges - 200) / 100
            trapped_area += poly.area * isolation_penalty * 0.1

    return trapped_area


def analyze_placement_blocking(
    placed_carpets: list[PlacedCarpet], sheet_width_mm: float, sheet_height_mm: float
) -> dict:
    """
    🧠 АНАЛИЗ БЛОКИРОВКИ: Анализирует как размещенные ковры блокируют пространство для будущих ковров.
    Возвращает рекомендации по улучшению размещения.
    """
    analysis = {
        "total_trapped_area": 0,
        "blocking_carpets": [],  # Ковры, создающие много блокировки
        "improvement_suggestions": [],
    }

    if len(placed_carpets) < 2:
        return analysis

    # Базовая заперность
    base_trapped = calculate_trapped_space(
        placed_carpets, sheet_width_mm, sheet_height_mm
    )
    analysis["total_trapped_area"] = base_trapped

    # Анализируем вклад каждого ковра в блокировку
    for i, carpet in enumerate(placed_carpets):
        # Убираем этот ковер и смотрим, как изменится заперность
        temp_placed = [c for j, c in enumerate(placed_carpets) if j != i]
        trapped_without = calculate_trapped_space(
            temp_placed, sheet_width_mm, sheet_height_mm
        )

        blocking_contribution = base_trapped - trapped_without

        if (
            blocking_contribution > 1000
        ):  # REDUCED: Больше 100 см² блокировки (еще более агрессивный порог)
            analysis["blocking_carpets"].append(
                {
                    "carpet": carpet,
                    "blocking_amount": blocking_contribution,
                    "carpet_index": i,
                }
            )

            # Предлагаем попробовать поворот
            analysis["improvement_suggestions"].append(
                {
                    "type": "rotation",
                    "carpet_index": i,
                    "reason": f"Блокирует {blocking_contribution/100:.0f} см² пространства",
                }
            )

    return analysis


def post_placement_optimize_aggressive(
    placed_carpets: list[PlacedCarpet],
    sheet_width_mm: float,
    sheet_height_mm: float,
    remaining_carpets: list[Carpet] = None,
) -> list[PlacedCarpet]:
    """
    🚀 АГРЕССИВНАЯ POST-PLACEMENT OPTIMIZATION: Полностью переразмещает проблемные ковры.
    Не просто поворачивает на месте, а находит НОВЫЕ позиции с учетом будущих ковров.
    """
    if len(placed_carpets) < 2:
        return placed_carpets

    # Анализируем проблемы
    blocking_analysis = analyze_placement_blocking(
        placed_carpets, sheet_width_mm, sheet_height_mm
    )

    if not blocking_analysis["blocking_carpets"]:
        return placed_carpets

    # Сортируем по степени блокировки (худшие первые)
    blocking_carpets = sorted(
        blocking_analysis["blocking_carpets"],
        key=lambda x: x["blocking_amount"],
        reverse=True,
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
            priority=c.priority,
        )
        for c in placed_carpets
    ]

    improvements_made = 0
    max_improvements = 5  # INCREASED: Агрессивно переразмещаем максимум 5 худших ковров

    for blocker_info in blocking_carpets[:max_improvements]:
        carpet_idx = blocker_info["carpet_index"]
        current_carpet = optimized_carpets[carpet_idx]

        print(
            f"🔄 Переразмещаем {current_carpet.filename} (блокирует {blocker_info['blocking_amount']/100:.0f} см²)"
        )

        # Восстанавливаем исходную форму ковра
        original_polygon = rotate_polygon(current_carpet.polygon, -current_carpet.angle)

        # Получаем все остальные ковры как препятствия
        obstacles = [
            c.polygon for i, c in enumerate(optimized_carpets) if i != carpet_idx
        ]

        current_trapped = calculate_trapped_space(
            optimized_carpets, sheet_width_mm, sheet_height_mm
        )
        best_improvement = 0
        best_placement = None

        # АГРЕССИВНАЯ СТРАТЕГИЯ: Пробуем ВСЕ ориентации + ВСЕ позиции
        for test_angle in [0, 90, 180, 270]:
            # angle = test_angle - current_carpet.angle
            # if angle < 0:
            #    angle += 360
            # rotated_polygon = get_cached_rotation(current_carpet, angle)
            rotated_polygon = (
                rotate_polygon(original_polygon, test_angle)
                if test_angle != 0
                else original_polygon
            )

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
                    if len(test_positions) > 15:  # Уменьшили лимит для ускорения (было 20)
                        break
                if len(test_positions) > 15:
                    break

            # Тестируем каждую позицию
            for test_x, test_y in test_positions:
                # Создаем тестовый полигон
                test_polygon = translate_polygon(
                    rotated_polygon, test_x - rot_bounds[0], test_y - rot_bounds[1]
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
                        priority=current_carpet.priority,
                    )

                    test_trapped = calculate_trapped_space(
                        test_carpets, sheet_width_mm, sheet_height_mm
                    )
                    improvement = current_trapped - test_trapped

                    if improvement > best_improvement:
                        best_improvement = improvement
                        best_placement = {
                            "polygon": test_polygon,
                            "x_offset": test_x - rot_bounds[0],
                            "y_offset": test_y - rot_bounds[1],
                            "angle": test_angle,
                        }

        # Применяем лучшее размещение если оно значимо лучше
        if (
            best_placement and best_improvement > 100
        ):  # REDUCED: Минимум 10 см² улучшения (более агрессивно)
            print(
                f"✅ Найдено лучшее размещение: освобождает {best_improvement/100:.0f} см²"
            )

            optimized_carpets[carpet_idx] = PlacedCarpet(
                polygon=best_placement["polygon"],
                x_offset=best_placement["x_offset"],
                y_offset=best_placement["y_offset"],
                angle=best_placement["angle"],
                filename=current_carpet.filename,
                color=current_carpet.color,
                order_id=current_carpet.order_id,
                carpet_id=current_carpet.carpet_id,
                priority=current_carpet.priority,
            )
            improvements_made += 1
        else:
            print(
                f"❌ Лучшее размещение не найдено (улучшение: {best_improvement/100:.0f} см²)"
            )

    if improvements_made > 0:
        print(f"🎊 Агрессивная оптимизация улучшила {improvements_made} ковров!")

    return optimized_carpets


def post_placement_optimize(
    placed_carpets: list[PlacedCarpet], sheet_width_mm: float, sheet_height_mm: float
) -> list[PlacedCarpet]:
    """
    🚀 POST-PLACEMENT OPTIMIZATION: Революционная система переразмещения.
    После размещения анализирует и улучшает позиции ковров для минимизации заперных зон.
    """
    if len(placed_carpets) < 2:
        return placed_carpets

    # Анализируем текущую блокировку
    blocking_analysis = analyze_placement_blocking(
        placed_carpets, sheet_width_mm, sheet_height_mm
    )

    if not blocking_analysis["blocking_carpets"]:
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
            priority=c.priority,
        )
        for c in placed_carpets
    ]

    improvements_made = 0
    max_improvements = min(
        5, len(blocking_analysis["blocking_carpets"])
    )  # Увеличили лимит улучшений

    # Оптимизируем самые проблемные ковры
    for suggestion in blocking_analysis["improvement_suggestions"][:max_improvements]:
        if suggestion["type"] == "rotation":
            carpet_idx = suggestion["carpet_index"]
            current_carpet = optimized_carpets[carpet_idx]

            # Пробуем все возможные повороты
            current_trapped = calculate_trapped_space(
                optimized_carpets, sheet_width_mm, sheet_height_mm
            )
            best_improvement = 0
            best_rotation = None

            for test_angle in [0, 90, 180, 270]:
                if test_angle == current_carpet.angle:
                    continue

                original_polygon = rotate_polygon(
                    current_carpet.polygon, -current_carpet.angle
                )  # Возвращаем к 0°
                rotated_polygon = rotate_polygon(original_polygon, test_angle)

                # Создаем тестовый ковер с новым углом
                # angle = test_angle - current_carpet.angle
                # if angle < 0:
                #    angle += 360
                # rotated_polygon = get_cached_rotation(current_carpet, angle)

                # Пробуем разместить в той же позиции
                bounds = rotated_polygon.bounds
                rotated_width = bounds[2] - bounds[0]
                rotated_height = bounds[3] - bounds[1]

                # Проверяем, помещается ли в лист
                if rotated_width > sheet_width_mm or rotated_height > sheet_height_mm:
                    continue

                # Создаем тестовое размещение
                test_x, test_y = (
                    current_carpet.polygon.bounds[0],
                    current_carpet.polygon.bounds[1],
                )
                test_polygon = translate_polygon(
                    rotated_polygon, test_x - bounds[0], test_y - bounds[1]
                )

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
                        priority=current_carpet.priority,
                    )

                    test_trapped = calculate_trapped_space(
                        test_carpets, sheet_width_mm, sheet_height_mm
                    )
                    improvement = current_trapped - test_trapped

                    if (
                        improvement > best_improvement and improvement > 200
                    ):  # REDUCED: Минимум 20 см² улучшения (еще более чувствительный)
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
                    priority=current_carpet.priority,
                )
                improvements_made += 1

    return optimized_carpets


def calculate_free_top_space(
    placed_carpets: list[PlacedCarpet], sheet_width_mm: float, sheet_height_mm: float
) -> float:
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


def place_polygon_at_origin(polygon: Polygon) -> Polygon:
    """Move polygon so its bottom-left corner is at (0,0)."""
    bounds = polygon.bounds
    return translate_polygon(polygon, -bounds[0], -bounds[1])


def apply_placement_transform(
    polygon: Polygon, x_offset: float, y_offset: float, rotation_angle: int
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
        # CRITICAL FIX: Check intersection and area
        if polygon1.intersects(polygon2):
            intersection = polygon1.intersection(polygon2)
            if hasattr(intersection, 'area') and intersection.area > 0.01:  # Более строгий порог
                # DEBUG: Логируем обнаруженные коллизии
                # logger.warning(f"🔍 КОЛЛИЗИЯ ОБНАРУЖЕНА: площадь пересечения {intersection.area:.3f} мм²")
                return True

        # SPEED OPTIMIZATION: Only use bbox pre-filter for distant objects
        bounds1 = polygon1.bounds
        bounds2 = polygon2.bounds

        # Calculate minimum possible distance between bounding boxes
        dx = max(0, max(bounds1[0] - bounds2[2], bounds2[0] - bounds1[2]))
        dy = max(0, max(bounds1[1] - bounds2[3], bounds2[1] - bounds1[3]))
        bbox_min_distance = (dx * dx + dy * dy) ** 0.5

        # SAFE EARLY EXIT: Only skip geometric check if bounding boxes are clearly far apart
        if bbox_min_distance > 50:  # Только если точно далеко
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

    placed: list[PlacedCarpet] = []
    unplaced: list[UnplacedCarpet] = []

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
        polygon = carpet.polygon

        placed_successfully = False

        # Check if polygon is too large for the sheet
        bounds = polygon.bounds
        poly_width = bounds[2] - bounds[0]
        poly_height = bounds[3] - bounds[1]

        if poly_width > sheet_width_mm or poly_height > sheet_height_mm:
            unplaced.append(UnplacedCarpet.from_carpet(carpet))
            continue

        # REVOLUTIONARY: Try all rotations with TETRIS PRIORITY (bottom-left first)
        best_placement = None
        best_priority = float("inf")  # Lower is better (Y*1000 + X)

        # Only allowed rotation angles for cutting machines
        rotation_angles = [0, 90, 180, 270]

        for angle in rotation_angles:
            rotated = get_cached_rotation(carpet, angle)
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
                # TRUE TETRIS STRATEGY: Minimize global maximum height, not individual positions!

                # Calculate what the maximum height would be after placing this carpet
                dx_to_target = best_x - rotated_bounds[0]
                dy_to_target = best_y - rotated_bounds[1]
                test_translated = translate_polygon(rotated, dx_to_target, dy_to_target)

                all_test_placed = (
                    existing_placed
                    + placed
                    + [
                        PlacedCarpet(
                            polygon=test_translated,
                            carpet_id=carpet.carpet_id,  # Используем реальный carpet_id вместо 0!
                            priority=carpet.priority,
                            x_offset=dx_to_target,
                            y_offset=dy_to_target,
                            angle=angle,
                            filename=carpet.filename,
                            color=carpet.color,
                            order_id=carpet.order_id,
                        )
                    ]
                )

                # Find maximum height after this placement - THIS IS THE KEY TETRIS METRIC!
                max_height_after = (
                    max(c.polygon.bounds[3] for c in all_test_placed)
                    if all_test_placed
                    else 0
                )

                # PRIMARY SCORE: Heavily penalize orientations that increase maximum height
                # This is the core of true Tetris behavior
                global_height_score = (
                    max_height_after * 10000
                )  # Much higher weight than individual position

                # SECONDARY SCORE: X position for tie-breaking (prefer left placement)
                x_position_score = best_x

                # Combined position score prioritizes global compactness
                position_score = global_height_score + x_position_score

                # УЛУЧШЕННЫЙ ТЕТРИС: Более чувствительная оценка aspect ratio
                shape_bonus = 0
                aspect_ratio = (
                    rotated_width / rotated_height if rotated_height > 0 else 1
                )

                # REDUCED bonus for horizontal orientations - don't override good positions
                if aspect_ratio > 1.05:
                    # Much smaller bonus for width - max 500 instead of 2000
                    width_bonus = min(500, int((aspect_ratio - 1) * 500))
                    shape_bonus -= width_bonus

                    # Extra bonus if touching bottom edge (still important for tetris)
                    if best_y < 5:  # Within 5mm of bottom
                        shape_bonus -= 2000  # Reduced from 3000

                    # Extra bonus if touching left edge (less important than bottom)
                    if best_x < 5:  # Within 5mm of left
                        shape_bonus -= 1000  # Reduced from 2000

                # REDUCED penalty for tall orientations - don't punish good positions too much
                elif aspect_ratio < 0.95:
                    height_penalty = min(
                        300, int((1 - aspect_ratio) * 300)
                    )  # Reduced from 1000
                    shape_bonus += height_penalty

                # REVOLUTIONARY: True tetris quality assessment
                tetris_bonus = calculate_tetris_quality_bonus(
                    rotated, all_test_placed, sheet_width_mm, sheet_height_mm
                )
                shape_bonus -= tetris_bonus  # Negative is better

                total_score = position_score + shape_bonus

                # DEBUG: Log scoring for each orientation
                if verbose:
                    print(
                        f"  Angle {angle}°: pos=({best_x:.1f},{best_y:.1f}), "
                        f"pos_score={position_score:.0f}, shape_bonus={shape_bonus:.0f}, "
                        f"tetris_bonus={tetris_bonus:.0f}, total={total_score:.0f}, aspect_ratio={aspect_ratio:.2f}"
                    )

                if total_score < best_priority:
                    best_priority = total_score

                    # Calculate proper offsets from original carpet position
                    orig_bounds = carpet.polygon.bounds
                    dx_to_target = best_x - rotated_bounds[0]
                    dy_to_target = best_y - rotated_bounds[1]
                    translated = translate_polygon(rotated, dx_to_target, dy_to_target)

                    # Calculate actual offset from original position
                    final_bounds = translated.bounds
                    actual_x_offset = final_bounds[0] - orig_bounds[0]
                    actual_y_offset = final_bounds[1] - orig_bounds[1]

                    best_placement = {
                        "polygon": translated,
                        "x_offset": actual_x_offset,
                        "y_offset": actual_y_offset,
                        "angle": angle,
                    }

        # Apply best placement if found
        if best_placement:
            placed.append(
                PlacedCarpet(
                    polygon=best_placement["polygon"],
                    carpet_id=carpet.carpet_id,
                    priority=carpet.priority,
                    x_offset=best_placement["x_offset"],
                    y_offset=best_placement["y_offset"],
                    angle=best_placement["angle"],
                    filename=carpet.filename,
                    color=carpet.color,
                    order_id=carpet.order_id,
                )
            )

            # 🚀 РЕВОЛЮЦИОННАЯ TETRIS-ОПТИМИЗАЦИЯ: Гравитация + Сжатие к краям
            if len(placed) > 1:  # Несколько новых ковров
                try:
                    # Этап 1: Гравитация
                    gravity_placed = apply_tetris_gravity(
                        placed, sheet_width_mm, sheet_height_mm
                    )

                    # Этап 2: Сжатие к правому краю
                    right_placed = apply_tetris_right_compaction(
                        gravity_placed, sheet_width_mm, sheet_height_mm
                    )

                    # Этап 3: Финальная гравитация
                    improved_placed = apply_tetris_gravity(
                        right_placed, sheet_width_mm, sheet_height_mm
                    )

                    # КРИТИЧНО: Ультра-строгая проверка коллизий
                    safe = True
                    for i, _ in enumerate(improved_placed):
                        for j in range(i + 1, len(improved_placed)):
                            if check_collision(
                                improved_placed[i].polygon,
                                improved_placed[j].polygon,
                                min_gap=2.0,  # Строгий 2мм зазор
                            ):
                                safe = False
                                break
                        if not safe:
                            break

                    # Проверяем коллизии с существующими коврами
                    if safe:
                        for new_carpet in improved_placed:
                            for existing_carpet in existing_placed:
                                if new_carpet.polygon.intersects(
                                    existing_carpet.polygon
                                ):
                                    intersection = new_carpet.polygon.intersection(
                                        existing_carpet.polygon
                                    )
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

    # FAST OPTIMIZATION for existing sheets
    if tighten and len(placed) <= 5:  # Very conservative optimization
        # Apply simple compaction only for tiny sets
        placed = simple_compaction(placed, sheet_size)

        # Light tightening with obstacles
        all_obstacles = existing_placed + placed
        placed = tighten_layout_with_obstacles(
            placed, all_obstacles, sheet_size, min_gap=1.0
        )

    return placed, unplaced


def ultra_left_compaction(
    placed: list[PlacedCarpet],
    sheet_size: tuple[float, float],
    target_width_fraction: float = 0.7,  # Try to fit everything in 70% of sheet width
) -> list[PlacedCarpet]:
    """ULTRA-AGGRESSIVE left compaction - squeeze everything to the left side."""
    if not placed:
        return placed

    sheet_width_mm = sheet_size[0] * 10
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
                for distance in [
                    move_distance,
                    move_distance * 0.75,
                    move_distance * 0.5,
                    move_distance * 0.25,
                    10.0,
                    5.0,
                    2.0,
                    1.0,
                ]:
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
                polygon=new_poly,
                carpet_id=item.carpet_id,
                priority=item.priority,
                x_offset=item.x_offset + dx_total,
                y_offset=item.y_offset + dy_total,
                angle=item.angle,
                filename=item.filename,
                color=item.color,
                order_id=item.order_id,
            )
        )

    return new_placed


def simple_compaction(
    placed: list[PlacedCarpet], sheet_size: tuple[float, float], min_gap: float = 0.5
) -> list[PlacedCarpet]:
    """FAST Simple compaction - just basic left+down movement."""
    if not placed or len(placed) > 35:  # Allow processing of larger sets
        return placed

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
        x_order = sorted(
            range(n), key=lambda i: current_polys[i].bounds[0]
        )  # Process left to right

        for i in x_order:
            poly = current_polys[i]
            bounds = poly.bounds

            # Calculate maximum possible left movement
            max_left_move = bounds[0]  # Distance to left edge

            # Try to move maximum distance first, then smaller steps
            for left_distance in [
                max_left_move,
                max_left_move * 0.75,
                max_left_move * 0.5,
                max_left_move * 0.25,
                5.0,
                2.0,
                1.0,
            ]:
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
                polygon=new_poly,
                carpet_id=item.carpet_id,
                priority=item.priority,
                x_offset=item.x_offset + dx_total,
                y_offset=item.y_offset + dy_total,
                angle=item.angle,
                filename=item.filename,
                color=item.color,
                order_id=item.order_id,
            )
        )

    return new_placed


def fast_edge_snap(
    placed: list[PlacedCarpet], sheet_size: tuple[float, float], min_gap: float = 1.0
) -> list[PlacedCarpet]:
    """FAST edge snapping - just basic left/bottom movement."""
    if not placed or len(placed) > 25:  # Allow larger sets for better optimization
        return placed

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
            for left_distance in [
                max_left,
                max_left * 0.75,
                max_left * 0.5,
                max_left * 0.25,
                step,
                step / 2,
            ]:
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
                polygon=new_poly,
                carpet_id=item.carpet_id,
                priority=item.priority,
                x_offset=new_x_off,
                y_offset=new_y_off,
                angle=item.angle,
                filename=item.filename,
                color=item.color,
                order_id=item.order_id,
            )
        )

    return new_placed


def bin_packing(
    polygons: list[Carpet],
    sheet_size: tuple[float, float],
    verbose: bool = True,
    progress_callback=None,  # Callback function for progress updates
) -> tuple[list[PlacedCarpet], list[UnplacedCarpet]]:
    """Optimize placement of complex polygons on a sheet with ultra-dense/polygonal/improved algorithms."""

    # Performance timing (no algorithm changes)
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
        # 1. Priority level (priority 1 always comes first)
        # 2. Area (larger first within same priority)
        # 3. Aspect ratio (irregular shapes first)
        # 4. Compactness (less regular shapes first)
        aspect_ratio = (
            max(width / height, height / width) if min(width, height) > 0 else 1
        )
        compactness = area / (width * height) if width * height > 0 else 0
        perimeter_approx = 2 * (width + height)

        # Base score from geometry
        geometry_score = (
            area * 1.0
            + (aspect_ratio - 1) * area * 0.3
            + (1 - compactness) * area * 0.2
            + perimeter_approx * 0.05
        )
        return geometry_score

    sorted_polygons = sorted(polygons, key=get_polygon_priority, reverse=True)

    # Set dataset size context for adaptive algorithms
    find_bottom_left_position._dataset_size = len(sorted_polygons)

    if verbose:
        st.info("✨ Сортировка полигонов по площади (сначала крупные)")

    # PERFORMANCE: Adaptive processing - гарантированная обработка всех ковров
    def should_process_carpet(index, total_count, placed_count):
        """
        Определить, нужно ли обрабатывать ковер с данным индексом.
        ИСПРАВЛЕНО: Обеспечивает обработку всех ковров, избегая "потери" остатков.
        """
        # КРИТИЧНО: Для малых наборов обрабатываем ВСЕ
        if total_count <= 70:
            return True

        # Адаптивная логика для больших наборов
        fill_ratio = placed_count / max(1, total_count * 0.1)

        if fill_ratio < 0.3:  # Почти пустой лист - больше кандидатов
            target_count = min(70, total_count)
        else:  # Почти полон - меньше кандидатов
            target_count = min(50, total_count)

        # ИСПРАВЛЕНИЕ: Безопасный расчет шага
        if target_count >= total_count:
            return True  # Если цель >= общего количества - берем все

        step = max(1, total_count // target_count)

        # Проверяем, попадает ли текущий индекс в равномерную выборку
        return index % step == 0

    total_carpet_count = len(sorted_polygons)
    processed_count = 0

    for i, carpet in enumerate(sorted_polygons):
        # PERFORMANCE: Быстро пропускаем ненужные ковры
        if not should_process_carpet(i, total_carpet_count, len(placed)):
            continue

        processed_count += 1
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
            rotated = get_cached_rotation(carpet, angle)
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
                # TRUE TETRIS STRATEGY: Minimize global maximum height, not individual positions!

                # Calculate what the maximum height would be after placing this carpet
                dx_to_target = best_x - rotated_bounds[0]
                dy_to_target = best_y - rotated_bounds[1]
                test_translated = translate_polygon(rotated, dx_to_target, dy_to_target)

                all_test_placed = placed + [
                    PlacedCarpet(
                        polygon=test_translated,
                        x_offset=dx_to_target,
                        y_offset=dy_to_target,
                        angle=angle,
                        filename=carpet.filename,
                        color=carpet.color,
                        order_id=carpet.order_id,
                        carpet_id=carpet.carpet_id,
                        priority=carpet.priority,
                    )
                ]

                # Find maximum height after this placement - THIS IS THE KEY TETRIS METRIC!
                max_height_after = (
                    max(c.polygon.bounds[3] for c in all_test_placed)
                    if all_test_placed
                    else 0
                )

                # PRIMARY SCORE: Heavily penalize orientations that increase maximum height
                # This is the core of true Tetris behavior
                global_height_score = (
                    max_height_after * 10000
                )  # Much higher weight than individual position

                # SECONDARY SCORE: X position for tie-breaking (prefer left placement)
                x_position_score = best_x

                # Combined position score prioritizes global compactness
                position_score = global_height_score + x_position_score

                # УЛУЧШЕННЫЙ ТЕТРИС: Более чувствительная оценка aspect ratio
                shape_bonus = 0
                aspect_ratio = (
                    rotated_width / rotated_height if rotated_height > 0 else 1
                )

                # REDUCED bonus for horizontal orientations - don't override good positions
                if aspect_ratio > 1.05:
                    # Much smaller bonus for width - max 500 instead of 2000
                    width_bonus = min(500, int((aspect_ratio - 1) * 500))
                    shape_bonus -= width_bonus

                    # Extra bonus if touching bottom edge (still important for tetris)
                    if best_y < 5:  # Within 5mm of bottom
                        shape_bonus -= 2000  # Reduced from 3000

                    # Extra bonus if touching left edge (less important than bottom)
                    if best_x < 5:  # Within 5mm of left
                        shape_bonus -= 1000  # Reduced from 2000

                # REDUCED penalty for tall orientations - don't punish good positions too much
                elif aspect_ratio < 0.95:
                    height_penalty = min(
                        300, int((1 - aspect_ratio) * 300)
                    )  # Reduced from 1000
                    shape_bonus += height_penalty

                # 🎯 МАКСИМИЗАЦИЯ ВЕРХНЕГО ПРОСТРАНСТВА: Ключевая Тетрис-стратегия
                # Предпочитаем ориентации которые максимизируют непрерывное свободное пространство сверху

                # Симулируем размещение этого ковра и вычисляем будущую максимальную высоту
                dx_to_target = best_x - rotated_bounds[0]
                dy_to_target = best_y - rotated_bounds[1]
                test_translated = translate_polygon(rotated, dx_to_target, dy_to_target)

                # REVOLUTIONARY: True tetris quality assessment
                tetris_bonus = calculate_tetris_quality_bonus(
                    rotated, all_test_placed, sheet_width_mm, sheet_height_mm
                )
                shape_bonus -= tetris_bonus  # Negative is better

                total_score = position_score + shape_bonus

                if total_score < best_score:
                    best_score = total_score

                    # Calculate proper offsets from original carpet position
                    orig_bounds = carpet.polygon.bounds
                    dx_to_target = best_x - rotated_bounds[0]
                    dy_to_target = best_y - rotated_bounds[1]
                    translated = translate_polygon(rotated, dx_to_target, dy_to_target)

                    # Calculate actual offset from original position
                    final_bounds = translated.bounds
                    actual_x_offset = final_bounds[0] - orig_bounds[0]
                    actual_y_offset = final_bounds[1] - orig_bounds[1]

                    best_placement = {
                        "polygon": translated,
                        "x_offset": actual_x_offset,
                        "y_offset": actual_y_offset,
                        "angle": angle,
                    }

        # Apply best placement if found
        if best_placement:
            placed.append(
                PlacedCarpet(
                    polygon=best_placement["polygon"],  # type: ignore
                    carpet_id=carpet.carpet_id,
                    priority=carpet.priority,
                    x_offset=best_placement["x_offset"],  # type: ignore
                    y_offset=best_placement["y_offset"],  # type: ignore
                    angle=best_placement["angle"],  # type: ignore
                    filename=carpet.filename,
                    color=carpet.color,
                    order_id=carpet.order_id,
                )
            )

            # 🚀 РЕВОЛЮЦИОННАЯ POST-PLACEMENT OPTIMIZATION
            if len(placed) >= 2:  # Применяем только если есть что оптимизировать
                try:
                    # Этап 1: АГРЕССИВНАЯ Post-Placement оптимизация (полное переразмещение проблемных ковров)
                    post_optimized = post_placement_optimize_aggressive(
                        placed, sheet_width_mm, sheet_height_mm
                    )

                    # Этап 2: Гравитация для финальной компактификации
                    gravity_optimized = apply_tetris_gravity(
                        post_optimized, sheet_width_mm, sheet_height_mm
                    )

                    # Этап 3: НОВОЕ! Сжатие к правому краю (как в настоящем Тетрисе)
                    right_compacted = apply_tetris_right_compaction(
                        gravity_optimized, sheet_width_mm, sheet_height_mm
                    )

                    # Этап 4: Финальная гравитация после сжатия к правому краю
                    final_optimized = apply_tetris_gravity(
                        right_compacted, sheet_width_mm, sheet_height_mm
                    )

                    # КРИТИЧНО: Проверяем безопасность финального результата с ультра-строгим контролем
                    collision_found = False
                    for i in range(len(final_optimized)):
                        for j in range(i + 1, len(final_optimized)):
                            if check_collision(
                                final_optimized[i].polygon,
                                final_optimized[j].polygon,
                                min_gap=2.0,  # Строгий 2мм зазор
                            ):
                                collision_found = True
                                break
                        if collision_found:
                            break

                    if not collision_found:
                        # Вычисляем улучшения
                        original_trapped = calculate_trapped_space(
                            placed, sheet_width_mm, sheet_height_mm
                        )
                        optimized_trapped = calculate_trapped_space(
                            final_optimized, sheet_width_mm, sheet_height_mm
                        )

                        trapped_improvement = original_trapped - optimized_trapped

                        placed = final_optimized  # Применяем полную оптимизацию

                        if (
                            verbose and trapped_improvement > 5000
                        ):  # Больше 500 см² улучшения
                            st.success(
                                f"🎯 Post-Placement оптимизация освободила {trapped_improvement/100:.0f} см² заперного пространства!"
                            )

                        # Дополнительная информация о верхнем пространстве
                        free_top_area = calculate_free_top_space(
                            placed, sheet_width_mm, sheet_height_mm
                        )
                        if verbose and free_top_area > 50000:  # Больше 500 см²
                            st.info(f"🏞️ Свободно сверху: {free_top_area/10000:.0f} см²")

                    elif verbose:
                        st.warning(
                            "⚠️ Post-Placement оптимизация отменена - обнаружены коллизии"
                        )

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
                                polygon=translated,
                                carpet_id=carpet.carpet_id,
                                priority=carpet.priority,
                                x_offset=x_offset,
                                y_offset=y_offset,
                                angle=0,
                                filename=carpet.filename,
                                color=carpet.color,
                                order_id=carpet.order_id,
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
                    polygon=carpet.polygon,
                    carpet_id=carpet.carpet_id,
                    priority=carpet.priority,
                    filename=carpet.filename,
                    color=carpet.color,
                    order_id=carpet.order_id,
                )
            )
    # КРИТИЧНО: Добавляем пропущенные ковры в unplaced чтобы они не терялись
    if processed_count < total_carpet_count:
        for i, carpet in enumerate(sorted_polygons):
            if not should_process_carpet(i, total_carpet_count, len(placed)):
                # Этот ковер был пропущен - добавляем в unplaced
                unplaced.append(
                    UnplacedCarpet(
                        polygon=carpet.polygon,
                        carpet_id=carpet.carpet_id,
                        priority=carpet.priority,
                        filename=carpet.filename,
                        color=carpet.color,
                        order_id=carpet.order_id,
                    )
                )

    # PERFORMANCE: Логируем статистику обработки
    if total_carpet_count > 100:
        skipped_count = total_carpet_count - processed_count
        logger.info(
            f"📊 Обработано {processed_count} из {total_carpet_count} ковров, пропущено {skipped_count}, размещено {len(placed)}, в unplaced {len(unplaced)}"
        )

    # ULTRA-AGGRESSIVE LEFT COMPACTION - always apply for maximum density
    if len(placed) <= 20:  # Optimize most reasonable sets
        # Ultra-aggressive left compaction to squeeze everything left - ТЕСТИРУЕМ
        placed = ultra_left_compaction(placed, sheet_size, target_width_fraction=0.4)

        # Simple compaction with aggressive left push - ТЕСТИРУЕМ
        placed = simple_compaction(placed, sheet_size)

        # Additional edge snapping for maximum left compaction - ТЕСТИРУЕМ
        placed = fast_edge_snap(placed, sheet_size)

        # Final ultra-left compaction - ТЕСТИРУЕМ
        placed = ultra_left_compaction(placed, sheet_size, target_width_fraction=0.5)

        # Light tightening to clean up - ВРЕМЕННО ОТКЛЮЧЕНО
        # placed = tighten_layout(placed, sheet_size, min_gap=0.5, step=2.0, max_passes=1)
    elif len(placed) <= 35:  # For larger sets, still do aggressive compaction - ВРЕМЕННО ОТКЛЮЧЕНО
        # placed = ultra_left_compaction(placed, sheet_size, target_width_fraction=0.6)
        # placed = simple_compaction(placed, sheet_size)
        # placed = fast_edge_snap(placed, sheet_size)
        pass
    # No optimization for very large sets

    # POST-OPTIMIZATION: Gravity compaction - ВРЕМЕННО ОТКЛЮЧЕНО для отладки пересечений
    # if placed:
    #     placed = apply_gravity_optimization(placed, sheet_width_mm, sheet_height_mm)

    # КРИТИЧЕСКАЯ ПРОВЕРКА: убеждаемся что нет пересечений
    intersections_found = False
    for i, carpet1 in enumerate(placed):
        for j, carpet2 in enumerate(placed):
            if i < j:  # Проверяем каждую пару только один раз
                if carpet1.polygon.intersects(carpet2.polygon):
                    intersection = carpet1.polygon.intersection(carpet2.polygon)
                    if hasattr(intersection, 'area') and intersection.area > 0.01:  # Более 0.01 мм²
                        logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА: Обнаружено пересечение между {carpet1.filename} и {carpet2.filename}, площадь: {intersection.area:.3f} мм²")
                        intersections_found = True

    if verbose:
        usage_percent = calculate_usage_percent(placed, sheet_size)
        elapsed_time = time.time() - start_time
        if intersections_found:
            logger.error("🚨 ВНИМАНИЕ: Обнаружены пересечения ковров!")
        st.info(
            f"🏁 Упаковка завершена: {len(placed)} размещено, {len(unplaced)} не размещено, использование: {usage_percent:.1f}%, время: {elapsed_time:.1f}с"
        )
    return placed, unplaced


def apply_gravity_optimization(
    placed_carpets: list[PlacedCarpet], sheet_width_mm: float, sheet_height_mm: float
) -> list[PlacedCarpet]:
    """
    Improved gravity optimization for better sheet utilization while maintaining performance.
    """
    if not placed_carpets:
        return placed_carpets

    # STEP 1: Vertical compaction (move down)
    sorted_carpets = sorted(
        placed_carpets, key=lambda c: c.polygon.bounds[3], reverse=True
    )
    vertically_optimized = []

    for i, carpet in enumerate(sorted_carpets):
        other_carpets = vertically_optimized + sorted_carpets[i + 1 :]
        moved_carpet = move_carpet_down(
            carpet, other_carpets, sheet_width_mm, sheet_height_mm
        )
        vertically_optimized.append(moved_carpet)

    # STEP 2: Horizontal compaction (move left)
    sorted_by_x = sorted(
        vertically_optimized, key=lambda c: c.polygon.bounds[2], reverse=True
    )
    horizontally_optimized = []

    for i, carpet in enumerate(sorted_by_x):
        other_carpets = horizontally_optimized + sorted_by_x[i + 1 :]
        moved_carpet = move_carpet_left(
            carpet, other_carpets, sheet_width_mm, sheet_height_mm
        )
        horizontally_optimized.append(moved_carpet)

    return horizontally_optimized


def move_carpet_down(
    carpet: PlacedCarpet,
    other_carpets: list[PlacedCarpet],
    sheet_width_mm: float,
    sheet_height_mm: float,
) -> PlacedCarpet:
    """Move a single carpet as low as possible without collisions, including trying different rotations."""
    import shapely.affinity

    bounds = carpet.polygon.bounds
    poly_width = bounds[2] - bounds[0]
    poly_height = bounds[3] - bounds[1]

    best_position = (bounds[0], bounds[1], carpet.angle)  # Current position and angle
    max_improvement = 0  # Track how much we moved down

    # Try different Y positions from bottom to current position
    step_size = 10  # 1cm steps for better precision

    # Try different rotations to fit through narrow spaces
    angles_to_try = [carpet.angle]  # Start with current angle
    if carpet.angle == 0:
        angles_to_try.extend([90, 180, 270])
    elif carpet.angle == 90:
        angles_to_try.extend([0, 180, 270])
    elif carpet.angle == 180:
        angles_to_try.extend([0, 90, 270])
    elif carpet.angle == 270:
        angles_to_try.extend([0, 90, 180])

    # Start from bottom and go up, looking for the lowest possible position
    for test_y in range(
        0, int(sheet_height_mm - max(poly_width, poly_height)) + step_size, step_size
    ):
        # Only consider positions that are lower than current position (actual improvement)
        if test_y >= bounds[1]:
            continue

        # Try different rotations
        for test_angle in angles_to_try:
            # Create rotated polygon at origin
            rotated_polygon = shapely.affinity.rotate(
                carpet.polygon, test_angle - carpet.angle, origin=(0, 0)
            )
            rot_bounds = rotated_polygon.bounds
            rot_width = rot_bounds[2] - rot_bounds[0]
            rot_height = rot_bounds[3] - rot_bounds[1]

            # Also try X adjustments for better fitting
            x_offsets = [
                bounds[0],
                bounds[0] - 20,
                bounds[0] + 20,
                bounds[0] - 50,
                bounds[0] + 50,
            ]

            for test_x_base in x_offsets:
                # Skip if rotated carpet would be outside sheet bounds
                if test_x_base < 0 or test_x_base + rot_width > sheet_width_mm:
                    continue
                if test_y + rot_height > sheet_height_mm:
                    continue

                # Calculate final position by moving rotated polygon to test position
                # First move to origin, then rotate, then move to target position
                dx_to_origin = -bounds[0]
                dy_to_origin = -bounds[1]
                moved_to_origin = shapely.affinity.translate(
                    carpet.polygon, dx_to_origin, dy_to_origin
                )
                rotated_at_origin = shapely.affinity.rotate(
                    moved_to_origin, test_angle - carpet.angle, origin=(0, 0)
                )
                test_polygon = shapely.affinity.translate(
                    rotated_at_origin, test_x_base, test_y
                )

                test_bounds = test_polygon.bounds

                # Double-check bounds
                if (
                    test_bounds[0] < 0
                    or test_bounds[1] < 0
                    or test_bounds[2] > sheet_width_mm
                    or test_bounds[3] > sheet_height_mm
                ):
                    continue

                # Check for collisions with other carpets
                has_collision = False
                for other in other_carpets:
                    if test_polygon.intersects(other.polygon):
                        intersection = test_polygon.intersection(other.polygon)
                        if (
                            hasattr(intersection, "area") and intersection.area > 1
                        ):  # Reduced overlap tolerance for tighter packing
                            has_collision = True
                            break

                if not has_collision:
                    improvement = bounds[1] - test_y  # How much we moved down
                    if improvement > max_improvement:
                        max_improvement = improvement
                        best_position = (test_x_base, test_y, test_angle)

    # If we found a better position, create new carpet
    if max_improvement > 1:  # Move even for small improvements (>1mm)
        new_x, new_y, new_angle = best_position

        # Calculate the final polygon position
        dx_to_origin = -bounds[0]
        dy_to_origin = -bounds[1]
        moved_to_origin = shapely.affinity.translate(
            carpet.polygon, dx_to_origin, dy_to_origin
        )
        rotated_at_origin = shapely.affinity.rotate(
            moved_to_origin, new_angle - carpet.angle, origin=(0, 0)
        )
        new_polygon = shapely.affinity.translate(rotated_at_origin, new_x, new_y)

        # Calculate the offset change
        new_bounds = new_polygon.bounds
        dx_total = new_bounds[0] - bounds[0]
        dy_total = new_bounds[1] - bounds[1]

        return PlacedCarpet(
            polygon=new_polygon,
            carpet_id=carpet.carpet_id,
            priority=carpet.priority,
            x_offset=carpet.x_offset + dx_total,
            y_offset=carpet.y_offset + dy_total,
            angle=new_angle,
            filename=carpet.filename,
            color=carpet.color,
            order_id=carpet.order_id,
        )

    return carpet  # No significant improvement found


def move_carpet_left(
    carpet: PlacedCarpet,
    other_carpets: list[PlacedCarpet],
    sheet_width_mm: float,
    sheet_height_mm: float,
) -> PlacedCarpet:
    """Move a single carpet as far left as possible without collisions, including trying different rotations."""
    import shapely.affinity

    bounds = carpet.polygon.bounds

    best_position = (bounds[0], bounds[1], carpet.angle)  # Current position and angle
    max_improvement = 0  # Track how much we moved left

    # Try different X positions from left to current position
    step_size = 10  # 1cm steps for better precision

    # Try different rotations to fit through narrow spaces
    angles_to_try = [carpet.angle]  # Start with current angle
    if carpet.angle == 0:
        angles_to_try.extend([90, 180, 270])
    elif carpet.angle == 90:
        angles_to_try.extend([0, 180, 270])
    elif carpet.angle == 180:
        angles_to_try.extend([0, 90, 270])
    elif carpet.angle == 270:
        angles_to_try.extend([0, 90, 180])

    # Start from left edge and go right, looking for the leftmost possible position
    for test_x in range(0, int(bounds[0]) + step_size, step_size):
        # Only consider positions that are further left than current position (actual improvement)
        if test_x >= bounds[0]:
            continue

        # Try different rotations
        for test_angle in angles_to_try:
            # Create rotated polygon at origin
            rotated_polygon = shapely.affinity.rotate(
                carpet.polygon, test_angle - carpet.angle, origin=(0, 0)
            )
            rot_bounds = rotated_polygon.bounds
            rot_width = rot_bounds[2] - rot_bounds[0]
            rot_height = rot_bounds[3] - rot_bounds[1]

            # Also try Y adjustments for better fitting
            y_offsets = [
                bounds[1],
                bounds[1] - 20,
                bounds[1] + 20,
                bounds[1] - 50,
                bounds[1] + 50,
            ]

            for test_y_base in y_offsets:
                # Skip if rotated carpet would be outside sheet bounds
                if test_x + rot_width > sheet_width_mm:
                    continue
                if test_y_base < 0 or test_y_base + rot_height > sheet_height_mm:
                    continue

                # Calculate final position by moving rotated polygon to test position
                # First move to origin, then rotate, then move to target position
                dx_to_origin = -bounds[0]
                dy_to_origin = -bounds[1]
                moved_to_origin = shapely.affinity.translate(
                    carpet.polygon, dx_to_origin, dy_to_origin
                )
                rotated_at_origin = shapely.affinity.rotate(
                    moved_to_origin, test_angle - carpet.angle, origin=(0, 0)
                )
                test_polygon = shapely.affinity.translate(
                    rotated_at_origin, test_x, test_y_base
                )

                test_bounds = test_polygon.bounds

                # Double-check bounds
                if (
                    test_bounds[0] < 0
                    or test_bounds[1] < 0
                    or test_bounds[2] > sheet_width_mm
                    or test_bounds[3] > sheet_height_mm
                ):
                    continue

                # Check for collisions with other carpets
                has_collision = False
                for other in other_carpets:
                    if test_polygon.intersects(other.polygon):
                        intersection = test_polygon.intersection(other.polygon)
                        if (
                            hasattr(intersection, "area") and intersection.area > 1
                        ):  # Reduced overlap tolerance for tighter packing
                            has_collision = True
                            break

                if not has_collision:
                    improvement = bounds[0] - test_x  # How much we moved left
                    if improvement > max_improvement:
                        max_improvement = improvement
                        best_position = (test_x, test_y_base, test_angle)

    # If we found a better position, create new carpet
    if max_improvement > 1:  # Move even for small improvements (>1mm)
        new_x, new_y, new_angle = best_position

        # Calculate the final polygon position
        dx_to_origin = -bounds[0]
        dy_to_origin = -bounds[1]
        moved_to_origin = shapely.affinity.translate(
            carpet.polygon, dx_to_origin, dy_to_origin
        )
        rotated_at_origin = shapely.affinity.rotate(
            moved_to_origin, new_angle - carpet.angle, origin=(0, 0)
        )
        new_polygon = shapely.affinity.translate(rotated_at_origin, new_x, new_y)

        # Calculate the offset change
        new_bounds = new_polygon.bounds
        dx_total = new_bounds[0] - bounds[0]
        dy_total = new_bounds[1] - bounds[1]

        return PlacedCarpet(
            polygon=new_polygon,
            carpet_id=carpet.carpet_id,
            priority=carpet.priority,
            x_offset=carpet.x_offset + dx_total,
            y_offset=carpet.y_offset + dy_total,
            angle=new_angle,
            filename=carpet.filename,
            color=carpet.color,
            order_id=carpet.order_id,
        )

    return carpet  # No significant improvement found


def move_carpet_down_aggressive(
    carpet: PlacedCarpet,
    other_carpets: list[PlacedCarpet],
    sheet_width_mm: float,
    sheet_height_mm: float,
) -> PlacedCarpet:
    """AGGRESSIVE downward movement with fine-grained steps and rotation."""
    import shapely.affinity

    bounds = carpet.polygon.bounds
    best_position = (bounds[0], bounds[1], carpet.angle)
    max_improvement = 0

    step_size = 5  # 5mm steps for good balance of precision/speed

    # Try current angle and all 90-degree rotations
    for test_angle in [carpet.angle, 0, 90, 180, 270]:
        if test_angle == carpet.angle:
            rotated_polygon = carpet.polygon
        else:
            rotated_polygon = shapely.affinity.rotate(
                carpet.polygon, test_angle - carpet.angle, origin=(0, 0)
            )

        rot_bounds = rotated_polygon.bounds
        rot_width = rot_bounds[2] - rot_bounds[0]

        # Try moving from bottom up to current position
        for test_y in range(0, int(bounds[1]) + step_size, step_size):
            if test_y >= bounds[1]:
                continue

            # Try slight X adjustments for better fitting
            for x_adjust in [-50, -20, 0, 20, 50]:
                test_x = bounds[0] + x_adjust
                if test_x < 0 or test_x + rot_width > sheet_width_mm:
                    continue

                # Create test position
                dx_to_origin = -bounds[0]
                dy_to_origin = -bounds[1]
                moved_to_origin = shapely.affinity.translate(
                    carpet.polygon, dx_to_origin, dy_to_origin
                )
                rotated_at_origin = shapely.affinity.rotate(
                    moved_to_origin, test_angle - carpet.angle, origin=(0, 0)
                )
                test_polygon = shapely.affinity.translate(
                    rotated_at_origin, test_x, test_y
                )

                test_bounds = test_polygon.bounds
                if (
                    test_bounds[0] < 0
                    or test_bounds[1] < 0
                    or test_bounds[2] > sheet_width_mm
                    or test_bounds[3] > sheet_height_mm
                ):
                    continue

                # Check collisions with minimal gap tolerance
                has_collision = False
                for other in other_carpets:
                    if test_polygon.intersects(other.polygon):
                        intersection = test_polygon.intersection(other.polygon)
                        if (
                            hasattr(intersection, "area") and intersection.area > 0.1
                        ):  # Ultra-tight packing
                            has_collision = True
                            break

                if not has_collision:
                    improvement = bounds[1] - test_y
                    if improvement > max_improvement:
                        max_improvement = improvement
                        best_position = (test_x, test_y, test_angle)

    # Apply best position if found
    if max_improvement > 0.1:  # Any improvement is valuable
        new_x, new_y, new_angle = best_position

        dx_to_origin = -bounds[0]
        dy_to_origin = -bounds[1]
        moved_to_origin = shapely.affinity.translate(
            carpet.polygon, dx_to_origin, dy_to_origin
        )
        rotated_at_origin = shapely.affinity.rotate(
            moved_to_origin, new_angle - carpet.angle, origin=(0, 0)
        )
        new_polygon = shapely.affinity.translate(rotated_at_origin, new_x, new_y)

        new_bounds = new_polygon.bounds
        dx_total = new_bounds[0] - bounds[0]
        dy_total = new_bounds[1] - bounds[1]

        return PlacedCarpet(
            polygon=new_polygon,
            carpet_id=carpet.carpet_id,
            priority=carpet.priority,
            x_offset=carpet.x_offset + dx_total,
            y_offset=carpet.y_offset + dy_total,
            angle=new_angle,
            filename=carpet.filename,
            color=carpet.color,
            order_id=carpet.order_id,
        )

    return carpet


def move_carpet_left_aggressive(
    carpet: PlacedCarpet,
    other_carpets: list[PlacedCarpet],
    sheet_width_mm: float,
    sheet_height_mm: float,
) -> PlacedCarpet:
    """AGGRESSIVE leftward movement with rotation support."""
    import shapely.affinity

    bounds = carpet.polygon.bounds
    best_position = (bounds[0], bounds[1], carpet.angle)
    max_improvement = 0

    step_size = 2  # 2mm steps for maximum precision

    # Try current angle and rotations
    for test_angle in [carpet.angle, 0, 90, 180, 270]:
        if test_angle == carpet.angle:
            rotated_polygon = carpet.polygon
        else:
            rotated_polygon = shapely.affinity.rotate(
                carpet.polygon, test_angle - carpet.angle, origin=(0, 0)
            )

        rot_bounds = rotated_polygon.bounds
        rot_width = rot_bounds[2] - rot_bounds[0]

        # Try moving from left edge to current position
        for test_x in range(0, int(bounds[0]) + step_size, step_size):
            if test_x >= bounds[0]:
                continue

            # Try Y adjustments
            for y_adjust in [-50, -20, 0, 20, 50]:
                test_y = bounds[1] + y_adjust
                if test_x + rot_width > sheet_width_mm:
                    continue

                # Create test position
                dx_to_origin = -bounds[0]
                dy_to_origin = -bounds[1]
                moved_to_origin = shapely.affinity.translate(
                    carpet.polygon, dx_to_origin, dy_to_origin
                )
                rotated_at_origin = shapely.affinity.rotate(
                    moved_to_origin, test_angle - carpet.angle, origin=(0, 0)
                )
                test_polygon = shapely.affinity.translate(
                    rotated_at_origin, test_x, test_y
                )

                test_bounds = test_polygon.bounds
                if (
                    test_bounds[0] < 0
                    or test_bounds[1] < 0
                    or test_bounds[2] > sheet_width_mm
                    or test_bounds[3] > sheet_height_mm
                ):
                    continue

                # Check collisions
                has_collision = False
                for other in other_carpets:
                    if test_polygon.intersects(other.polygon):
                        intersection = test_polygon.intersection(other.polygon)
                        if hasattr(intersection, "area") and intersection.area > 0.1:
                            has_collision = True
                            break

                if not has_collision:
                    improvement = bounds[0] - test_x
                    if improvement > max_improvement:
                        max_improvement = improvement
                        best_position = (test_x, test_y, test_angle)

    # Apply best position if found
    if max_improvement > 0.1:
        new_x, new_y, new_angle = best_position

        dx_to_origin = -bounds[0]
        dy_to_origin = -bounds[1]
        moved_to_origin = shapely.affinity.translate(
            carpet.polygon, dx_to_origin, dy_to_origin
        )
        rotated_at_origin = shapely.affinity.rotate(
            moved_to_origin, new_angle - carpet.angle, origin=(0, 0)
        )
        new_polygon = shapely.affinity.translate(rotated_at_origin, new_x, new_y)

        new_bounds = new_polygon.bounds
        dx_total = new_bounds[0] - bounds[0]
        dy_total = new_bounds[1] - bounds[1]

        return PlacedCarpet(
            polygon=new_polygon,
            x_offset=carpet.x_offset + dx_total,
            y_offset=carpet.y_offset + dy_total,
            angle=new_angle,
            filename=carpet.filename,
            color=carpet.color,
            order_id=carpet.order_id,
            carpet_id=carpet.carpet_id,
            priority=carpet.priority,
        )

    return carpet


def move_carpet_right_to_edge(
    carpet: PlacedCarpet,
    other_carpets: list[PlacedCarpet],
    sheet_width_mm: float,
    sheet_height_mm: float,
) -> PlacedCarpet:
    """Move carpet as far right as possible to maximize left space."""
    import shapely.affinity

    bounds = carpet.polygon.bounds
    poly_width = bounds[2] - bounds[0]

    best_x = bounds[0]
    max_improvement = 0

    # Try moving right from current position to edge
    step_size = 2
    for test_x in range(
        int(bounds[0]), int(sheet_width_mm - poly_width) + step_size, step_size
    ):
        if test_x <= bounds[0]:
            continue

        # Try slight Y adjustments
        for y_adjust in [-20, 0, 20]:
            test_y = bounds[1] + y_adjust

            dx = test_x - bounds[0]
            dy = test_y - bounds[1]
            test_polygon = shapely.affinity.translate(carpet.polygon, dx, dy)

            test_bounds = test_polygon.bounds
            if (
                test_bounds[0] < 0
                or test_bounds[1] < 0
                or test_bounds[2] > sheet_width_mm
                or test_bounds[3] > sheet_height_mm
            ):
                continue

            # Check collisions
            has_collision = False
            for other in other_carpets:
                if test_polygon.intersects(other.polygon):
                    intersection = test_polygon.intersection(other.polygon)
                    if hasattr(intersection, "area") and intersection.area > 0.1:
                        has_collision = True
                        break

            if not has_collision:
                improvement = test_x - bounds[0]
                if improvement > max_improvement:
                    max_improvement = improvement
                    best_x = test_x

    # Apply best position if found
    if max_improvement > 0.1:
        dx = best_x - bounds[0]
        new_polygon = shapely.affinity.translate(carpet.polygon, dx, 0)

        return PlacedCarpet(
            polygon=new_polygon,
            x_offset=carpet.x_offset + dx,
            y_offset=carpet.y_offset,
            angle=carpet.angle,
            filename=carpet.filename,
            color=carpet.color,
            order_id=carpet.order_id,
            carpet_id=carpet.carpet_id,
            priority=carpet.priority,
        )

    return carpet


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

    # Add sheet edges with adaptive step for small polygons
    polygon_size = poly_width * poly_height
    is_small = polygon_size < 10000  # 100mm x 100mm

    step = 0.5 if is_small else max(1.0, min(poly_width, poly_height) / 10)

    for x in np.arange(0, sheet_width - poly_width + 1, step):
        candidates.append((x, 0))
    for y in np.arange(0, sheet_height - poly_height + 1, step):
        candidates.append((0, y))

    # Sort by bottom-left preference and limit candidates
    candidates = list(set(candidates))  # Remove duplicates
    candidates.sort(key=lambda pos: (pos[1], pos[0]))

    # Increase limit for small polygons to improve placement success
    max_candidates = 1500 if is_small else 1000
    candidates = candidates[: min(max_candidates, len(candidates))]

    # Test each position using true geometric collision detection
    for x, y in candidates:
        x_offset = x - bounds[0]
        y_offset = y - bounds[1]
        test_polygon = translate_polygon(polygon, x_offset, y_offset)

        # CRITICAL FIX: Check sheet boundaries first
        test_bounds = test_polygon.bounds
        if (
            test_bounds[0] < -0.1
            or test_bounds[1] < -0.1
            or test_bounds[2] > sheet_width + 0.1
            or test_bounds[3] > sheet_height + 0.1
        ):
            continue

        # Use our new TRUE GEOMETRIC collision check (no bounding box constraints!)
        collision = False
        for obstacle in obstacles:
            if check_collision(test_polygon, obstacle, min_gap=0.1):  # Ultra-tight
                collision = True
                break

        if not collision:
            return x, y

    return None, None


def calculate_tetris_quality_bonus(
    rotated_polygon: Polygon, all_placed: list, sheet_width: float, sheet_height: float
) -> float:
    """
    Calculate tetris quality bonus for a given orientation.

    Returns a bonus score (higher = better tetris quality) based on:
    1. Fill ratio (how well the shape fills its bounding box)
    2. Accessibility (how much space below is accessible for future carpets)
    3. Top space utilization (how much vertical space remains)
    """
    bounds = rotated_polygon.bounds

    # 1. Bounding box fill ratio
    bbox_area = (bounds[2] - bounds[0]) * (bounds[3] - bounds[1])
    actual_area = rotated_polygon.area
    fill_ratio = actual_area / bbox_area if bbox_area > 0 else 0

    # 2. Accessibility analysis - check space below for future placement
    test_points_below = []
    for x in np.linspace(bounds[0], bounds[2], 8):
        for y in np.linspace(max(0, bounds[1] - 100), bounds[1], 5):  # 100mm below
            test_points_below.append((x, y))

    if test_points_below:
        # Count accessible points (not inside any placed carpet)
        accessible_count = 0
        for point in test_points_below:
            accessible = True
            for placed_carpet in all_placed:
                if hasattr(placed_carpet, "polygon") and placed_carpet.polygon.contains(
                    Point(point)
                ):
                    accessible = False
                    break
            if accessible:
                accessible_count += 1

        accessibility_ratio = accessible_count / len(test_points_below)
    else:
        accessibility_ratio = 1.0

    # 3. Vertical space efficiency
    carpet_height = bounds[3] - bounds[1]
    remaining_height = sheet_height - carpet_height
    height_efficiency = remaining_height / sheet_height if sheet_height > 0 else 0

    # 4. Check if carpet creates "overhangs" that could trap space
    # Simple heuristic: if carpet is much wider than tall, it might create better base
    aspect_ratio = (bounds[2] - bounds[0]) / carpet_height if carpet_height > 0 else 1
    base_quality = min(aspect_ratio / 2.0, 1.0)  # Cap at 1.0

    # 5. Bottom placement preference (being close to bottom edge of sheet)
    bottom_distance = bounds[1]
    bottom_bonus = max(0, (100 - bottom_distance) / 100) if bottom_distance < 100 else 0

    # Weighted combination
    tetris_score = (
        fill_ratio * 0.25
        + accessibility_ratio * 0.35  # Most important - future space
        + height_efficiency * 0.2
        + base_quality * 0.1
        + bottom_bonus * 0.1
    )

    # Convert to bonus (scale to meaningful range for shape_bonus)
    bonus = int(tetris_score * 10000)  # Scale to compete with other bonuses

    return bonus


def find_super_dense_position(
    polygon: Polygon, obstacles: list[Polygon], sheet_width: float, sheet_height: float
) -> tuple[float | None, float | None]:
    """REVOLUTIONARY: Maximum density placement using exhaustive multi-strategy search."""
    bounds = polygon.bounds
    poly_width = bounds[2] - bounds[0]
    poly_height = bounds[3] - bounds[1]

    # Strategy 1: SMART grid search - adaptive step based on polygon size and existing density
    polygon_area = poly_width * poly_height

    # Adaptive step: smaller for small polygons, larger for big ones
    if polygon_area < 5000:  # Small carpet
        step = 1.0  # Увеличили с 0.5 для ускорения
    elif polygon_area < 20000:  # Medium carpet
        step = 1.0
    else:  # Large carpet
        step = 2.0

    # Limit search area based on existing obstacles to avoid empty regions
    occupied_regions = []
    if obstacles:
        for obs in obstacles:
            obs_bounds = obs.bounds
            occupied_regions.append(obs_bounds)

    # Search in expanding rings from bottom-left
    max_candidates = 2000  # Reasonable limit
    tested = 0

    for ring in range(20):  # Maximum 20 rings
        ring_step = step * (1 + ring * 0.5)  # Coarser at distance

        # Bottom edge of ring
        for x in np.arange(
            0, min(sheet_width - poly_width, ring * 50) + ring_step, ring_step
        ):
            y = ring * 10
            if y > sheet_height - poly_height:
                break

            x_offset = x - bounds[0]
            y_offset = y - bounds[1]
            test_polygon = translate_polygon(polygon, x_offset, y_offset)

            # Quick bounds check
            test_bounds = test_polygon.bounds
            if (
                test_bounds[0] >= -0.01
                and test_bounds[1] >= -0.01
                and test_bounds[2] <= sheet_width + 0.01
                and test_bounds[3] <= sheet_height + 0.01
            ):
                # Collision check
                collision = False
                for obstacle in obstacles:
                    if check_collision(test_polygon, obstacle, min_gap=0.1):
                        collision = True
                        break

                if not collision:
                    return x, y

            tested += 1
            if tested > max_candidates:
                break

        if tested > max_candidates:
            break

    return None, None


def find_enhanced_contour_following_position(
    polygon: Polygon, obstacles: list[Polygon], sheet_width: float, sheet_height: float
) -> tuple[float | None, float | None]:
    """Enhanced contour following - ALL obstacles, more positions."""
    bounds = polygon.bounds
    poly_width = bounds[2] - bounds[0]
    poly_height = bounds[3] - bounds[1]

    candidates = []

    # Strategy 1: Follow obstacle contours (limit for performance)
    for obstacle in obstacles[: min(len(obstacles), 10)]:  # Reasonable limit
        if hasattr(obstacle.exterior, "coords"):
            contour_points = list(obstacle.exterior.coords)

            # Much denser sampling along contour
            for i, (cx, cy) in enumerate(contour_points[:-1]):
                # More test positions around each contour point
                test_positions = [
                    # Right side positions (multiple heights)
                    (cx + 0.05, cy - poly_height + 0.05),
                    (cx + 0.05, cy - poly_height / 2),
                    (cx + 0.05, cy),
                    (cx + 0.05, cy + 0.05),
                    # Left side positions
                    (cx - poly_width - 0.05, cy - poly_height + 0.05),
                    (cx - poly_width - 0.05, cy - poly_height / 2),
                    (cx - poly_width - 0.05, cy),
                    (cx - poly_width - 0.05, cy + 0.05),
                    # Above positions (multiple widths)
                    (cx - poly_width + 0.05, cy + 0.05),
                    (cx - poly_width / 2, cy + 0.05),
                    (cx, cy + 0.05),
                    (cx + 0.05, cy + 0.05),
                    # Below positions
                    (cx - poly_width + 0.05, cy - poly_height - 0.05),
                    (cx - poly_width / 2, cy - poly_height - 0.05),
                    (cx, cy - poly_height - 0.05),
                    (cx + 0.05, cy - poly_height - 0.05),
                ]

                for test_x, test_y in test_positions:
                    if (
                        0 <= test_x <= sheet_width - poly_width
                        and 0 <= test_y <= sheet_height - poly_height
                    ):
                        candidates.append((test_x, test_y))

    # Strategy 2: Sheet edges with very fine step
    fine_step = 0.05
    for x in np.arange(0, sheet_width - poly_width + fine_step, fine_step):
        candidates.append((x, 0))  # Bottom edge
        if sheet_height - poly_height > 0:
            candidates.append((x, sheet_height - poly_height))  # Top edge

    for y in np.arange(0, sheet_height - poly_height + fine_step, fine_step):
        candidates.append((0, y))  # Left edge
        if sheet_width - poly_width > 0:
            candidates.append((sheet_width - poly_width, y))  # Right edge

    # Remove duplicates and sort by preference (bottom-left first)
    candidates = list(set(candidates))
    candidates.sort(key=lambda pos: (pos[1], pos[0]))

    # Test each position
    for x, y in candidates[:2000]:  # Reasonable limit for performance
        x_offset = x - bounds[0]
        y_offset = y - bounds[1]
        test_polygon = translate_polygon(polygon, x_offset, y_offset)

        # Bounds check
        test_bounds = test_polygon.bounds
        if (
            test_bounds[0] < -0.01
            or test_bounds[1] < -0.01
            or test_bounds[2] > sheet_width + 0.01
            or test_bounds[3] > sheet_height + 0.01
        ):
            continue

        # Collision check
        collision = False
        for obstacle in obstacles:
            if check_collision(test_polygon, obstacle, min_gap=1.0):  # Увеличили для предотвращения пересечений
                collision = True
                break

        if not collision:
            return x, y

    return None, None


def find_ultra_tight_position(
    polygon: Polygon, obstacles: list[Polygon], sheet_width: float, sheet_height: float
) -> tuple[float | None, float | None]:
    """Find ultra-tight position using ENHANCED maximum density algorithm."""

    # Try new SUPER DENSE algorithm first
    result = find_super_dense_position(polygon, obstacles, sheet_width, sheet_height)
    if result[0] is not None:
        return result

    # Try enhanced contour-following algorithm
    result = find_enhanced_contour_following_position(
        polygon, obstacles, sheet_width, sheet_height
    )
    if result[0] is not None:
        return result

    # Fallback to grid-based approach
    bounds = polygon.bounds
    poly_width = bounds[2] - bounds[0]
    poly_height = bounds[3] - bounds[1]

    # Use adaptive grid size - finer for smaller polygons
    polygon_size = poly_width * poly_height
    small_polygon = polygon_size < 10000  # 100mm x 100mm

    if small_polygon:
        step_size = 0.5  # Very fine grid for small polygons
    elif len(obstacles) <= 5:
        step_size = 1.0
    else:
        step_size = 2.0

    candidates = []

    # Grid search with adaptive limits (reduced for performance)
    max_candidates = 800 if small_polygon else 400

    for x in np.arange(0, sheet_width - poly_width + 1, step_size):
        for y in np.arange(0, sheet_height - poly_height + 1, step_size):
            candidates.append((x, y))
            if len(candidates) >= max_candidates:
                break
        if len(candidates) >= max_candidates:
            break

    # Test positions using pure geometric collision detection
    for x, y in candidates:
        x_offset = x - bounds[0]
        y_offset = y - bounds[1]
        test_polygon = translate_polygon(polygon, x_offset, y_offset)

        # CRITICAL FIX: Check sheet boundaries first
        test_bounds = test_polygon.bounds
        if (
            test_bounds[0] < -0.1
            or test_bounds[1] < -0.1
            or test_bounds[2] > sheet_width + 0.1
            or test_bounds[3] > sheet_height + 0.1
        ):
            continue

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
    poly_width = bounds[2] - bounds[0]
    poly_height = bounds[3] - bounds[1]

    # Try positions along bottom and left edges first
    candidate_positions = []

    # ADAPTIVE STEP: Fine grid for small polygons, coarse for large ones
    polygon_size = poly_width * poly_height
    is_small = polygon_size < 10000  # 100mm x 100mm

    grid_step = 2.0 if is_small else 15  # Fine step for small polygons

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
            if check_collision(test_polygon, obstacle, min_gap=0.1):
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
            if (
                test_bounds[0] < 0
                or test_bounds[1] < 0
                or test_bounds[2] > sheet_width
                or test_bounds[3] > sheet_height
            ):
                continue

            # CRITICAL FIX: Use proper collision detection with minimum gap
            collision = False
            for placed_poly in placed_polygons:
                if check_collision(
                    test_polygon, placed_poly.polygon, min_gap=2.0
                ):  # 2mm minimum gap
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
                if check_collision(
                    test_polygon, placed_poly.polygon, min_gap=2.0
                ):  # 2mm minimum gap
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

    # ENHANCED BIG-TO-SMALL STRATEGY: Large carpets first, then progressively smaller
    # This creates better foundation for Tetris-style falling behavior
    def get_enhanced_smart_score(carpet: Carpet):
        bounds = carpet.polygon.bounds
        area = carpet.polygon.area
        width = bounds[2] - bounds[0]
        height = bounds[3] - bounds[1]

        # PRIMARY: Area is the most important factor (bigger first)
        area_score = area * 1000000  # Scale up area significantly

        # SECONDARY: Prefer shapes that are easier to place around (wider is better for foundation)
        width_bonus = width * 1000  # Bonus for width (good for bottom layer)

        # TERTIARY: Slight penalty for very tall narrow shapes (harder to fill around)
        aspect_ratio = width / height if height > 0 else 1
        if aspect_ratio < 0.3:  # Very tall narrow shapes
            narrow_penalty = 50000  # Small penalty
        else:
            narrow_penalty = 0

        return area_score + width_bonus - narrow_penalty

    # Sort by enhanced strategy: largest areas with good foundation potential first
    smart_sorted = sorted(carpets, key=get_enhanced_smart_score, reverse=True)

    # Use enhanced bin packing with tighter gap settings
    placed, unplaced = bin_packing(smart_sorted, sheet_size, verbose=verbose)

    return placed, unplaced


def try_simple_placement(
    carpet: Carpet, existing_placed: list[PlacedCarpet], sheet_size: tuple[float, float]
) -> PlacedCarpet | None:
    """ULTRA-AGGRESSIVE placement with TETRIS QUALITY evaluation."""
    import shapely.affinity

    # Convert sheet size from cm to mm
    sheet_width_mm, sheet_height_mm = sheet_size[0] * 10, sheet_size[1] * 10

    # Get existing obstacles
    obstacles = [placed.polygon for placed in existing_placed]

    # Initialize candidates list
    candidates = []

    # Try multiple approaches for maximum space utilization
    placement_strategies = [
        {
            "step": 10,
            "rotations": [0, 90, 180, 270],
        },  # Увеличен шаг с 5 до 10мм для ускорения
    ]

    # Cache rotation results to avoid repeated calculations
    rotation_cache = {}

    for strategy in placement_strategies:
        step: int = strategy["step"]
        rotations = strategy["rotations"]

        # Try different rotations
        for angle in rotations:
            # Use cached rotation
            if angle not in rotation_cache:
                rotation_cache[angle] = get_cached_rotation(carpet, angle)
            rotated_polygon = rotation_cache[angle]

            bounds = rotated_polygon.bounds
            poly_width = bounds[2] - bounds[0]
            poly_height = bounds[3] - bounds[1]

            # Skip if doesn't fit in sheet
            if poly_width > sheet_width_mm or poly_height > sheet_height_mm:
                continue

            # BOTTOM-LEFT FIRST approach for maximum compaction
            for y in range(0, int(sheet_height_mm - poly_height + 1), step):
                for x in range(0, int(sheet_width_mm - poly_width + 1), step):
                    # Move polygon to position
                    dx = x - bounds[0]
                    dy = y - bounds[1]
                    positioned_polygon = shapely.affinity.translate(
                        rotated_polygon, dx, dy
                    )

                    # Check if it fits in sheet
                    pos_bounds = positioned_polygon.bounds
                    if (
                        pos_bounds[0] >= 0
                        and pos_bounds[1] >= 0
                        and pos_bounds[2] <= sheet_width_mm
                        and pos_bounds[3] <= sheet_height_mm
                    ):
                        # Check for collisions with existing polygons
                        has_collision = False
                        for obstacle in obstacles:
                            if positioned_polygon.intersects(obstacle):
                                intersection = positioned_polygon.intersection(obstacle)
                                if (
                                    hasattr(intersection, "area")
                                    and intersection.area > 0.1
                                ):  # Ultra-tight packing
                                    has_collision = True
                                    break

                        if not has_collision:
                            # For Priority 2, take first valid position for speed
                            # Calculate correct offsets from original position
                            original_bounds = carpet.polygon.bounds
                            final_x_offset = dx + (original_bounds[0] - bounds[0])
                            final_y_offset = dy + (original_bounds[1] - bounds[1])

                            return PlacedCarpet(
                                polygon=positioned_polygon,
                                x_offset=final_x_offset,
                                y_offset=final_y_offset,
                                angle=angle,
                                filename=carpet.filename,
                                color=carpet.color,
                                order_id=carpet.order_id,
                                carpet_id=carpet.carpet_id,
                                priority=carpet.priority,
                            )

    return None  # No valid placement found


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
    if progress_callback:
        progress_callback(
            5,
            "Подготовка ковров к раскладке...",
        )

    clear_optimization_caches()

    # ВАЖНО: Кэшируем оригинальные полигоны ДО любых трансформаций
    cache_original_polygons(carpets)

    placed_sheets: list[PlacedSheet] = []
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

    num_priority2_total = len(priority2_carpets)

    priority1_max_progress = 70 if priority2_carpets else 100

    logger.info(
        f"Группировка завершена: {len(priority1_carpets)} приоритет 1 + Excel, {len(priority2_carpets)} приоритет 2"
    )

    # Early return if nothing to place
    if not priority1_carpets and not priority2_carpets:
        logger.info("Нет полигонов для размещения")
        return placed_sheets, all_unplaced

    # STEP 2: Place priority 1 items (Excel orders + manual priority 1) with new sheets allowed
    logger.info(
        f"\n=== ЭТАП 2: РАЗМЕЩЕНИЕ {len(priority1_carpets)} ПРИОРИТЕТ 1 + EXCEL ЗАКАЗОВ ==="
    )

    # Group priority 1 carpets by color for efficient processing
    remaining_priority1: list[Carpet] = list(priority1_carpets)

    for layout_idx, layout in enumerate(placed_sheets):
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
                placed_sheets[layout_idx].placed_polygons.extend(additional_placed)
                placed_sheets[layout_idx].usage_percent = calculate_usage_percent(
                    placed_sheets[layout_idx].placed_polygons, layout.sheet_size
                )

                # Update remaining
                remaining_carpet_map = {
                    UnplacedCarpet.from_carpet(c): c for c in matching_carpets
                }
                newly_remaining = set(
                    remaining_carpet_map[remaining_carpet]
                    for remaining_carpet in remaining_unplaced
                    if remaining_carpet in remaining_carpet_map
                )

                # Remove placed carpets from remaining list
                placed_carpet_set = set(
                    c for c in matching_carpets if c not in newly_remaining
                )
                remaining_priority1 = [
                    c for c in remaining_priority1 if c not in placed_carpet_set
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
        if remaining_carpets and placed_sheets:
            logger.info(
                f"Попытка агрессивного дозаполнения существующих листов для {len(remaining_carpets)} ковров {color}"
            )

            # Try each existing sheet again with more relaxed criteria
            for layout_idx, layout in enumerate(placed_sheets):
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
                        UnplacedCarpet.from_carpet(c): c for c in matching_carpets
                    }

                    for attempt in range(4):  # Try 4 different enhanced orderings
                        if attempt == 1:
                            # Enhanced big-to-small strategy (best for foundation)
                            def get_foundation_score(carpet: Carpet):
                                bounds = carpet.polygon.bounds
                                area = carpet.polygon.area
                                width = bounds[2] - bounds[0]
                                return (
                                    area * 1000 + width
                                )  # Prioritize large + wide shapes

                            test_carpets = sorted(
                                matching_carpets, key=get_foundation_score, reverse=True
                            )
                        elif attempt == 2:
                            # Small-to-large strategy (good for filling gaps)
                            test_carpets = sorted(
                                matching_carpets, key=lambda c: c.polygon.area
                            )
                        elif attempt == 3:
                            # Width-prioritized sorting (good for horizontal filling)
                            def get_width_score(carpet: Carpet):
                                bounds = carpet.polygon.bounds
                                width = bounds[2] - bounds[0]
                                area = carpet.polygon.area
                                return width * 1000 + area  # Width first, then area

                            test_carpets = sorted(
                                matching_carpets, key=get_width_score, reverse=True
                            )
                        else:
                            # Default order (original)
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
                                        polygon=rt.polygon,
                                        carpet_id=rt.carpet_id,
                                        priority=rt.priority,
                                        filename=rt.filename,
                                        color=rt.color,
                                        order_id=rt.order_id,
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
                                        polygon=rt.polygon,
                                        carpet_id=rt.carpet_id,
                                        priority=rt.priority,
                                        filename=rt.filename,
                                        color=rt.color,
                                        order_id=rt.order_id,
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
                                    new_poly, existing_poly, min_gap=1.0  # Увеличили для предотвращения пересечений
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
                            placed_sheets[layout_idx].placed_polygons.extend(
                                best_placed
                            )
                            placed_sheets[
                                layout_idx
                            ].usage_percent = calculate_usage_percent(
                                placed_sheets[layout_idx].placed_polygons,
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
                all_unplaced.extend(
                    UnplacedCarpet.from_carpet(carpet) for carpet in remaining_carpets
                )
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
                placed_sheets.append(new_layout)

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
                        priority1_max_progress,
                        int(
                            priority1_max_progress * len(placed_sheets) / (len(carpets))
                        ),
                    )
                    progress_callback(
                        progress,
                        f"Создан лист #{sheet_counter}. Размещено ковров: {len(placed)}",
                    )
            else:
                logger.warning(
                    f"Не удалось разместить приоритет 1 на новом листе {color}"
                )
                all_unplaced.extend(
                    UnplacedCarpet.from_carpet(carpet) for carpet in remaining_carpets
                )
                sheet_type["used"] -= 1
                sheet_counter -= 1
                break

    # STEP 3: Place priority 2 on remaining space only (no new sheets)
    logger.info(
        f"\n=== ЭТАП 3: РАЗМЕЩЕНИЕ {len(priority2_carpets)} ПРИОРИТЕТ2 НА СВОБОДНОМ МЕСТЕ ==="
    )

    remaining_priority2: list[Carpet] = list(priority2_carpets)
    placed_sheets, all_unplaced = place_priority2(
        num_priority2_total,
        remaining_priority2,
        placed_sheets,
        all_unplaced,
        progress_callback,
    )

    # STEP 4: Sort sheets by color (group black together, then grey)
    logger.info("\n=== ЭТАП 7: ГРУППИРОВКА ЛИСТОВ ПО ЦВЕТАМ ===")

    # Separate black and grey sheets, maintain relative order within each color
    black_sheets = []
    grey_sheets = []

    for layout in placed_sheets:
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

    placed_sheets = final_layouts

    logger.info(
        f"Перегруппировка завершена: {len(black_sheets)} черных + {len(grey_sheets)} серых = {len(placed_sheets)} листов"
    )

    # Final logging and progress
    logger.info("\n=== ИТОГИ РАЗМЕЩЕНИЯ ===")
    logger.info(f"Всего листов создано: {len(placed_sheets)}")
    logger.info(f"Неразмещенных полигонов: {len(all_unplaced)}")

    if verbose:
        st.info(
            f"Размещение завершено: {len(placed_sheets)} листов, {len(all_unplaced)} не размещено"
        )

    if progress_callback:
        progress_callback(100, f"Завершено: {len(placed_sheets)} листов создано")

    return placed_sheets, all_unplaced


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
                polygon=new_poly,
                carpet_id=item.carpet_id,
                priority=item.priority,
                x_offset=new_x_off,
                y_offset=new_y_off,
                angle=item.angle,
                filename=item.filename,
                color=item.color,
                order_id=item.order_id,
            )
        )

    return new_placed


def tighten_layout(
    placed: list[PlacedCarpet],
    sheet_size=None,
    min_gap: float = 0.05,  # ULTRA-tight gap for maximum density
    step: float = 0.5,  # Finer step for better precision
    max_passes: int = 4,  # Reduced passes for better performance
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
            [(-step / 2, -step / 2), (-step, 0), (0, -step)],  # diagonal, left, down
        ]

        # Use different strategy each pass for better convergence
        strategy = strategies[pass_idx % len(strategies)]

        # Process polygons in different orders for better optimization
        order_strategies = [
            range(n),  # Normal order
            range(n - 1, -1, -1),  # Reverse order
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
                    if (
                        test.bounds[0] < -0.001
                        or test.bounds[1] < -0.001
                        or (sheet_size and test.bounds[2] > sheet_size[0] * 10 + 0.001)
                        or (sheet_size and test.bounds[3] > sheet_size[1] * 10 + 0.001)
                    ):
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
                    potential_y_move = -min(
                        bounds[1], step * 3
                    )  # Move up to 3 steps toward bottom
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
                    potential_x_move = -min(
                        bounds[0], step * 3
                    )  # Move up to 3 steps toward left
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
                polygon=new_poly,
                carpet_id=item.carpet_id,
                priority=item.priority,
                x_offset=new_x_off,
                y_offset=new_y_off,
                angle=item.angle,
                filename=item.filename,
                color=item.color,
                order_id=item.order_id,
            )
        )

    return new_placed


def place_priority2(
    num_priority2_total: int,
    remaining_priority2: list[Carpet],
    placed_layouts: list[PlacedSheet],
    all_unplaced: list[UnplacedCarpet],
    progress_callback=None,  # Callback function for progress updates
) -> tuple[list[PlacedSheet], list[UnplacedCarpet]]:
    # Sort layouts by increasing usage percent to fill emptier sheets first
    sorted_layouts = sorted(placed_layouts, key=lambda l: l.usage_percent)

    total_priority2_placed = 0

    for layout in sorted_layouts:
        if not remaining_priority2:
            break
        if layout.usage_percent >= 99:  # Skip almost full sheets
            continue

        # Get and sort matching carpets by decreasing area
        matching_carpets = sorted(
            [c for c in remaining_priority2 if c.color == layout.sheet_color],
            key=lambda c: c.polygon.area,
            reverse=True,
        )
        if not matching_carpets:
            logger.info(
                f"Лист #{layout.sheet_number}: нет совпадающих ковров приоритета 2 по цвету {layout.sheet_color}"
            )
            continue

        logger.info(
            f"Лист #{layout.sheet_number} ({layout.usage_percent:.1f}% заполнен): пытаемся разместить {len(matching_carpets)} ковров приоритета 2"
        )

        try:
            additional_placed = []
            current_placed = list(layout.placed_polygons)  # Copy current placements

            for carpet in matching_carpets:
                # Try simple placement for each carpet individually
                placed = try_simple_placement(carpet, current_placed, layout.sheet_size)
                if placed:
                    additional_placed.append(placed)
                    total_priority2_placed += 1
                    current_placed.append(placed)  # Update current for next placements
                    logger.info(f"  ✅ Ковер {carpet.filename} размещен успешно")
                    if progress_callback:
                        progress = 70 + int(
                            100 * total_priority2_placed / num_priority2_total * 0.3
                        )
                        progress_callback(
                            progress,
                            f"Размещение ковров приоритета 2: {total_priority2_placed}/{num_priority2_total}",
                        )
                else:
                    logger.info(f"  ❌ Ковер {carpet.filename} не размещен")

            if additional_placed:
                # Optimized overlap check - check only once per new item
                has_overlap = False
                existing_polygons = [p.polygon for p in layout.placed_polygons]

                for new in additional_placed:
                    # Use any() for early exit
                    overlapping_polys = [
                        existing
                        for existing in existing_polygons
                        if new.polygon.intersects(existing)
                    ]

                    if overlapping_polys:
                        # Check actual intersection area only for intersecting polygons
                        for existing in overlapping_polys:
                            inter = new.polygon.intersection(existing)
                            if hasattr(inter, "area") and inter.area > 1:
                                has_overlap = True
                                logger.warning(
                                    f"Перекрытие при размещении приоритета 2: {inter.area:.1f} мм² на листе #{layout.sheet_number}"
                                )
                                break
                    if has_overlap:
                        break

                if not has_overlap:
                    # Update the layout
                    layout.placed_polygons.extend(additional_placed)
                    layout.usage_percent = calculate_usage_percent(
                        layout.placed_polygons, layout.sheet_size
                    )
                    # Remove placed carpets from remaining_priority2
                    placed_ids = set(
                        (p.filename, p.color, p.order_id) for p in additional_placed
                    )
                    remaining_priority2 = [
                        c
                        for c in remaining_priority2
                        if (c.filename, c.color, c.order_id) not in placed_ids
                    ]
                    logger.info(
                        f"    Дозаполнен лист #{layout.sheet_number}: +{len(additional_placed)} приоритет2, осталось {len(remaining_priority2)}"
                    )
                else:
                    logger.warning(
                        f"Отклонено размещение приоритета 2 из-за перекрытий на листе #{layout.sheet_number}"
                    )
        except Exception as e:
            logger.debug(f"Не удалось дозаполнить лист приоритетом 2: {e}")
            continue

    # Add any remaining priority 2 to unplaced (no new sheets allowed for priority 2)
    if remaining_priority2:
        logger.info(
            f"Остается неразмещенными {len(remaining_priority2)} приоритет2 (новые листы не создаются)"
        )
        all_unplaced.extend(
            UnplacedCarpet.from_carpet(carpet) for carpet in remaining_priority2
        )

    return placed_layouts, all_unplaced
