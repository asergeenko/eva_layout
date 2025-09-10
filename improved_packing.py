"""
Улучшенный алгоритм раскладки с использованием No-Fit Polygon (NFP) подходов
для максимальной плотности размещения автомобильных ковриков с приоритетом плотной группировки.
"""

import numpy as np
from shapely.geometry import Polygon, Point
from shapely import affinity
from typing import List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

class AdvancedCarpetPacker:
    """Продвинутый алгоритм размещения ковриков с акцентом на максимальную плотность и группировку."""

    def __init__(self, sheet_width_mm: float, sheet_height_mm: float):
        self.sheet_width = sheet_width_mm
        self.sheet_height = sheet_height_mm
        self.placed_polygons = []
        self.placed_positions = []
        self.occupied_min_x = float('inf')
        self.occupied_max_x = float('-inf')
        self.occupied_min_y = float('inf')
        self.occupied_max_y = float('-inf')
        self.current_sheet = 1

    def pack_carpets(self, carpets, progress_callback=None) -> Tuple[List, List]:
        """Основная функция размещения ковриков с максимальной плотностью на всех листах."""
        placed = []
        unplaced = carpets.copy()

        while unplaced:
            if progress_callback:
                progress_callback(
                    int(50 + 40 * (len(carpets) - len(unplaced)) / len(carpets)),
                    f"Обработка листа {self.current_sheet}",
                )

            sheet_placed, remaining = self._process_sheet(unplaced)
            placed.extend(sheet_placed)
            unplaced = remaining

            if remaining and self._is_sheet_full():
                self._start_new_sheet()

        return placed, unplaced

    def _start_new_sheet(self):
        """Начинает новый лист, сбрасывая размещенные полигоны."""
        self.placed_polygons = []
        self.placed_positions = []
        self.occupied_min_x = float('inf')
        self.occupied_max_x = float('-inf')
        self.occupied_min_y = float('inf')
        self.occupied_max_y = float('-inf')
        self.current_sheet += 1

    def _process_sheet(self, carpets) -> Tuple[List, List]:
        """Обрабатывает текущий лист с максимальной плотностью и группировкой."""
        placed = []
        unplaced = []

        sorted_carpets = self._sort_carpets_advanced(carpets)
        for carpet in sorted_carpets:
            placement = self._try_dense_placement(carpet)
            if placement:
                placed.append(placement)
                self.placed_polygons.append(placement[0])
                self.placed_positions.append((placement[1], placement[2]))
                bounds = placement[0].bounds
                self.occupied_min_x = min(self.occupied_min_x, bounds[0])
                self.occupied_max_x = max(self.occupied_max_x, bounds[2])
                self.occupied_min_y = min(self.occupied_min_y, bounds[1])
                self.occupied_max_y = max(self.occupied_max_y, bounds[3])
                density = placement[7].get("density", 0)
                logger.info(f"Размещен {carpet.filename} на листе {self.current_sheet} с плотностью {density:.2f}")
            else:
                unplaced.append(carpet)

        return placed, unplaced

    def _is_sheet_full(self) -> bool:
        """Проверяет, достиг ли лист порога заполнения (90% площади или 50 ковров)."""
        if not self.placed_polygons:
            return False
        total_area = sum(polygon.area for polygon in self.placed_polygons)
        sheet_area = self.sheet_width * self.sheet_height
        occupancy = total_area / sheet_area
        return occupancy >= 0.90 or len(self.placed_polygons) >= 50

    def _sort_carpets_advanced(self, carpets):
        """Улучшенная сортировка ковриков для оптимальной группировки."""
        def carpet_priority(carpet):
            bounds = carpet.polygon.bounds
            width = bounds[2] - bounds[0]
            height = bounds[3] - bounds[1]
            area = carpet.polygon.area
            bbox_area = width * height
            complexity = area / bbox_area if bbox_area > 0 else 0
            aspect_ratio = max(width, height) / min(width, height) if min(width, height) > 0 else float("inf")
            return (area * 1000, -complexity * 500, aspect_ratio * 100)
        return sorted(carpets, key=carpet_priority, reverse=True)

    def _try_dense_placement(self, carpet):
        """Попытка плотного размещения с акцентом на группировку."""
        best_placement = None
        best_score = float("-inf")
        rotation_angles = [0, 90]  # Ограничено для производительности

        for angle in rotation_angles:
            rotated_polygon = self._rotate_carpet(carpet.polygon, angle)
            rotated_bounds = rotated_polygon.bounds
            rotated_width = rotated_bounds[2] - rotated_bounds[0]
            rotated_height = rotated_bounds[3] - rotated_bounds[1]

            if rotated_width > self.sheet_width or rotated_height > self.sheet_height:
                continue

            candidates = self._generate_grouping_candidates(rotated_polygon, rotated_width, rotated_height)

            for x, y in candidates[:50]:
                if x + rotated_width > self.sheet_width or y + rotated_height > self.sheet_height:
                    continue

                dx = x - rotated_bounds[0]
                dy = y - rotated_bounds[1]
                test_polygon = self._translate_polygon(rotated_polygon, dx, dy)

                if not self._has_collisions(test_polygon, tolerance=1.0):
                    score = self._evaluate_placement(test_polygon, x, y)

                    if score > best_score or best_placement is None:
                        best_score = score
                        best_placement = (
                            test_polygon,
                            x, y, angle,
                            carpet.filename,
                            carpet.color,
                            carpet.order_id,
                            {"density": score, "algorithm": "dense"}
                        )

        return best_placement

    def _generate_grouping_candidates(self, polygon: Polygon, width: float, height: float) -> List[Tuple[float, float]]:
        """Генерирует кандидатов с приоритетом плотной группировки рядом с существующими полигонами."""
        candidates = set()
        bounds = polygon.bounds
        gap = 0.5  # Минимальный зазор для плотной группировки
        dynamic_step = max(10.0, min(width, height) / 5)

        if not self.placed_polygons:
            for x in np.arange(0, self.sheet_width - width + dynamic_step, dynamic_step):
                for y in np.arange(0, self.sheet_height - height + dynamic_step, dynamic_step):
                    if 0 <= x <= self.sheet_width - width and 0 <= y <= self.sheet_height - height:
                        candidates.add((x, y))
        else:
            for placed in self.placed_polygons[:5]:  # Увеличено до 5 для лучшей группировки
                p_bounds = placed.bounds
                # Справа
                x = p_bounds[2] + gap
                if x + width <= self.sheet_width:
                    for dy in np.arange(-height/2, height/2 + dynamic_step, dynamic_step):
                        y = p_bounds[1] + dy
                        if 0 <= y <= self.sheet_height - height:
                            candidates.add((x, y))
                # Сверху
                y = p_bounds[3] + gap
                if y + height <= self.sheet_height:
                    for dx in np.arange(-width/2, width/2 + dynamic_step, dynamic_step):
                        x = p_bounds[0] + dx
                        if 0 <= x <= self.sheet_width - width:
                            candidates.add((x, y))
                # Слева
                x = p_bounds[0] - width - gap
                if x >= 0:
                    for dy in np.arange(-height/2, height/2 + dynamic_step, dynamic_step):
                        y = p_bounds[1] + dy
                        if 0 <= y <= self.sheet_height - height:
                            candidates.add((x, y))
                # Снизу
                y = p_bounds[1] - height - gap
                if y >= 0:
                    for dx in np.arange(-width/2, width/2 + dynamic_step, dynamic_step):
                        x = p_bounds[0] + dx
                        if 0 <= x <= self.sheet_width - width:
                            candidates.add((x, y))

        candidates_list = list(candidates)
        max_candidates = 50
        if len(candidates_list) > max_candidates:
            candidates_list = candidates_list[:max_candidates]

        return candidates_list

    def _evaluate_placement(self, polygon: Polygon, x: float, y: float) -> float:
        """Оценивает качество размещения с акцентом на плотную группировку."""
        score = 500.0
        bounds = polygon.bounds

        if self.placed_polygons:
            min_distance = float('inf')
            for placed_polygon in self.placed_polygons:
                distance = polygon.distance(placed_polygon)
                min_distance = min(min_distance, distance)
            if min_distance < 5:
                score += 2000 * (1 - min_distance / 5)  # Сильный бонус за тесное расположение
            elif min_distance < 20:
                score += 1000 * (1 - (min_distance - 5) / 15)

        edge_bonus = 0.0
        if bounds[0] < 50:
            edge_bonus += 50
        if bounds[1] < 50:
            edge_bonus += 50
        if self.sheet_width - bounds[2] < 50:
            edge_bonus += 50
        if self.sheet_height - bounds[3] < 50:
            edge_bonus += 50
        score += edge_bonus

        return score

    def _has_collisions(self, test_polygon: Polygon, tolerance=0.0) -> bool:
        """Проверка пересечений с допуском."""
        test_bounds = test_polygon.bounds
        for placed_polygon in self.placed_polygons:
            placed_bounds = placed_polygon.bounds
            dx = max(0, max(test_bounds[0] - placed_bounds[2], placed_bounds[0] - test_bounds[2]))
            dy = max(0, max(test_bounds[1] - placed_bounds[3], placed_bounds[1] - test_bounds[3]))
            if np.sqrt(dx * dx + dy * dy) > tolerance + 1.0:
                continue
            if test_polygon.distance(placed_polygon) < tolerance:
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
        sheet_area = sheet_width_mm * sheet_height_mm * packer.current_sheet
        usage_percent = (total_area / sheet_area) * 100
        logger.info(
            f"Улучшенный алгоритм: размещено {len(placed)}, использование {usage_percent:.1f}% через {packer.current_sheet} листа(ов)"
        )

    return placed, unplaced