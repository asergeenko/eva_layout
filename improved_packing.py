"""
Улучшенный алгоритм раскладки с использованием No-Fit Polygon (NFP) подходов
для максимальной плотности размещения автомобильных ковриков с приоритетом заполнения пространства.
"""

import numpy as np
from shapely.geometry import Polygon, Point
from shapely import affinity
from typing import List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

class AdvancedCarpetPacker:
    """Продвинутый алгоритм размещения ковриков с акцентом на максимальное заполнение пространства."""

    def __init__(self, sheet_width_mm: float, sheet_height_mm: float):
        self.sheet_width = sheet_width_mm
        self.sheet_height = sheet_height_mm
        self.placed_polygons = []
        self.placed_positions = []
        self.occupied_min_x = float('inf')
        self.occupied_max_x = float('-inf')
        self.occupied_min_y = float('inf')
        self.occupied_max_y = float('-inf')

    def pack_carpets(self, carpets, progress_callback=None) -> Tuple[List, List]:
        """Основная функция размещения ковриков на одном листе с максимальным заполнением."""
        placed = []
        unplaced = []

        # Улучшенная сортировка по нескольким критериям
        sorted_carpets = self._sort_carpets_advanced(carpets)

        total_carpets = len(sorted_carpets)
        for i, carpet in enumerate(sorted_carpets):
            if progress_callback:
                progress_callback(
                    int(50 + 40 * i / total_carpets),
                    f"Размещение коврика {i+1}/{total_carpets}",
                )

            placement = self._try_standard_placement(carpet)

            if placement:
                placed.append(placement)
                self.placed_polygons.append(placement[0])
                self.placed_positions.append((placement[1], placement[2]))
                # Обновляем занятые границы
                bounds = placement[0].bounds
                self.occupied_min_x = min(self.occupied_min_x, bounds[0])
                self.occupied_max_x = max(self.occupied_max_x, bounds[2])
                self.occupied_min_y = min(self.occupied_min_y, bounds[1])
                self.occupied_max_y = max(self.occupied_max_y, bounds[3])
                density = (
                    placement[7].get("density", 0)
                    if len(placement) > 7 and isinstance(placement[7], dict)
                    else 0
                )
                logger.info(f"Размещен {carpet.filename} с плотностью {density:.2f}")
            else:
                unplaced.append(carpet)
                logger.warning(f"Не удалось разместить {carpet.filename}")

        return placed, unplaced

    def _sort_carpets_advanced(self, carpets):
        """Улучшенная сортировка ковриков для оптимального размещения."""
        def carpet_priority(carpet):
            bounds = carpet.polygon.bounds
            width = bounds[2] - bounds[0]
            height = bounds[3] - bounds[1]
            area = carpet.polygon.area
            bbox_area = width * height
            complexity = area / bbox_area if bbox_area > 0 else 0
            aspect_ratio = max(width, height) / min(width, height) if min(width, height) > 0 else float("inf")
            return (area * 1000, complexity * 500, -aspect_ratio * 100)
        return sorted(carpets, key=carpet_priority, reverse=True)

    def _try_standard_placement(self, carpet):
        """Улучшенный стандартный алгоритм размещения с фокусом на заполнение пространства."""
        best_placement = None
        best_score = float("-inf")
        rotation_angles = [0, 90, 180, 270]

        for angle in rotation_angles:
            rotated_polygon = self._rotate_carpet(carpet.polygon, angle)
            rotated_bounds = rotated_polygon.bounds
            rotated_width = rotated_bounds[2] - rotated_bounds[0]
            rotated_height = rotated_bounds[3] - rotated_bounds[1]

            if rotated_width > self.sheet_width or rotated_height > self.sheet_height:
                continue

            candidates = self._generate_placement_candidates(rotated_polygon, rotated_width, rotated_height)

            for x, y in candidates:
                if x + rotated_width > self.sheet_width or y + rotated_height > self.sheet_height:
                    continue

                dx = x - rotated_bounds[0]
                dy = y - rotated_bounds[1]
                test_polygon = self._translate_polygon(rotated_polygon, dx, dy)

                if self._has_collisions(test_polygon):
                    continue

                score = self._evaluate_placement(test_polygon, x, y)

                if score > best_score:
                    best_score = score
                    best_placement = (
                        test_polygon,
                        x, y, angle,
                        carpet.filename,
                        carpet.color,
                        carpet.order_id,
                        {"density": score, "algorithm": "standard"}
                    )

        return best_placement

    def _generate_placement_candidates(self, polygon: Polygon, width: float, height: float) -> List[Tuple[float, float]]:
        """Генерирует кандидатов для размещения с акцентом на заполнение пустого пространства."""
        candidates = set()
        bounds = polygon.bounds
        gap = 0.5
        dynamic_step = max(20.0, min(width, height) / 5)  # Адаптивный шаг

        if not self.placed_polygons:
            candidates.add((0, 0))
            for x in np.arange(0, self.sheet_width - width + dynamic_step, dynamic_step):
                candidates.add((x, 0))
            for y in np.arange(0, self.sheet_height - height + dynamic_step, dynamic_step):
                candidates.add((0, y))
        else:
            # Плотное размещение рядом с существующими
            for placed in self.placed_polygons:
                p_bounds = placed.bounds
                # Справа
                x = p_bounds[2] + gap
                if x + width <= self.sheet_width:
                    for dy in np.arange(-height, height + 10, 10):  # Мелкий шаг для плотности
                        y = p_bounds[1] + dy
                        if 0 <= y <= self.sheet_height - height:
                            candidates.add((x, y))

                # Сверху
                y = p_bounds[3] + gap
                if y + height <= self.sheet_height:
                    for dx in np.arange(-width, width + 10, 10):  # Мелкий шаг
                        x = p_bounds[0] + dx
                        if 0 <= x <= self.sheet_width - width:
                            candidates.add((x, y))

                # Левее
                x = p_bounds[0] - width - gap
                if x >= 0:
                    for dy in np.arange(-height, height + 10, 10):
                        y = p_bounds[1] + dy
                        if 0 <= y <= self.sheet_height - height:
                            candidates.add((x, y))

                # Ниже
                y = p_bounds[1] - height - gap
                if y >= 0:
                    for dx in np.arange(-width, width + 10, 10):
                        x = p_bounds[0] + dx
                        if 0 <= x <= self.sheet_width - width:
                            candidates.add((x, y))

            # Точная сетка для больших пустых областей
            unoccupied_width = self.sheet_width - (self.occupied_max_x - self.occupied_min_x)
            unoccupied_height = self.sheet_height - (self.occupied_max_y - self.occupied_min_y)
            fine_step = max(10.0, min(width, height) / 10)  # Еще более мелкий шаг

            if unoccupied_width > width or unoccupied_height > height:
                # Проверяем оставшееся пространство
                for y in np.arange(0, self.sheet_height - height + fine_step, fine_step):
                    for x in np.arange(0, self.sheet_width - width + fine_step, fine_step):
                        if not any(self._quick_overlap_check(x, y, width, height, placed.bounds) for placed in self.placed_polygons):
                            candidates.add((x, y))

        candidates_list = list(candidates)
        candidates_list.sort(key=lambda pos: (pos[1], pos[0]))
        max_candidates = 200
        if len(candidates_list) > max_candidates:
            candidates_list = candidates_list[:max_candidates]

        return candidates_list

    def _quick_overlap_check(self, x: float, y: float, width: float, height: float, placed_bounds):
        """Быстрая проверка пересечения с bounding box."""
        return not (x + width <= placed_bounds[0] or x >= placed_bounds[2] or
                    y + height <= placed_bounds[1] or y >= placed_bounds[3])

    def _evaluate_placement(self, polygon: Polygon, x: float, y: float) -> float:
        """Оценивает качество размещения с акцентом на заполнение пространства."""
        score = 0.0
        bounds = polygon.bounds

        # Усиленный бонус за bottom-left
        corner_score = 1200 - (x * 0.4 + y * 0.5)
        score += corner_score

        # Бонус за компактность и заполнение
        if self.placed_polygons:
            min_distance = float('inf')
            avg_distance = 0.0
            count = 0
            for placed_polygon in self.placed_polygons:
                placed_bounds = placed_polygon.bounds
                dx = max(0, max(bounds[0] - placed_bounds[2], placed_bounds[0] - bounds[2]))
                dy = max(0, max(bounds[1] - placed_bounds[3], placed_bounds[1] - bounds[3]))
                distance = np.sqrt(dx * dx + dy * dy)
                min_distance = min(min_distance, distance)
                avg_distance += distance
                count += 1

            avg_distance /= count if count > 0 else 1

            if min_distance < 40:
                score += 600 * (1 - min_distance / 40)  # Усилен бонус за близость

            if avg_distance > 80:
                score -= 250 * (avg_distance / 80 - 1)  # Усилен штраф

        # Сильный бонус за использование оставшегося пространства
        space_bonus = self._calculate_space_utilization_bonus(polygon)
        score += space_bonus * 2  # Удвоен вес для приоритета заполнения

        # Бонус за заполнение зазоров
        gap_bonus = self._calculate_gap_fill_bonus(polygon)
        score += gap_bonus * 4

        # Штраф за отходы
        waste_penalty = self._calculate_waste_penalty(polygon)
        score -= waste_penalty * 2

        return score

    def _calculate_space_utilization_bonus(self, polygon: Polygon) -> float:
        """Бонус за использование оставшегося пространства."""
        bounds = polygon.bounds
        bonus = 0.0
        unoccupied_width = self.sheet_width - (self.occupied_max_x - self.occupied_min_x)
        unoccupied_height = self.sheet_height - (self.occupied_max_y - self.occupied_min_y)

        # Бонус за заполнение горизонтального пространства
        if bounds[2] > self.occupied_max_x and unoccupied_width > 0:
            bonus += 200 * (1 - (self.sheet_width - bounds[2]) / unoccupied_width)

        # Бонус за заполнение вертикального пространства
        if bounds[3] > self.occupied_max_y and unoccupied_height > 0:
            bonus += 200 * (1 - (self.sheet_height - bounds[3]) / unoccupied_height)

        # Бонус за использование краев
        edge_bonus = 0.0
        if bounds[0] < 50:  # Близко к левому краю
            edge_bonus += 100
        if bounds[1] < 50:  # Близко к нижнему краю
            edge_bonus += 100
        if self.sheet_width - bounds[2] < 50:  # Близко к правому краю
            edge_bonus += 100
        if self.sheet_height - bounds[3] < 50:  # Близко к верхнему краю
            edge_bonus += 100
        bonus += edge_bonus

        return bonus

    def _calculate_gap_fill_bonus(self, polygon: Polygon) -> float:
        """Бонус за заполнение промежутков между полигонами."""
        bounds = polygon.bounds
        bonus = 0.0
        left_count = right_count = above_count = below_count = 0

        for placed_polygon in self.placed_polygons:
            placed_bounds = placed_polygon.bounds
            if placed_bounds[2] < bounds[0] + 25 and abs(placed_bounds[1] - bounds[1]) < 40:
                left_count += 1
            elif placed_bounds[0] > bounds[2] - 25 and abs(placed_bounds[1] - bounds[1]) < 40:
                right_count += 1
            if placed_bounds[3] < bounds[1] + 25 and abs(placed_bounds[0] - bounds[0]) < 40:
                below_count += 1
            elif placed_bounds[1] > bounds[3] - 25 and abs(placed_bounds[0] - bounds[0]) < 40:
                above_count += 1

        neighbor_count = bool(left_count) + bool(right_count) + bool(above_count) + bool(below_count)
        bonus += 250 * neighbor_count
        bonus += 60 * (left_count + right_count + above_count + below_count)

        return bonus

    def _calculate_waste_penalty(self, polygon: Polygon) -> float:
        """Рассчитывает штраф за создание непригодных областей."""
        bounds = polygon.bounds
        penalty = 0.0
        min_useful = 25

        if 0 < self.sheet_width - bounds[2] < min_useful:
            penalty += 15
        if 0 < self.sheet_height - bounds[3] < min_useful:
            penalty += 15

        return penalty

    def _rotate_carpet(self, polygon: Polygon, angle: float) -> Polygon:
        if angle == 0:
            return polygon
        return affinity.rotate(polygon, angle, origin="centroid")

    def _translate_polygon(self, polygon: Polygon, dx: float, dy: float) -> Polygon:
        return affinity.translate(polygon, dx, dy)

    def _fits_on_sheet(self, polygon: Polygon) -> bool:
        bounds = polygon.bounds
        return (bounds[2] - bounds[0] <= self.sheet_width and
                bounds[3] - bounds[1] <= self.sheet_height)

    def _has_collisions(self, test_polygon: Polygon) -> bool:
        test_bounds = test_polygon.bounds
        for placed_polygon in self.placed_polygons:
            placed_bounds = placed_polygon.bounds
            dx = max(0, max(test_bounds[0] - placed_bounds[2], placed_bounds[0] - test_bounds[2]))
            dy = max(0, max(test_bounds[1] - placed_bounds[3], placed_bounds[1] - test_bounds[3]))
            if np.sqrt(dx * dx + dy * dy) > 1.0:
                continue
            if test_polygon.distance(placed_polygon) < 0.5:
                return True
        return False


def improved_bin_packing(carpets, sheet_size, verbose=True):
    """Улучшенная функция bin packing с использованием AdvancedCarpetPacker."""
    sheet_width_mm = sheet_size[0] * 10
    sheet_height_mm = sheet_size[1] * 10

    packer = AdvancedCarpetPacker(sheet_width_mm, sheet_height_mm)
    placed, unplaced = packer.pack_carpets(carpets)

    if verbose and len(placed) > 0:
        total_area = sum(p[0].area for p in placed)
        sheet_area = sheet_width_mm * sheet_height_mm
        usage_percent = (total_area / sheet_area) * 100
        logger.info(
            f"Улучшенный алгоритм: размещено {len(placed)}, использование {usage_percent:.1f}%"
        )

    return placed, unplaced