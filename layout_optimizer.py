"""Helper functions for EVA mat nesting optimization."""

# Version for cache busting
__version__ = "1.5.0"

import numpy as np
import time

from shapely.geometry import Polygon, Point
import logging

from carpet import Carpet, PlacedCarpet, UnplacedCarpet, PlacedSheet
from geometry_utils import translate_polygon, rotate_polygon
from fast_geometry import (
    SpatialIndexCache,
    check_collision_fast_indexed_intersects_only,
    batch_check_collisions_cached_fast,
)

# Настройка логирования
logger = logging.getLogger(__name__)

# OPTIMIZATION: Global STRtree cache for fast collision detection
_global_spatial_cache = SpatialIndexCache()

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
            _original_polygons[carpet_id] = Polygon(carpet.polygon.exterior.coords)


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


def calculate_optimal_rotation_angles(
    polygon: Polygon, angle_step: int = 5
) -> list[float]:
    """
    🎯 ОПТИМАЛЬНЫЕ УГЛЫ ПОВОРОТА: Вычисляет углы, которые максимизируют плотность упаковки.

    Стратегия:
    1. Находит минимальный ограничивающий прямоугольник (minimum bounding rectangle)
    2. Определяет угол наклона этого прямоугольника
    3. Возвращает ПРИОРИТЕТНЫЕ углы: стандартные + оптимальные для формы

    Args:
        polygon: Shapely Polygon для анализа
        angle_step: Шаг углов для тестирования (по умолчанию 5°)

    Returns:
        Список оптимальных углов поворота, отсортированных по приоритету
    """
    from shapely import minimum_rotated_rectangle
    import math

    # Получаем минимальный ограничивающий прямоугольник
    min_rect = minimum_rotated_rectangle(polygon)

    # Извлекаем координаты углов прямоугольника
    coords = list(min_rect.exterior.coords)

    # Вычисляем угол наклона первой стороны прямоугольника
    dx = coords[1][0] - coords[0][0]
    dy = coords[1][1] - coords[0][1]
    angle_rad = math.atan2(dy, dx)
    angle_deg = math.degrees(angle_rad)

    # Нормализуем угол к диапазону [0, 90) так как прямоугольник симметричен
    angle_deg = angle_deg % 90

    # ПРИОРИТЕТНАЯ СТРАТЕГИЯ: Ограничиваем количество углов для скорости
    angles = []

    # 1. ВЫСОКИЙ ПРИОРИТЕТ: Стандартные углы (0°, 90°, 180°, 270°)
    standard_angles = [0, 90, 180, 270]
    angles.extend(standard_angles)

    # 2. ВЫСОКИЙ ПРИОРИТЕТ: Оптимальные углы на основе формы ковра
    optimal_angle_1 = -angle_deg  # Поворот для выравнивания по горизонтали
    optimal_angle_2 = 90 - angle_deg  # Поворот для выравнивания по вертикали

    # Проверяем, насколько оптимальные углы отличаются от стандартных
    # Если отличие меньше 3°, не добавляем (избыточно)
    for opt_angle in [optimal_angle_1, optimal_angle_2]:
        norm_angle = opt_angle % 360
        # Проверяем, не слишком ли близко к уже добавленным углам
        is_unique = all(
            abs(norm_angle - existing) > 3 and abs(norm_angle - existing - 360) > 3
            for existing in angles
        )
        if (
            is_unique and abs(angle_deg) > 3
        ):  # Только если форма действительно наклонена
            angles.append(norm_angle)
            # Добавляем эти углы со всех 4 сторон
            for base_rotation in [0, 90, 180, 270]:
                rotated = (norm_angle + base_rotation) % 360
                if all(abs(rotated - existing) > 3 for existing in angles):
                    angles.append(rotated)

    # 3. СРЕДНИЙ ПРИОРИТЕТ: Небольшие вариации оптимальных углов
    # Только если форма значительно наклонена (> 10°)
    if abs(angle_deg) > 10:
        for base in [optimal_angle_1, optimal_angle_2]:
            for delta in [-angle_step, angle_step]:
                varied_angle = (base + delta) % 360
                if all(abs(varied_angle - existing) > 3 for existing in angles):
                    angles.append(varied_angle)

    # 4. НИЗКИЙ ПРИОРИТЕТ: Промежуточные углы (только для очень нестандартных форм)
    # Добавляем только если форма ОЧЕНЬ наклонена (> 20°) и отличается от стандартной
    if abs(angle_deg) > 20:
        # Добавляем углы с шагом 15° в диапазоне ±30° от оптимального
        for opt_angle in [optimal_angle_1, optimal_angle_2]:
            for additional_angle in range(-30, 31, 15):
                test_angle = (opt_angle + additional_angle) % 360
                if all(abs(test_angle - existing) > 3 for existing in angles):
                    angles.append(test_angle)

    # Убираем дубликаты и сортируем
    # ВАЖНО: Приоритет - стандартные углы идут первыми
    angles = sorted(set(round(a, 1) for a in angles))

    # Переупорядочиваем: стандартные углы (0,90,180,270) в начало
    standard_set = set(standard_angles)
    priority_angles = [a for a in angles if a in standard_set]
    other_angles = [a for a in angles if a not in standard_set]

    return priority_angles + other_angles


def analyze_edge_straightness(polygon: Polygon) -> dict:
    """
    📏 АНАЛИЗ ПРЯМОЛИНЕЙНОСТИ КРАЁВ: Определяет, какие края ковра наиболее прямые.

    Возвращает словарь с информацией о краях:
    - straightest_edge_angle: угол наиболее прямого края
    - straightness_score: оценка прямолинейности (0-1, где 1 = идеально прямой)
    """
    import math

    coords = list(polygon.exterior.coords)
    if len(coords) < 3:
        return {"straightest_edge_angle": 0, "straightness_score": 0}

    # Анализируем каждый край полигона
    edge_info = []

    for i in range(len(coords) - 1):
        p1 = coords[i]
        p2 = coords[i + 1]

        # Длина края
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        length = math.sqrt(dx * dx + dy * dy)

        if length < 1:  # Игнорируем очень короткие края
            continue

        # Угол края
        angle = math.degrees(math.atan2(dy, dx))

        edge_info.append({"length": length, "angle": angle, "start": p1, "end": p2})

    if not edge_info:
        return {"straightest_edge_angle": 0, "straightness_score": 0}

    # Находим самый длинный край (обычно он наиболее важен для стыковки)
    longest_edge = max(edge_info, key=lambda e: e["length"])

    # Оценка прямолинейности = отношение длины к периметру
    straightness = longest_edge["length"] / polygon.length

    return {
        "straightest_edge_angle": longest_edge["angle"],
        "straightness_score": straightness,
        "longest_edge_length": longest_edge["length"],
    }


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
    max_movements = len(gravity_carpets) // 2

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


def apply_aggressive_gravity(
    placed_carpets: list[PlacedCarpet],
    sheet_width_mm: float,
    sheet_height_mm: float,
    max_iterations: int = 10,
) -> list[PlacedCarpet]:
    """
    🎯 АГРЕССИВНАЯ ГРАВИТАЦИЯ: Опускает ВСЕ ковры максимально вниз.

    Стратегия:
    1. Сортирует ковры снизу вверх (нижние не двигаются, верхние падают)
    2. Для каждого ковра находит самую низкую возможную позицию
    3. Повторяет несколько итераций для максимальной плотности

    Args:
        placed_carpets: Размещённые ковры
        sheet_width_mm: Ширина листа
        sheet_height_mm: Высота листа
        max_iterations: Максимальное количество итераций

    Returns:
        Ковры после применения гравитации
    """
    if not placed_carpets:
        return placed_carpets

    # Создаем копии
    result = []
    for carpet in placed_carpets:
        result.append(
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

    # Итеративно применяем гравитацию
    for iteration in range(max_iterations):
        any_movement = False
        logger.info(
            f"   Вертикальная гравитация - итерация {iteration + 1}/{max_iterations}"
        )

        # Сортируем по Y (снизу вверх) - нижние сначала, они стабильны
        result.sort(key=lambda c: c.polygon.bounds[1])

        # Пытаемся опустить каждый ковёр
        for i, carpet in enumerate(result):
            current_bounds = carpet.polygon.bounds
            current_bottom_y = current_bounds[1]

            # Если уже на дне, пропускаем
            if current_bottom_y < 1:
                logger.debug(f"     Ковёр {i} уже на дне (Y={current_bottom_y:.1f})")
                continue

            # Препятствия = все остальные ковры
            obstacles = [other.polygon for j, other in enumerate(result) if j != i]

            # Ищем самую низкую позицию без коллизий
            # Начинаем с Y=0 и двигаемся вверх, пока не найдём свободное место
            best_y = current_bottom_y

            # ПРАВИЛЬНАЯ СТРАТЕГИЯ: Ищем САМУЮ НИЗКУЮ позицию
            # Начинаем с текущей позиции и двигаемся ВНИЗ, пока не найдём препятствие
            # Последняя позиция без коллизии = самая низкая возможная позиция

            # Шаг 1: Грубый поиск сверху вниз (шаг 5мм для баланса скорости и точности)
            coarse_step = 5
            best_y = current_bottom_y

            # Идём от текущей позиции вниз до Y=0
            for test_y in range(int(current_bottom_y), -1, -coarse_step):
                y_shift = test_y - current_bounds[1]
                test_polygon = translate_polygon(carpet.polygon, 0, y_shift)

                test_bounds = test_polygon.bounds
                if test_bounds[1] < -0.1 or test_bounds[3] > sheet_height_mm + 0.1:
                    break  # Вышли за границы листа

                has_collision = False
                for obstacle in obstacles:
                    if check_collision(test_polygon, obstacle, min_gap=10.0):
                        has_collision = True
                        break

                if not has_collision:
                    # Эта позиция валидна, запоминаем и продолжаем спускаться
                    best_y = test_y
                else:
                    # Нашли коллизию, останавливаемся (предыдущая позиция была самой низкой)
                    break

            # Шаг 2: Точный поиск в диапазоне (best_y, best_y + coarse_step) (шаг 1мм)
            # Проверяем промежуточные позиции, которые могли пропустить в грубом поиске
            if best_y < current_bottom_y:
                search_start = int(best_y + coarse_step)
                search_end = int(best_y) - 1

                # Идём от более высокой позиции к best_y
                for test_y in range(search_start, search_end, -1):
                    y_shift = test_y - current_bounds[1]
                    test_polygon = translate_polygon(carpet.polygon, 0, y_shift)

                    test_bounds = test_polygon.bounds
                    if test_bounds[1] < -0.1 or test_bounds[3] > sheet_height_mm + 0.1:
                        continue

                    has_collision = False
                    for obstacle in obstacles:
                        if check_collision(test_polygon, obstacle, min_gap=10.0):
                            has_collision = True
                            break

                    if not has_collision:
                        best_y = test_y
                    else:
                        break  # Нашли коллизию, останавливаемся

            # Применяем перемещение если есть улучшение
            if best_y < current_bottom_y - 0.1:  # Хотя бы 0.1мм улучшения
                y_shift = best_y - current_bounds[1]
                movement = current_bottom_y - best_y
                logger.info(
                    f"     ✓ Ковёр {i}: опущен на {movement:.1f}мм (Y={current_bottom_y:.1f} → {best_y:.1f})"
                )
                carpet.polygon = translate_polygon(carpet.polygon, 0, y_shift)
                carpet.y_offset += y_shift
                any_movement = True
            else:
                logger.debug(
                    f"     Ковёр {i}: не может опуститься ниже (best_y={best_y:.1f})"
                )

        # Если ничего не двигалось, завершаем
        if not any_movement:
            logger.info("   Вертикальная гравитация: нет больше движений, завершаем")
            break

    return result


def apply_aggressive_horizontal_compaction(
    placed_carpets: list[PlacedCarpet],
    sheet_width_mm: float,
    sheet_height_mm: float,
    max_iterations: int = 10,
) -> list[PlacedCarpet]:
    """
    🎯 АГРЕССИВНАЯ ГОРИЗОНТАЛЬНАЯ КОМПРЕССИЯ: Прижимает ВСЕ ковры максимально влево.

    Стратегия:
    1. Сортирует ковры слева направо (левые не двигаются, правые сдвигаются влево)
    2. Для каждого ковра находит самую левую возможную позицию
    3. Повторяет несколько итераций для максимальной плотности

    Args:
        placed_carpets: Размещённые ковры
        sheet_width_mm: Ширина листа
        sheet_height_mm: Высота листа
        max_iterations: Максимальное количество итераций

    Returns:
        Ковры после применения горизонтальной компрессии
    """
    if not placed_carpets:
        return placed_carpets

    # Создаем копии
    result = []
    for carpet in placed_carpets:
        result.append(
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

    # Итеративно применяем горизонтальную компрессию
    for iteration in range(max_iterations):
        any_movement = False
        logger.info(
            f"   Горизонтальная компрессия - итерация {iteration + 1}/{max_iterations}"
        )

        # Сортируем по X (слева направо) - левые сначала, они стабильны
        result.sort(key=lambda c: c.polygon.bounds[0])

        # Пытаемся сдвинуть каждый ковёр влево
        for i, carpet in enumerate(result):
            current_bounds = carpet.polygon.bounds
            current_left_x = current_bounds[0]

            # Если уже у левой границы, пропускаем
            if current_left_x < 1:
                logger.debug(
                    f"     Ковёр {i} уже у левой границы (X={current_left_x:.1f})"
                )
                continue

            # Препятствия = все остальные ковры
            obstacles = [other.polygon for j, other in enumerate(result) if j != i]

            # Ищем самую левую позицию без коллизий
            best_x = current_left_x
            logger.debug(f"     Ковёр {i}: текущая позиция X={current_left_x:.1f}")

            # Шаг 1: Грубый поиск справа налево (шаг 5мм)
            coarse_step = 5

            # Идём от текущей позиции влево до X=0
            for test_x in range(int(current_left_x), -1, -coarse_step):
                x_shift = test_x - current_bounds[0]
                test_polygon = translate_polygon(carpet.polygon, x_shift, 0)

                test_bounds = test_polygon.bounds
                if test_bounds[0] < -0.1 or test_bounds[2] > sheet_width_mm + 0.1:
                    break  # Вышли за границы листа

                has_collision = False
                for obstacle in obstacles:
                    if check_collision(test_polygon, obstacle, min_gap=10.0):
                        has_collision = True
                        break

                if not has_collision:
                    # Эта позиция валидна, запоминаем и продолжаем двигаться влево
                    best_x = test_x
                else:
                    # Нашли коллизию, останавливаемся (предыдущая позиция была самой левой)
                    break

            # Шаг 2: Точный поиск в диапазоне (best_x, best_x + coarse_step) (шаг 1мм)
            if best_x < current_left_x:
                search_start = int(best_x + coarse_step)
                search_end = int(best_x) - 1

                # Идём от более правой позиции к best_x
                for test_x in range(search_start, search_end, -1):
                    x_shift = test_x - current_bounds[0]
                    test_polygon = translate_polygon(carpet.polygon, x_shift, 0)

                    test_bounds = test_polygon.bounds
                    if test_bounds[0] < -0.1 or test_bounds[2] > sheet_width_mm + 0.1:
                        continue

                    has_collision = False
                    for obstacle in obstacles:
                        if check_collision(test_polygon, obstacle, min_gap=10.0):
                            has_collision = True
                            break

                    if not has_collision:
                        best_x = test_x
                    else:
                        break  # Нашли коллизию, останавливаемся

            # Применяем перемещение если есть улучшение
            if best_x < current_left_x - 0.1:  # Хотя бы 0.1мм улучшения
                x_shift = best_x - current_bounds[0]
                movement = current_left_x - best_x
                logger.info(
                    f"     ✓ Ковёр {i}: сдвинут влево на {movement:.1f}мм (X={current_left_x:.1f} → {best_x:.1f})"
                )
                carpet.polygon = translate_polygon(carpet.polygon, x_shift, 0)
                carpet.x_offset += x_shift
                any_movement = True
            else:
                logger.debug(
                    f"     Ковёр {i}: не может сдвинуться влево (best_x={best_x:.1f})"
                )

        # Если ничего не двигалось, завершаем
        if not any_movement:
            logger.info("   Горизонтальная компрессия: нет больше движений, завершаем")
            break

    return result


def apply_combined_compaction(
    placed_carpets: list[PlacedCarpet],
    sheet_width_mm: float,
    sheet_height_mm: float,
    max_iterations: int = 5,
) -> list[PlacedCarpet]:
    """
    🎯 КОМБИНИРОВАННАЯ КОМПРЕССИЯ: Чередует вертикальную гравитацию и горизонтальную компрессию.

    Стратегия:
    1. Применяет вертикальную гравитацию (опускает вниз)
    2. Применяет горизонтальную компрессию (прижимает влево)
    3. Повторяет цикл пока есть движение

    Args:
        placed_carpets: Размещённые ковры
        sheet_width_mm: Ширина листа
        sheet_height_mm: Высота листа
        max_iterations: Максимальное количество внешних итераций

    Returns:
        Ковры после применения комбинированной компрессии
    """
    if not placed_carpets:
        return placed_carpets

    result = placed_carpets

    for iteration in range(max_iterations):
        logger.info(
            f"🔄 Комбинированная компрессия - цикл {iteration + 1}/{max_iterations}"
        )

        # Запоминаем текущие позиции для проверки движения
        before_positions = [(c.polygon.bounds[0], c.polygon.bounds[1]) for c in result]

        # Шаг 1: Вертикальная гравитация (опускаем вниз)
        result = apply_aggressive_gravity(
            result, sheet_width_mm, sheet_height_mm, max_iterations=3
        )

        # Шаг 2: Горизонтальная компрессия (прижимаем влево)
        result = apply_aggressive_horizontal_compaction(
            result, sheet_width_mm, sheet_height_mm, max_iterations=3
        )

        # Проверяем было ли движение
        after_positions = [(c.polygon.bounds[0], c.polygon.bounds[1]) for c in result]

        total_movement = sum(
            abs(before[0] - after[0]) + abs(before[1] - after[1])
            for before, after in zip(before_positions, after_positions)
        )

        logger.info(
            f"   Общее движение в цикле {iteration + 1}: {total_movement:.1f}мм"
        )

        if total_movement < 1.0:  # Меньше 1мм суммарного движения - стабилизация
            logger.info("   Компрессия стабилизировалась, завершаем")
            break

    return result


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
                if check_collision(test_polygon, obstacle, min_gap=10.0):
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


def apply_tetris_left_compaction(
    placed_carpets: list[PlacedCarpet], sheet_width_mm: float, sheet_height_mm: float
) -> list[PlacedCarpet]:
    """
    TETRIS-ФУНКЦИЯ: Сжимает ковры к левому краю для плотной упаковки.
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

    # Сортируем по расстоянию от левого края (дальние сначала)
    compacted_carpets.sort(key=lambda c: c.polygon.bounds[0], reverse=True)

    movements_made = 0
    max_movements = min(5, len(compacted_carpets))

    # Применяем сжатие к левому краю
    for i, carpet in enumerate(compacted_carpets):
        if movements_made >= max_movements:
            break

        # Препятствия = все остальные ковры
        obstacles = [
            other.polygon for j, other in enumerate(compacted_carpets) if j != i
        ]

        # Текущие границы ковра
        current_bounds = carpet.polygon.bounds
        current_left = current_bounds[0]

        if current_left <= 10:  # Уже у левого края
            continue

        # Пробуем сдвинуть влево
        best_x = current_left
        improvement_found = False

        # Шагаем влево с шагом 5мм
        for test_left_x in range(int(current_left) - 5, -1, -5):
            if test_left_x < 0:
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
                if check_collision(test_polygon, obstacle, min_gap=10.0):
                    collision = True
                    break

            if not collision:
                best_x = test_left_x
                improvement_found = True
            else:
                break  # Натолкнулись на препятствие, дальше не двигаемся

        # Применяем улучшение
        if improvement_found and best_x < current_left - 3:  # Минимум 3мм улучшения
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
                    if (
                        len(test_positions) > 15
                    ):  # Уменьшили лимит для ускорения (было 20)
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

            # Получаем оригинальный полигон для анализа
            original_polygon = rotate_polygon(
                current_carpet.polygon, -current_carpet.angle
            )  # Возвращаем к 0°

            for test_angle in [0, 90, 180, 270]:
                if test_angle == current_carpet.angle:
                    continue
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


def check_collision_with_strtree(
    polygon: Polygon, placed_polygons: list[Polygon]
) -> bool:
    """Ultra-fast collision check using CACHED STRtree spatial index."""
    if not placed_polygons:
        return False

    if not polygon.is_valid:
        return True

    # OPTIMIZATION: Use cached STRtree with intersects only (bc9bc54 behavior)
    global _global_spatial_cache
    _global_spatial_cache.update(placed_polygons)
    return check_collision_fast_indexed_intersects_only(polygon, _global_spatial_cache)


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


def check_collision(
    polygon1: Polygon, polygon2: Polygon, min_gap: float = 10.0
) -> bool:
    """Check if two polygons collide using TRUE GEOMETRIC distance with speed optimization.

    min_gap=10.0mm чтобы компенсировать погрешность при экспорте SPLINE entities в DXF.
    """
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

        # Стандартные углы для резки (0°, 90°, 180°, 270°)
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

                # PRIMARY SCORE: Умеренный штраф за увеличение высоты
                # ИЗМЕНЕНО: Уменьшен множитель для разрешения размещения в верхних карманах
                # Вместо жёсткой минимизации высоты, приоритизируем локальную плотность
                global_height_score = (
                    max_height_after * 1000  # Уменьшено с 5000 до 1000
                )  # Позволяет размещать ковры в верхней части при высокой заполненности

                # SECONDARY SCORE: X position for tie-breaking (prefer left placement)
                x_position_score = best_x

                # Для совсем малых листов (1-2 ковра) НЕ минимизируем ширину
                # так как это блокирует правильное размещение у краев
                # Вместо этого полагаемся на scoring в find_bottom_left_position
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

                # КРИТИЧЕСКИЙ ANTI-HANGING: Штрафуем "висящие" размещения для максимальной тетрисовости
                # Ковры ДОЛЖНЫ опираться на дно или другие ковры, иначе блокируют пространство
                test_bounds = test_translated.bounds
                bottom_y = test_bounds[1]

                # УСИЛЕННЫЙ ШТРАФ: даже небольшая высота от дна должна штрафоваться
                if (
                    bottom_y > 50
                ):  # Снижен порог с 100 до 50 для более строгой компактности
                    # Проверяем площадь опоры снизу
                    support_area = 0
                    for other in placed:
                        if other.polygon.bounds[3] <= bottom_y + 5:  # Ковер снизу
                            # Создаем полигон чуть ниже текущего для проверки опоры
                            support_test = translate_polygon(test_translated, 0, -3)
                            if support_test.intersects(other.polygon):
                                intersection = support_test.intersection(other.polygon)
                                support_area += intersection.area

                    # Если опора маленькая, это "висящий" ковер - КРИТИЧЕСКИЙ штраф
                    carpet_area = test_translated.area
                    support_ratio = support_area / carpet_area if carpet_area > 0 else 0

                    # ИЗМЕНЕНО: Умеренный штраф за недостаточную опору
                    # Разрешаем размещение в верхних карманах при хорошей локальной плотности
                    if support_ratio < 0.4:
                        # Умеренный штраф вместо огромного (было 150000)
                        # Это позволяет размещать ковры в верхних карманах между другими коврами
                        hanging_penalty = int(
                            (0.4 - support_ratio) * 10000
                        )  # Уменьшено с 150000
                        shape_bonus += hanging_penalty

                    # ИЗМЕНЕНО: Минимальный штраф за высоту, не блокирующий
                    # Уменьшено с 50 до 10 для разрешения верхнего размещения
                    height_penalty = int(bottom_y * 10)  # Минимальный штраф
                    shape_bonus += height_penalty

                total_score = position_score + shape_bonus

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
                                min_gap=10.0,  # Строгий 2мм зазор
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
    max_passes = 1  # Reduced from 2 for speed

    for pass_num in range(max_passes):
        if not moved_any:
            break
        moved_any = False

        # Simple down movement
        for i in range(n):
            poly = current_polys[i]
            step = 3.0  # Increased from 2.0 for speed

            while True:
                test = translate_polygon(poly, 0, -step)
                if test.bounds[1] < 0:
                    break

                # Collision check with min_gap
                collision = False
                for j in range(n):
                    if j != i:
                        # Check both intersection and minimum gap
                        if (
                            test.intersects(current_polys[j])
                            or test.distance(current_polys[j]) < min_gap
                        ):
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
                    if j != i:
                        # Check both intersection and minimum gap
                        if (
                            test.intersects(current_polys[j])
                            or test.distance(current_polys[j]) < min_gap
                        ):
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

    # Convert sheet size from cm to mm to match DXF polygon units
    sheet_width_mm, sheet_height_mm = sheet_size[0] * 10, sheet_size[1] * 10

    placed: list[PlacedCarpet] = []
    unplaced: list[UnplacedCarpet] = []

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
            unplaced.append(UnplacedCarpet.from_carpet(carpet))
            continue

        # REVOLUTIONARY TETRIS ROTATION STRATEGY: Optimize for space liberation
        best_placement = None
        best_score = float("inf")  # Lower is better

        # Стандартные углы для резки (0°, 90°, 180°, 270°)
        rotation_angles = [0, 90, 180, 270]

        # ПРИОРИТЕТ ОДИНАКОВОГО УГЛА: Для одинаковых ковров сначала пробуем тот же угол
        # Это обеспечивает плотную упаковку - одинаковые формы лучше стыкуются
        same_carpets_placed = [p for p in placed if p.filename == carpet.filename]
        if len(same_carpets_placed) > 0:
            # Смотрим какие углы уже использованы
            used_angles = [p.angle for p in same_carpets_placed]

            # Находим самый популярный угол среди уже размещенных одинаковых ковров
            angle_counts = {a: used_angles.count(a) for a in [0, 90, 180, 270]}
            most_common_angle = max(angle_counts.items(), key=lambda x: x[1])[0]

            # Пробуем сначала самый популярный угол, потом все остальные
            # Это даёт плотную упаковку: одинаковые ковры под одним углом стыкуются лучше
            rotation_angles = [most_common_angle] + [
                a for a in [0, 90, 180, 270] if a != most_common_angle
            ]

        for angle in rotation_angles:
            rotated = get_cached_rotation(carpet, angle)
            rotated_bounds = rotated.bounds
            rotated_width = rotated_bounds[2] - rotated_bounds[0]
            rotated_height = rotated_bounds[3] - rotated_bounds[1]

            # Skip if doesn't fit
            if rotated_width > sheet_width_mm or rotated_height > sheet_height_mm:
                continue

            # ЧИСТЫЙ BOTTOM-LEFT: размещаем в самой нижней-левой позиции
            bl_x, bl_y = find_bottom_left_position(
                rotated, placed, sheet_width_mm, sheet_height_mm
            )
            if bl_x is None or bl_y is None:
                continue

            # Используем только одну позицию - bottom-left
            candidate_positions = [(bl_x, bl_y)]

            # Пробуем эту позицию
            for best_x, best_y in candidate_positions:
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

                # PRIMARY SCORE: Умеренный штраф за увеличение высоты
                # ИЗМЕНЕНО: Уменьшен множитель для разрешения размещения в верхних карманах
                # Вместо жёсткой минимизации высоты, приоритизируем локальную плотность
                global_height_score = (
                    max_height_after * 1000  # Уменьшено с 5000 до 1000
                )  # Позволяет размещать ковры в верхней части при высокой заполненности

                # SECONDARY SCORE: X position for tie-breaking (prefer left placement)
                x_position_score = best_x

                # Для совсем малых листов (1-2 ковра) НЕ минимизируем ширину
                # так как это блокирует правильное размещение у краев
                # Вместо этого полагаемся на scoring в find_bottom_left_position
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
                # dx_to_target = best_x - rotated_bounds[0]
                # dy_to_target = best_y - rotated_bounds[1]
                # test_translated = translate_polygon(rotated, dx_to_target, dy_to_target)

                # REVOLUTIONARY: True tetris quality assessment
                tetris_bonus = calculate_tetris_quality_bonus(
                    rotated, all_test_placed, sheet_width_mm, sheet_height_mm
                )
                shape_bonus -= tetris_bonus  # Negative is better

                # КРИТИЧЕСКИЙ ANTI-HANGING: Штрафуем "висящие" размещения для максимальной тетрисовости
                # Ковры ДОЛЖНЫ опираться на дно или другие ковры, иначе блокируют пространство
                test_bounds = test_translated.bounds
                bottom_y = test_bounds[1]

                # УСИЛЕННЫЙ ШТРАФ: даже небольшая высота от дна должна штрафоваться
                if (
                    bottom_y > 50
                ):  # Снижен порог с 100 до 50 для более строгой компактности
                    # Проверяем площадь опоры снизу
                    support_area = 0
                    for other in placed:
                        if other.polygon.bounds[3] <= bottom_y + 5:  # Ковер снизу
                            # Создаем полигон чуть ниже текущего для проверки опоры
                            support_test = translate_polygon(test_translated, 0, -3)
                            if support_test.intersects(other.polygon):
                                intersection = support_test.intersection(other.polygon)
                                support_area += intersection.area

                    # Если опора маленькая, это "висящий" ковер - КРИТИЧЕСКИЙ штраф
                    carpet_area = test_translated.area
                    support_ratio = support_area / carpet_area if carpet_area > 0 else 0

                    # ИЗМЕНЕНО: Умеренный штраф за недостаточную опору
                    # Разрешаем размещение в верхних карманах при хорошей локальной плотности
                    if support_ratio < 0.4:
                        # Умеренный штраф вместо огромного (было 150000)
                        # Это позволяет размещать ковры в верхних карманах между другими коврами
                        hanging_penalty = int(
                            (0.4 - support_ratio) * 10000
                        )  # Уменьшено с 150000
                        shape_bonus += hanging_penalty

                    # ИЗМЕНЕНО: Минимальный штраф за высоту, не блокирующий
                    # Уменьшено с 50 до 10 для разрешения верхнего размещения
                    height_penalty = int(bottom_y * 10)  # Минимальный штраф
                    shape_bonus += height_penalty

                # КРИТИЧЕСКИ ВАЖНЫЙ БОНУС ЗА ПРАВИЛЬНУЮ ОРИЕНТАЦИЮ
                # Для симметричных ковров - одинаковый угол
                # Для асимметричных - чередующиеся углы (90°↔270°, 0°↔180°) для лучшей стыковки
                orientation_bonus = 0
                if len(same_carpets_placed) > 0:
                    angles_used = [p.angle for p in same_carpets_placed]

                    # Проверяем асимметричность: сравниваем центроиды при 0° и 180°
                    rot_0 = get_cached_rotation(carpet, 0)
                    rot_180 = get_cached_rotation(carpet, 180)

                    # Нормализуем обе формы к одинаковой позиции для сравнения
                    bounds_0 = rot_0.bounds
                    bounds_180 = rot_180.bounds

                    # Сдвигаем обе формы в (0,0)
                    from shapely.affinity import translate as shapely_translate

                    norm_0 = shapely_translate(rot_0, -bounds_0[0], -bounds_0[1])
                    norm_180 = shapely_translate(
                        rot_180, -bounds_180[0], -bounds_180[1]
                    )

                    # Сравниваем центроиды после нормализации
                    cent_0 = norm_0.centroid
                    cent_180 = norm_180.centroid

                    # Если центроиды отличаются >5% от размера - асимметричная
                    width_0 = bounds_0[2] - bounds_0[0]
                    height_0 = bounds_0[3] - bounds_0[1]
                    max_dim = max(width_0, height_0)

                    cent_diff_x = abs(cent_0.x - cent_180.x)
                    cent_diff_y = abs(cent_0.y - cent_180.y)

                    is_asymmetric = (
                        cent_diff_x > max_dim * 0.05 or cent_diff_y > max_dim * 0.05
                    )

                    if is_asymmetric:
                        # Для асимметричных: чередуем 90° и 270° (или 0° и 180°)
                        # Если последний ковер был 270°, текущий должен быть 90° (и наоборот)
                        last_angle = angles_used[-1]

                        if (last_angle == 270 and angle == 90) or (
                            last_angle == 90 and angle == 270
                        ):
                            orientation_bonus = -200000  # ОГРОМНЫЙ бонус за чередование
                        elif (last_angle == 0 and angle == 180) or (
                            last_angle == 180 and angle == 0
                        ):
                            orientation_bonus = -200000
                        elif angle == last_angle:
                            # Одинаковый угол для асимметричных - ОГРОМНЫЙ штраф
                            orientation_bonus = +200000
                    else:
                        # Для симметричных: одинаковый угол
                        if angle in angles_used:
                            count_at_this_angle = angles_used.count(angle)
                            orientation_bonus = -count_at_this_angle * 100000

                shape_bonus += orientation_bonus

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

                    logger.debug(f"📍 НОВОЕ ЛУЧШЕЕ РАЗМЕЩЕНИЕ для {carpet.filename}:")
                    logger.debug(
                        f"   Угол: {angle}°, Позиция: ({best_x:.1f}, {best_y:.1f}), Score: {total_score:.0f}"
                    )
                    logger.debug(f"   Финальные bounds: {final_bounds}")

                    best_placement = {
                        "polygon": translated,
                        "x_offset": actual_x_offset,
                        "y_offset": actual_y_offset,
                        "angle": angle,
                    }

        # Apply best placement if found
        if best_placement:
            new_carpet = PlacedCarpet(
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
            placed.append(new_carpet)
            logger.debug(
                f"✅ Размещён ковёр {carpet.filename} с углом {best_placement['angle']}°"
            )
            logger.debug(
                f"   Polygon bounds сразу после размещения: {new_carpet.polygon.bounds}"
            )

            # POST-PLACEMENT OPTIMIZATION - DISABLED
            # Эта оптимизация переразмещает ковры и ломает правильную раскладку
            # из find_bottom_left_position с улучшенным scoring
            if False and len(placed) >= 2:  # ОТКЛЮЧЕНО
                try:
                    # Этап 1: АГРЕССИВНАЯ Post-Placement оптимизация (полное переразмещение проблемных ковров)
                    # post_optimized = post_placement_optimize_aggressive(
                    #    placed, sheet_width_mm, sheet_height_mm
                    # )

                    # Этап 2: Гравитация для финальной компактификации
                    gravity_optimized = apply_tetris_gravity(
                        placed, sheet_width_mm, sheet_height_mm
                    )

                    # Этап 3: НОВОЕ! Сжатие к правому краю (как в настоящем Тетрисе)
                    right_compacted = apply_tetris_right_compaction(
                        gravity_optimized, sheet_width_mm, sheet_height_mm
                    )

                    # Этап 4: Финальная гравитация после сжатия к правому краю
                    gravity_optimized2 = apply_tetris_gravity(
                        right_compacted, sheet_width_mm, sheet_height_mm
                    )

                    # Этап 5: Сжатие к левому краю для плотной упаковки
                    final_optimized = apply_tetris_left_compaction(
                        gravity_optimized2, sheet_width_mm, sheet_height_mm
                    )

                    # КРИТИЧНО: Проверяем безопасность финального результата с ультра-строгим контролем
                    collision_found = False
                    for i in range(len(final_optimized)):
                        for j in range(i + 1, len(final_optimized)):
                            if check_collision(
                                final_optimized[i].polygon,
                                final_optimized[j].polygon,
                                min_gap=10.0,  # Строгий 2мм зазор
                            ):
                                collision_found = True
                                break
                        if collision_found:
                            break

                    if not collision_found:
                        placed = final_optimized  # Применяем полную оптимизацию

                except Exception:
                    logger.exception("❌ Ошибка Post-Placement оптимизации.")

            placed_successfully = True
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

                    # Final precise collision check using STRtree
                    placed_polygons = [p.polygon for p in placed]
                    collision = check_collision_with_strtree(
                        translated, placed_polygons
                    )

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
                        break

                if placed_successfully:
                    break

        if not placed_successfully:
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
    # placed = simple_compaction(placed, sheet_size, min_gap=1.0)

    # # ULTRA-AGGRESSIVE LEFT COMPACTION - ОТКЛЮЧЕНА для предотвращения пересечений
    if False and len(placed) <= 20:  # ОТКЛЮЧЕНО: вызывает пересечения
        # Ultra-aggressive left compaction to squeeze everything left - ТЕСТИРУЕМ
        placed = ultra_left_compaction(placed, sheet_size, target_width_fraction=0.7)
        #
        # Simple compaction with aggressive left push - ТЕСТИРУЕМ
        placed = simple_compaction(placed, sheet_size)
    #
    #     # Additional edge snapping for maximum left compaction - ТЕСТИРУЕМ
    #     placed = fast_edge_snap(placed, sheet_size)
    #
    #     # Final ultra-left compaction - ТЕСТИРУЕМ
    #     placed = ultra_left_compaction(placed, sheet_size, target_width_fraction=0.5)
    #
    #     # Light tightening to clean up - ТЕСТИРУЕМ
    #     placed = tighten_layout(placed, sheet_size, min_gap=10.0, step=2.0, max_passes=1)
    elif (
        len(placed) <= 35
    ):  # COMPACTION DISABLED - breaks optimal layout from find_bottom_left_position
        # placed = ultra_left_compaction(placed, sheet_size, target_width_fraction=0.7)
        # placed = simple_compaction(placed, sheet_size)
        pass
    #     placed = fast_edge_snap(placed, sheet_size)
    #
    # # No optimization for very large sets

    # 🎯 ФИНАЛЬНАЯ КОМБИНИРОВАННАЯ КОМПРЕССИЯ: ВРЕМЕННО ОТКЛЮЧЕНА
    # Отключаем компрессию для исключения пересечений
    logger.info(f"📊 Размещено {len(placed)} ковров на листе")
    logger.warning("⚠️ КОМПРЕССИЯ ОТКЛЮЧЕНА для предотвращения пересечений")

    # 🔍 ФИНАЛЬНАЯ ПРОВЕРКА НА ПЕРЕСЕЧЕНИЯ
    if placed:
        logger.info("🔍 Выполняем финальную проверку на пересечения...")
        collision_found = False
        for i in range(len(placed)):
            for j in range(i + 1, len(placed)):
                if check_collision(
                    placed[i].polygon,
                    placed[j].polygon,
                    min_gap=10.0,
                ):
                    collision_found = True
                    logger.error(
                        f"❌ КРИТИЧЕСКАЯ ОШИБКА: Обнаружено пересечение между коврами {i} и {j}"
                    )
                    logger.error(f"   Ковёр {i}: {placed[i].filename}")
                    logger.error(f"   Ковёр {j}: {placed[j].filename}")
                    break
            if collision_found:
                break

        if not collision_found:
            logger.info("✓ Проверка пройдена: пересечений не обнаружено")
        else:
            logger.error("❌ ВНИМАНИЕ: Обнаружены пересечения в финальной раскладке!")

    # if placed and len(placed) <= 100:
    #     try:
    #         logger.info(f"🎯 Применяем комбинированную компрессию к {len(placed)} коврам...")
    #         compacted_placed = apply_combined_compaction(
    #             placed, sheet_width_mm, sheet_height_mm, max_iterations=3
    #         )
    #
    #         # Проверяем безопасность результата
    #         collision_found = False
    #         for i in range(len(compacted_placed)):
    #             for j in range(i + 1, len(compacted_placed)):
    #                 if check_collision(
    #                     compacted_placed[i].polygon,
    #                     compacted_placed[j].polygon,
    #                     min_gap=10.0,
    #                 ):
    #                     collision_found = True
    #                     logger.warning(f"⚠️ Обнаружена коллизия после компрессии между {i} и {j}")
    #                     break
    #             if collision_found:
    #                 break
    #
    #         if not collision_found:
    #             placed = compacted_placed
    #             logger.info("✓ Комбинированная компрессия применена успешно")
    #         else:
    #             logger.warning("⚠️ Откатываем комбинированную компрессию из-за коллизий")
    #     except Exception as e:
    #         logger.exception(f"❌ Ошибка при применении комбинированной компрессии: {e}")
    # else:
    #     if placed:
    #         logger.warning(f"⚠️ Компрессия НЕ применяется: слишком много ковров ({len(placed)} > 100)")

    # ОТЛАДКА: Проверяем bounds перед возвратом
    logger.debug("🔍 ФИНАЛЬНЫЕ BOUNDS ПЕРЕД ВОЗВРАТОМ:")
    for i, carpet in enumerate(placed):
        logger.debug(f"   Ковёр {i} ({carpet.filename}): {carpet.polygon.bounds}")

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
    max_candidates = 1000 if is_small else 600  # Reduced for speed
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

        # Use STRtree for ultra-fast collision check
        collision = check_collision_with_strtree(test_polygon, obstacles)

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

    # 6. НОВОЕ: Проверка на создание "карманов" справа (запертого пространства)
    # Проверяем пространство справа от ковра - доступно ли оно сверху?
    pocket_penalty = 0
    right_edge = bounds[2]
    if right_edge < sheet_width - 50:  # Есть пространство справа (>50мм)
        # Проверяем точки справа на доступность сверху
        test_points_right = []
        for x in np.linspace(
            right_edge + 10, min(right_edge + 200, sheet_width - 10), 5
        ):
            for y in np.linspace(bounds[1], bounds[3], 3):
                test_points_right.append((x, y))

        if test_points_right:
            blocked_from_top = 0
            for point in test_points_right:
                # Проверяем, есть ли ковёр выше этой точки, который блокирует доступ
                blocked = False
                for placed_carpet in all_placed:
                    if hasattr(placed_carpet, "polygon"):
                        pb = placed_carpet.polygon.bounds
                        # Если ковёр выше и перекрывает по X
                        if pb[3] > point[1] and pb[0] <= point[0] <= pb[2]:
                            blocked = True
                            break
                if blocked:
                    blocked_from_top += 1

            pocket_ratio = (
                blocked_from_top / len(test_points_right) if test_points_right else 0
            )
            pocket_penalty = pocket_ratio  # 0..1, чем больше тем хуже

    # Weighted combination - увеличен вес штрафа за карманы
    tetris_score = (
        fill_ratio * 0.25
        + accessibility_ratio * 0.35  # Most important - future space
        + height_efficiency * 0.2
        + base_quality * 0.1
        + bottom_bonus * 0.1
        - pocket_penalty * 0.5  # Усилен штраф за создание карманов
    )

    # Convert to bonus (scale to meaningful range for shape_bonus)
    bonus = int(tetris_score * 8000)  # Уменьшен для лучшего баланса с другими факторами

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
    max_candidates = 600  # Balanced for speed and quality
    all_candidates = []  # (x, y, x_offset, y_offset)

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

            # Quick bounds check
            test_bounds = (
                bounds[0] + x_offset,
                bounds[1] + y_offset,
                bounds[2] + x_offset,
                bounds[3] + y_offset,
            )
            if (
                test_bounds[0] >= -0.01
                and test_bounds[1] >= -0.01
                and test_bounds[2] <= sheet_width + 0.01
                and test_bounds[3] <= sheet_height + 0.01
            ):
                all_candidates.append((x, y, x_offset, y_offset))

            if len(all_candidates) > max_candidates:
                break

        if len(all_candidates) > max_candidates:
            break

    if not all_candidates:
        return None, None

    # CRITICAL: Sort by bottom-left preference (Y first, then X) for proper gravity
    all_candidates.sort(key=lambda c: (c[1], c[0]))

    # BATCH: Create all translated polygons at once
    test_polygons = [
        translate_polygon(polygon, x_off, y_off)
        for _x, _y, x_off, y_off in all_candidates
    ]

    # OPTIMIZATION: Update STRtree cache ONCE
    global _global_spatial_cache
    _global_spatial_cache.update(obstacles)

    # BATCH: Check all collisions at once using fast batch check
    collisions = batch_check_collisions_cached_fast(
        test_polygons, _global_spatial_cache, min_gap=10.0
    )

    # Find first non-colliding position (already sorted by Y, then X)
    for i, has_collision in enumerate(collisions):
        if not has_collision:
            x, y, _x_off, _y_off = all_candidates[i]
            return x, y

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
    for obstacle in obstacles[: min(len(obstacles), 5)]:  # Reduced for speed
        if hasattr(obstacle.exterior, "coords"):
            contour_points = list(obstacle.exterior.coords)

            # Sample contour points with stride for speed
            for i, (cx, cy) in enumerate(
                contour_points[:-1:5]
            ):  # Every 5th point for speed
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

    # Strategy 2: Sheet edges with coarser step for speed
    edge_step = 1.0  # Increased from 0.05 for much better speed
    for x in np.arange(0, sheet_width - poly_width + edge_step, edge_step):
        candidates.append((x, 0))  # Bottom edge
        if sheet_height - poly_height > 0:
            candidates.append((x, sheet_height - poly_height))  # Top edge

    for y in np.arange(0, sheet_height - poly_height + edge_step, edge_step):
        candidates.append((0, y))  # Left edge
        if sheet_width - poly_width > 0:
            candidates.append((sheet_width - poly_width, y))  # Right edge

    # Remove duplicates and sort by preference (bottom-left first)
    candidates = list(set(candidates))
    candidates.sort(key=lambda pos: (pos[1], pos[0]))

    # BATCH OPTIMIZATION: Collect all valid candidates with offsets
    all_candidates = []  # (x, y, x_offset, y_offset)

    for x, y in candidates[:600]:  # Balanced for speed and quality
        x_offset = x - bounds[0]
        y_offset = y - bounds[1]

        # Bounds check
        test_bounds = (
            bounds[0] + x_offset,
            bounds[1] + y_offset,
            bounds[2] + x_offset,
            bounds[3] + y_offset,
        )
        if (
            test_bounds[0] < -0.01
            or test_bounds[1] < -0.01
            or test_bounds[2] > sheet_width + 0.01
            or test_bounds[3] > sheet_height + 0.01
        ):
            continue

        all_candidates.append((x, y, x_offset, y_offset))

    if not all_candidates:
        return None, None

    # CRITICAL: Sort by bottom-left preference (Y first, then X) for proper gravity
    all_candidates.sort(key=lambda c: (c[1], c[0]))

    # BATCH: Create all translated polygons at once
    test_polygons = [
        translate_polygon(polygon, x_off, y_off)
        for _x, _y, x_off, y_off in all_candidates
    ]

    # OPTIMIZATION: Update STRtree cache ONCE
    global _global_spatial_cache
    _global_spatial_cache.update(obstacles)

    # BATCH: Check all collisions at once using fast batch check with 1mm gap
    # Create buffered obstacles for min_gap check
    buffered_obstacles = [obs.buffer(1.0) for obs in obstacles] if obstacles else []

    # Update STRtree with buffered obstacles
    _global_spatial_cache.update(buffered_obstacles)

    # BATCH: Check all collisions at once
    collisions = batch_check_collisions_cached_fast(
        test_polygons, _global_spatial_cache
    )

    # Find first non-colliding position
    for i, has_collision in enumerate(collisions):
        if not has_collision:
            x, y, _x_off, _y_off = all_candidates[i]
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
        step_size = 1.0  # Increased from 0.5 for speed
    elif len(obstacles) <= 5:
        step_size = 2.0  # Increased from 1.0 for speed
    else:
        step_size = 3.0  # Increased from 2.0 for speed

    candidates = []

    # Grid search with adaptive limits (reduced for performance)
    max_candidates = 350 if small_polygon else 200  # Balanced for speed and quality

    for x in np.arange(0, sheet_width - poly_width + 1, step_size):
        for y in np.arange(0, sheet_height - poly_height + 1, step_size):
            candidates.append((x, y))
            if len(candidates) >= max_candidates:
                break
        if len(candidates) >= max_candidates:
            break

    # BATCH OPTIMIZATION: Collect all valid candidates with offsets
    all_candidates = []  # (x, y, x_offset, y_offset)

    for x, y in candidates:
        x_offset = x - bounds[0]
        y_offset = y - bounds[1]

        # CRITICAL FIX: Check sheet boundaries first
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

        all_candidates.append((x, y, x_offset, y_offset))

    if not all_candidates:
        return None, None

    # CRITICAL: Sort by bottom-left preference (Y first, then X) for proper gravity
    all_candidates.sort(key=lambda c: (c[1], c[0]))

    # BATCH: Create all translated polygons at once
    test_polygons = [
        translate_polygon(polygon, x_off, y_off)
        for _x, _y, x_off, y_off in all_candidates
    ]

    # OPTIMIZATION: Update STRtree cache ONCE
    global _global_spatial_cache
    _global_spatial_cache.update(obstacles)

    # BATCH: Check all collisions at once using fast batch check
    collisions = batch_check_collisions_cached_fast(
        test_polygons, _global_spatial_cache, min_gap=10.0
    )

    # Find first non-colliding position (already sorted by Y, then X)
    for i, has_collision in enumerate(collisions):
        if not has_collision:
            x, y, _x_off, _y_off = all_candidates[i]
            return x, y

    return None, None


class _Stats:
    call_counter = 0


def find_bottom_left_position_with_obstacles(
    polygon: Polygon, obstacles: list[Polygon], sheet_width: float, sheet_height: float
) -> tuple[float | None, float | None]:
    """Find the bottom-left position using FAST batch algorithm with tight packing."""
    # Try ultra-tight algorithm first
    result = find_ultra_tight_position(polygon, obstacles, sheet_width, sheet_height)
    if result[0] is not None:
        return result

    # Fallback to improved algorithm
    bounds = polygon.bounds
    poly_width = bounds[2] - bounds[0]
    poly_height = bounds[3] - bounds[1]

    # Generate candidate positions - ORIGINAL algorithm logic
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

    # Remove duplicates and sort by bottom-left preference (Y first, then X)
    candidate_positions = list(set(candidate_positions))
    candidate_positions.sort(key=lambda pos: (pos[1], pos[0]))

    if not candidate_positions:
        return None, None

    # BATCH OPTIMIZATION: Collect all valid candidates with offsets
    all_candidates = []  # (x, y, x_offset, y_offset)

    for x, y in candidate_positions:
        # Fast boundary pre-check
        if x + poly_width > sheet_width + 0.1 or y + poly_height > sheet_height + 0.1:
            continue
        if x < -0.1 or y < -0.1:
            continue

        # Pre-calculate translation offset
        x_offset = x - bounds[0]
        y_offset = y - bounds[1]

        # Check if bounds would be valid after translation
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

        all_candidates.append((x, y, x_offset, y_offset))

    if not all_candidates:
        return None, None

    # BATCH: Create all translated polygons at once
    test_polygons = [
        translate_polygon(polygon, x_off, y_off)
        for _x, _y, x_off, y_off in all_candidates
    ]

    # OPTIMIZATION: Update STRtree cache ONCE
    global _global_spatial_cache
    _global_spatial_cache.update(obstacles)

    # BATCH: Check all collisions at once using fast batch check
    collisions = batch_check_collisions_cached_fast(
        test_polygons, _global_spatial_cache, min_gap=10.0
    )

    # Find first non-colliding position (already sorted by Y, then X for bottom-left)
    for i, has_collision in enumerate(collisions):
        if not has_collision:
            x, y, _x_off, _y_off = all_candidates[i]
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

            # Quick collision check with tight tolerance for maximum density
            collision = False
            for placed_poly in placed_polygons:
                if check_collision(test_polygon, placed_poly.polygon, min_gap=10.0):
                    collision = True
                    break

            if not collision:
                return x, y

    return None, None


def find_bottom_left_position(
    polygon: Polygon, placed_polygons, sheet_width: float, sheet_height: float
):
    """FAST Simple bottom-left placement - prioritize speed over perfect density."""
    _Stats.call_counter += 1

    logger.debug(
        f"🔍 find_bottom_left_position вызвана для полигона с bounds={polygon.bounds}"
    )
    logger.debug(f"   Уже размещено ковров: {len(placed_polygons)}")

    # First placement - always bottom-left corner
    if not placed_polygons:
        logger.debug("   ✓ Первый ковёр - размещаем в (0, 0)")
        return 0, 0

    bounds = polygon.bounds
    poly_width = bounds[2] - bounds[0]
    poly_height = bounds[3] - bounds[1]

    logger.debug(f"   Размеры ковра: {poly_width:.1f} x {poly_height:.1f}")

    # FAST SCAN: Use large steps for speed
    step = max(10.0, min(poly_width, poly_height) / 3)  # Large adaptive step for speed

    best_y = None

    # КРИТИЧНО: Генерируем X позиции для МАКСИМАЛЬНОЙ компактности
    # Проверяем: 0 (левый край), справа от каждого ковра, правый край
    x_positions = []

    # 1. Левый край
    x_positions.append(0)

    # 2. Позиции справа от каждого размещенного ковра
    for placed_poly in placed_polygons:
        right_edge = placed_poly.polygon.bounds[2]
        if right_edge + poly_width <= sheet_width:
            x_positions.append(
                int(right_edge) + 10
            )  # ИСПРАВЛЕНО: 10mm gap для совместимости с check_collision

    # 3. Правый край листа (прижать к правому краю!)
    right_aligned_x = int(sheet_width - poly_width)
    if right_aligned_x >= 0:
        x_positions.append(right_aligned_x)

    # 4. Дополнительные промежуточные позиции для полноты
    for x in range(0, int(sheet_width - poly_width), max(5, int(step))):
        x_positions.append(x)

    # Убираем дубликаты и сортируем (приоритет левым)
    x_positions = sorted(set(x_positions))

    # OPTIMIZATION: Cache obstacles and STRtree ONCE
    obstacles = [placed_poly.polygon for placed_poly in placed_polygons]
    global _global_spatial_cache
    _global_spatial_cache.update(obstacles)

    # BATCH OPTIMIZATION: Collect ALL candidate positions first
    all_candidates = []  # (x, y, x_offset, y_offset)

    # УЛУЧШЕНИЕ ПЛОТНОСТИ: Проверяем больше X позиций для лучшей компактности
    for test_x in x_positions[:30]:  # Увеличено с 15 до 30 для большей плотности
        # Test only a few Y positions per X for speed
        test_y_positions = [0]  # Always try bottom

        # Add positions based on existing polygons - check ALL polygons for dense packing
        # КРИТИЧНО для плотности: нужно учитывать ВСЕ размещенные ковры
        for placed_poly in placed_polygons:  # Проверяем все полигоны
            other_bounds = placed_poly.polygon.bounds
            y_above = (
                other_bounds[3] + 10.0
            )  # ИСПРАВЛЕНО: 10mm gap для совместимости с check_collision
            test_y_positions.append(y_above)
            logger.debug(
                f"      Генерируем Y позицию выше ковра {placed_poly.filename}: {other_bounds[3]:.1f} + 10.0 = {y_above:.1f}"
            )
            # Добавляем также позиции справа от ковров для лучшей компактности
            test_y_positions.append(other_bounds[1])  # На той же высоте что низ
            test_y_positions.append(
                other_bounds[1] + (other_bounds[3] - other_bounds[1]) / 2
            )  # Посередине

        # Collect valid positions
        for test_y in sorted(set(test_y_positions)):
            if test_y < 0 or test_y + poly_height > sheet_height:
                continue

            x_offset = test_x - bounds[0]
            y_offset = test_y - bounds[1]

            # Quick bounds check
            test_bounds = (
                bounds[0] + x_offset,
                bounds[1] + y_offset,
                bounds[2] + x_offset,
                bounds[3] + y_offset,
            )

            if (
                test_bounds[0] >= 0
                and test_bounds[1] >= 0
                and test_bounds[2] <= sheet_width
                and test_bounds[3] <= sheet_height
            ):
                all_candidates.append((test_x, test_y, x_offset, y_offset))

    if not all_candidates:
        # Try fallback immediately if no candidates
        for y in range(0, int(sheet_height - poly_height), 20):
            for x in range(0, int(sheet_width - poly_width), 20):
                x_offset = x - bounds[0]
                y_offset = y - bounds[1]

                # ВАЖНО: Проверяем границы для fallback кандидатов!
                test_bounds = (
                    bounds[0] + x_offset,
                    bounds[1] + y_offset,
                    bounds[2] + x_offset,
                    bounds[3] + y_offset,
                )
                if (
                    test_bounds[0] >= 0
                    and test_bounds[1] >= 0
                    and test_bounds[2] <= sheet_width
                    and test_bounds[3] <= sheet_height
                ):
                    all_candidates.append((x, y, x_offset, y_offset))

                if len(all_candidates) >= 50:  # Limit fallback candidates
                    break
            if len(all_candidates) >= 50:
                break

    if not all_candidates:
        return None, None

    # BATCH: Create all translated polygons at once
    test_polygons = [
        translate_polygon(polygon, x_off, y_off)
        for _x, _y, x_off, y_off in all_candidates
    ]

    # BATCH: Check all collisions at once using fast batch check
    collisions = batch_check_collisions_cached_fast(
        test_polygons, _global_spatial_cache, min_gap=10.0
    )

    # КРИТИЧЕСКОЕ УЛУЧШЕНИЕ: Вместо выбора первой позиции с минимальным Y,
    # оцениваем ВСЕ валидные позиции и выбираем лучшую по плотности

    valid_positions = []
    for i, has_collision in enumerate(collisions):
        if not has_collision:
            x, y, x_off, y_off = all_candidates[i]
            test_poly = test_polygons[i]

            # Оцениваем качество позиции для максимальной плотности
            score = 0
            bounds = test_poly.bounds

            # 1. АДАПТИВНЫЙ ПРИОРИТЕТ ПОЗИЦИИ
            # Вместо жёсткого штрафа за Y, приоритизируем близость к соседям
            # Это позволяет размещать ковры в верхних "карманах" если они там хорошо помещаются

            # 1. ПРИОРИТЕТ: Количество контактов (стенок) с соседями и границами
            # Чем больше контактов, тем плотнее упаковка
            contact_count = 0
            contact_bonus = 0

            # Считаем контакты с соседями (близость < 5мм = контакт)
            for placed in placed_polygons:
                placed_bounds = placed.polygon.bounds

                # Проверяем близость со всех 4 сторон
                left_gap = bounds[0] - placed_bounds[2]  # Слева от placed
                right_gap = placed_bounds[0] - bounds[2]  # Справа от placed
                bottom_gap = bounds[1] - placed_bounds[3]  # Снизу от placed
                top_gap = placed_bounds[1] - bounds[3]  # Сверху от placed

                # Контакт если зазор < 5мм
                if -5 < left_gap < 5:
                    contact_count += 1
                    contact_bonus -= 200000
                if -5 < right_gap < 5:
                    contact_count += 1
                    contact_bonus -= 200000
                if -5 < bottom_gap < 5:
                    contact_count += 1
                    contact_bonus -= 200000
                if -5 < top_gap < 5:
                    contact_count += 1
                    contact_bonus -= 200000

            # Контакты с границами листа
            if bounds[0] < 5:  # Левый край
                contact_count += 1
                contact_bonus -= 100000
            if bounds[1] < 5:  # Нижний край
                contact_count += 1
                contact_bonus -= 100000
            if abs(bounds[2] - sheet_width) < 5:  # Правый край
                contact_count += 1
                contact_bonus -= 100000
            if abs(bounds[3] - sheet_height) < 5:  # Верхний край (реже нужно)
                contact_count += 1
                contact_bonus -= 50000

            score += contact_bonus

            # 2. МИНИМАЛЬНЫЙ штраф за высоту (приоритет для нижних, но не блокирующий)
            score += y * 20

            # 3. МИНИМАЛЬНЫЙ штраф за удалённость от левого края
            score += bounds[0] * 5

            # 4. Если нет контактов вообще, большой штраф (изолированная позиция)
            if contact_count == 0:
                score += 1000000  # Очень плохо - ковёр в пустоте

            # 5. УМЕРЕННЫЙ ШТРАФ ЗА НЕДОСТАТОЧНУЮ ОПОРУ
            # Проверяем опору снизу, но не блокируем размещение в верхних карманах
            bottom_y = bounds[1]
            if bottom_y > 50:
                # Проверяем опору снизу
                support_area = 0
                for placed in placed_polygons:
                    if placed.polygon.bounds[3] <= bottom_y + 5:
                        # Проверяем пересечение снизу
                        support_test = translate_polygon(test_poly, 0, -3)
                        if support_test.intersects(placed.polygon):
                            intersection = support_test.intersection(placed.polygon)
                            support_area += intersection.area

                support_ratio = (
                    support_area / test_poly.area if test_poly.area > 0 else 0
                )

                # ИЗМЕНЕНО: Умеренный штраф вместо огромного
                # Если есть близкие соседи, опора не так важна
                if support_ratio < 0.4:
                    # Вместо 100000, используем 5000 - умеренный штраф
                    # Это позволяет размещать ковры в верхних карманах
                    support_penalty = int((0.4 - support_ratio) * 5000)

                    # Если ковер имеет много контактов (в кармане), уменьшаем штраф
                    if contact_count >= 2:
                        support_penalty = support_penalty // 2

                    score += support_penalty

            valid_positions.append((score, x, y, i))

    # Выбираем позицию с МИНИМАЛЬНЫМ score (лучшая плотность)
    if valid_positions:
        valid_positions.sort()  # Сортируем по score
        best_score, best_x, best_y, best_i = valid_positions[0]

        logger.debug(f"   ✓ Найдено {len(valid_positions)} валидных позиций")
        logger.debug(
            f"   ✓ Выбрана лучшая позиция: ({best_x:.1f}, {best_y:.1f}) со score={best_score}"
        )
        if len(valid_positions) > 1:
            logger.debug(
                f"   Альтернативы (top 3): {[(score, x, y) for score, x, y, _ in valid_positions[:3]]}"
            )

        return best_x, best_y

    logger.warning(
        f"   ❌ НЕ НАЙДЕНО валидных позиций! Всего кандидатов: {len(all_candidates)}, коллизий: {sum(collisions)}"
    )
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


def try_simple_placement(
    carpet: Carpet, existing_placed: list[PlacedCarpet], sheet_size: tuple[float, float]
) -> PlacedCarpet | None:
    """FAST placement using find_bottom_left_position for priority2 carpets."""
    import shapely.affinity

    # Convert sheet size from cm to mm
    sheet_width_mm, sheet_height_mm = sheet_size[0] * 10, sheet_size[1] * 10

    # Try all 4 rotations for better placement
    for angle in [0, 90, 180, 270]:
        rotated = get_cached_rotation(carpet, angle)
        bounds = rotated.bounds
        poly_width = bounds[2] - bounds[0]
        poly_height = bounds[3] - bounds[1]

        # Skip if doesn't fit
        if poly_width > sheet_width_mm or poly_height > sheet_height_mm:
            continue

        # Use find_bottom_left_position which intelligently checks edges and key positions
        bl_x, bl_y = find_bottom_left_position(
            rotated, existing_placed, sheet_width_mm, sheet_height_mm
        )

        if bl_x is not None and bl_y is not None:
            # Calculate final position
            dx = bl_x - bounds[0]
            dy = bl_y - bounds[1]
            positioned_polygon = shapely.affinity.translate(rotated, dx, dy)

            # Check if it fits in sheet
            pos_bounds = positioned_polygon.bounds
            if (
                pos_bounds[0] < 0
                or pos_bounds[1] < 0
                or pos_bounds[2] > sheet_width_mm
                or pos_bounds[3] > sheet_height_mm
            ):
                continue

            # Check for collisions with existing polygons
            has_collision = False
            for placed in existing_placed:
                if positioned_polygon.intersects(placed.polygon):
                    intersection = positioned_polygon.intersection(placed.polygon)
                    if hasattr(intersection, "area") and intersection.area > 0.1:
                        has_collision = True
                        break

            if not has_collision:
                # Found valid placement - return immediately
                return PlacedCarpet(
                    polygon=positioned_polygon,
                    x_offset=dx,
                    y_offset=dy,
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
                        all_existing_polygons = (
                            p.polygon for p in layout.placed_polygons
                        )
                        new_polygons = (p.polygon for p in best_placed)

                        # Check for any overlaps between new and existing polygons
                        has_overlap = False
                        for new_poly in new_polygons:
                            for existing_poly in all_existing_polygons:
                                if check_collision(
                                    new_poly,
                                    existing_poly,
                                    min_gap=1.0,  # Увеличили для предотвращения пересечений
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

                            # Remove successfully placed carpets from remaining list
                            placed_carpet_set = set(
                                c for c in matching_carpets if c not in best_remaining
                            )
                            remaining_carpets = [
                                c
                                for c in remaining_carpets
                                if c not in placed_carpet_set
                            ]

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
            t1 = time.time()
            placed, remaining = bin_packing(
                remaining_carpets,
                sheet_size,
                verbose=False,
                progress_callback=progress_callback,
            )
            logger.info(f"bin_packing сработал за {time.time() - t1} c.")

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
