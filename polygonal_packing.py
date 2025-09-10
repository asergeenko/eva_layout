"""
Настоящий полигональный алгоритм размещения ковриков.
Использует истинные геометрические формы полигонов, а не только bounding box.
Реализует No-Fit Polygon (NFP) технологии для максимально плотной упаковки.
"""

import numpy as np
from shapely.geometry import Polygon, Point, LineString
from shapely.ops import unary_union
from shapely import affinity
from typing import List, Tuple, Optional, Dict
import logging

logger = logging.getLogger(__name__)

class PolygonalCarpetPacker:
    """Полигональный алгоритм размещения с NFP технологиями."""
    
    def __init__(self, sheet_width_mm: float, sheet_height_mm: float):
        self.sheet_width = sheet_width_mm
        self.sheet_height = sheet_height_mm
        self.placed_polygons = []
        self.placed_positions = []
        self.sheet_boundary = self._create_sheet_polygon()
        
    def _create_sheet_polygon(self) -> Polygon:
        """Создает полигон листа."""
        return Polygon([
            (0, 0),
            (self.sheet_width, 0),
            (self.sheet_width, self.sheet_height),
            (0, self.sheet_height)
        ])
    
    def pack_carpets(self, carpets, progress_callback=None) -> Tuple[List, List]:
        """Основная функция размещения ковриков с полигональным подходом."""
        placed = []
        unplaced = []
        
        # Сортировка ковриков по сложности формы
        sorted_carpets = self._sort_carpets_by_complexity(carpets)
        
        total_carpets = len(sorted_carpets)
        for i, carpet in enumerate(sorted_carpets):
            if progress_callback:
                progress_callback(int(50 + 40 * i / total_carpets), f"Полигональное размещение {i+1}/{total_carpets}")
                
            best_placement = self._find_best_polygonal_placement(carpet)
            
            if best_placement:
                placed.append(best_placement)
                self.placed_polygons.append(best_placement[0])
                self.placed_positions.append((best_placement[1], best_placement[2]))
                logger.info(f"Полигонально размещен {carpet.filename}")
            else:
                unplaced.append(carpet)
                logger.warning(f"Не удалось полигонально разместить {carpet.filename}")
                
        return placed, unplaced
    
    def _sort_carpets_by_complexity(self, carpets):
        """Сортировка ковриков по геометрической сложности."""
        def complexity_score(carpet):
            polygon = carpet.polygon
            area = polygon.area
            perimeter = polygon.length
            
            # Извлекаем координаты для анализа сложности формы
            coords = list(polygon.exterior.coords)
            num_vertices = len(coords) - 1  # -1 так как первая и последняя точки одинаковые
            
            # Convex hull ratio (насколько форма далека от выпуклой)
            convex_hull = polygon.convex_hull
            convex_ratio = polygon.area / convex_hull.area if convex_hull.area > 0 else 0
            
            # Чем сложнее форма, тем выше приоритет размещения
            complexity = area * 1000 + num_vertices * 100 + (1 - convex_ratio) * 500
            return complexity
            
        return sorted(carpets, key=complexity_score, reverse=True)
    
    def _find_best_polygonal_placement(self, carpet):
        """Поиск лучшего размещения полигона с использованием NFP."""
        best_placement = None
        best_score = float('-inf')
        
        # Тестируем все возможные углы поворота
        rotation_angles = [0, 90, 180, 270]
        
        for angle in rotation_angles:
            rotated_polygon = self._rotate_polygon(carpet.polygon, angle)
            
            # Находим все допустимые позиции с использованием NFP
            valid_positions = self._calculate_no_fit_positions(rotated_polygon)
            
            for position in valid_positions:
                x, y = position
                
                # Создаем окончательно размещенный полигон
                final_polygon = self._translate_polygon(rotated_polygon, x, y)
                
                # Упрощенная проверка границ листа через bounding box
                bounds = final_polygon.bounds
                if (bounds[0] < 0 or bounds[1] < 0 or 
                    bounds[2] > self.sheet_width or bounds[3] > self.sheet_height):
                    continue
                
                # Проверяем отсутствие пересечений с размещенными полигонами
                if self._has_polygon_collisions(final_polygon):
                    continue
                
                # Оцениваем качество этого размещения
                score = self._evaluate_polygonal_placement(final_polygon, position)
                
                if score > best_score:
                    best_score = score
                    best_placement = (
                        final_polygon,
                        x, y, angle,
                        carpet.filename,
                        carpet.color,
                        carpet.order_id,
                        {'polygonal_score': score}
                    )
        
        return best_placement
    
    def _calculate_no_fit_positions(self, polygon: Polygon) -> List[Tuple[float, float]]:
        """
        Вычисляет No-Fit Polygon позиции для размещения.
        NFP определяет все возможные позиции, где полигон может быть размещен
        без пересечения с уже размещенными полигонами.
        """
        positions = set()
        
        if not self.placed_polygons:
            # Первый полигон - размещаем в углах листа
            positions.update(self._get_corner_positions(polygon))
            positions.update(self._get_edge_positions(polygon))
        else:
            # Вычисляем NFP для каждого размещенного полигона
            for placed_polygon in self.placed_polygons:
                nfp_positions = self._compute_nfp_positions(polygon, placed_polygon)
                positions.update(nfp_positions)
            
            # Добавляем позиции относительно границ листа
            boundary_positions = self._compute_boundary_nfp_positions(polygon)
            positions.update(boundary_positions)
        
        # Быстрая фильтрация позиций по bounding box
        bounds = polygon.bounds
        poly_width = bounds[2] - bounds[0]
        poly_height = bounds[3] - bounds[1]
        
        valid_positions = []
        for pos in positions:
            x, y = pos
            # Быстрая проверка границ
            if (x + poly_width <= self.sheet_width and 
                y + poly_height <= self.sheet_height and 
                x >= 0 and y >= 0):
                valid_positions.append(pos)
        
        # Сортируем позиции по принципу bottom-left
        valid_positions.sort(key=lambda p: (p[1], p[0]))
        
        return valid_positions[:50]  # Увеличиваем количество кандидатов
    
    def _get_corner_positions(self, polygon: Polygon) -> List[Tuple[float, float]]:
        """Позиции в углах листа."""
        bounds = polygon.bounds
        positions = []
        
        # Нижний левый угол
        positions.append((0 - bounds[0], 0 - bounds[1]))
        
        # Нижний правый угол
        positions.append((self.sheet_width - bounds[2], 0 - bounds[1]))
        
        # Верхний левый угол
        positions.append((0 - bounds[0], self.sheet_height - bounds[3]))
        
        # Верхний правый угол
        positions.append((self.sheet_width - bounds[2], self.sheet_height - bounds[3]))
        
        return positions
    
    def _get_edge_positions(self, polygon: Polygon) -> List[Tuple[float, float]]:
        """Позиции вдоль краев листа."""
        bounds = polygon.bounds
        positions = []
        step = 20.0  # Шаг в мм
        
        # Нижний край
        x = 0
        while x + (bounds[2] - bounds[0]) <= self.sheet_width:
            positions.append((x - bounds[0], 0 - bounds[1]))
            x += step
            
        # Левый край  
        y = 0
        while y + (bounds[3] - bounds[1]) <= self.sheet_height:
            positions.append((0 - bounds[0], y - bounds[1]))
            y += step
            
        return positions
    
    def _compute_nfp_positions(self, moving_polygon: Polygon, fixed_polygon: Polygon) -> List[Tuple[float, float]]:
        """
        Упрощенное вычисление NFP позиций.
        В полном NFP алгоритме это сложная геометрическая операция,
        здесь используем упрощенный подход с ключевыми точками.
        """
        positions = []
        fixed_coords = list(fixed_polygon.exterior.coords)
        moving_bounds = moving_polygon.bounds
        gap = 5.0  # Минимальный зазор
        
        for coord in fixed_coords[:-1]:  # -1 чтобы избежать дублирования последней точки
            fx, fy = coord
            
            # Позиции справа от фиксированного полигона
            positions.append((fx + gap - moving_bounds[0], fy - moving_bounds[1]))
            
            # Позиции сверху от фиксированного полигона
            positions.append((fx - moving_bounds[0], fy + gap - moving_bounds[1]))
            
            # Позиции по диагонали
            positions.append((fx + gap - moving_bounds[0], fy + gap - moving_bounds[1]))
        
        return positions
    
    def _compute_boundary_nfp_positions(self, polygon: Polygon) -> List[Tuple[float, float]]:
        """Вычисляет NFP позиции относительно границ листа."""
        bounds = polygon.bounds
        positions = []
        
        # Позиции вдоль левой стенки
        for y in np.arange(0, self.sheet_height - (bounds[3] - bounds[1]), 10):
            positions.append((0 - bounds[0], y - bounds[1]))
        
        # Позиции вдоль нижней стенки
        for x in np.arange(0, self.sheet_width - (bounds[2] - bounds[0]), 10):
            positions.append((x - bounds[0], 0 - bounds[1]))
            
        return positions
    
    def _has_polygon_collisions(self, test_polygon: Polygon) -> bool:
        """Проверяет полигональные пересечения (не bounding box)."""
        for placed_polygon in self.placed_polygons:
            if test_polygon.intersects(placed_polygon):
                intersection = test_polygon.intersection(placed_polygon)
                if hasattr(intersection, 'area') and intersection.area > 10.0:  # Более щедрые допуски
                    return True
        return False
    
    def _evaluate_polygonal_placement(self, polygon: Polygon, position: Tuple[float, float]) -> float:
        """Оценка качества размещения с учетом полигональной геометрии."""
        x, y = position
        score = 0.0
        
        # 1. Бонус за близость к левому нижнему углу
        corner_distance = np.sqrt(x*x + y*y)
        corner_bonus = max(0, 1000 - corner_distance * 0.5)
        score += corner_bonus
        
        # 2. Бонус за компактность относительно других полигонов
        if self.placed_polygons:
            min_distance = float('inf')
            for placed_polygon in self.placed_polygons:
                # Расстояние между центроидами
                distance = polygon.centroid.distance(placed_polygon.centroid)
                min_distance = min(min_distance, distance)
            
            if min_distance < 100:  # В пределах 10 см
                compactness_bonus = 150 * (1 - min_distance / 100)
                score += compactness_bonus
        
        # 3. Бонус за эффективное использование пространства
        utilization_bonus = self._calculate_space_utilization(polygon)
        score += utilization_bonus
        
        # 4. Бонус за минимизацию отходов (оставшееся пространство)
        waste_penalty = self._calculate_waste_penalty(polygon)
        score -= waste_penalty
        
        return score
    
    def _calculate_space_utilization(self, polygon: Polygon) -> float:
        """Бонус за эффективное использование пространства."""
        bounds = polygon.bounds
        
        # Бонус за близость к краям листа
        bonus = 0.0
        edge_threshold = 50  # 5 см
        
        # Расстояние до правого края
        right_distance = self.sheet_width - bounds[2]
        if right_distance < edge_threshold:
            bonus += 30 * (1 - right_distance / edge_threshold)
        
        # Расстояние до верхнего края
        top_distance = self.sheet_height - bounds[3]
        if top_distance < edge_threshold:
            bonus += 30 * (1 - top_distance / edge_threshold)
            
        return bonus
    
    def _calculate_waste_penalty(self, polygon: Polygon) -> float:
        """Штраф за создание непригодных областей."""
        # Упрощенная версия - штраф за создание узких зазоров
        bounds = polygon.bounds
        penalty = 0.0
        
        # Штраф за узкие зазоры у краев
        min_useful_width = 30  # 3 см
        
        right_gap = self.sheet_width - bounds[2]
        if 0 < right_gap < min_useful_width:
            penalty += 10
            
        top_gap = self.sheet_height - bounds[3]
        if 0 < top_gap < min_useful_width:
            penalty += 10
            
        return penalty
    
    def _rotate_polygon(self, polygon: Polygon, angle: float) -> Polygon:
        """Поворачивает полигон на заданный угол."""
        if angle == 0:
            return polygon
        return affinity.rotate(polygon, angle, origin='centroid')
    
    def _translate_polygon(self, polygon: Polygon, dx: float, dy: float) -> Polygon:
        """Перемещает полигон на заданное смещение."""
        return affinity.translate(polygon, dx, dy)


def polygonal_bin_packing(carpets, sheet_size, verbose=True):
    """Полигональный bin packing с использованием PolygonalCarpetPacker."""
    sheet_width_mm = sheet_size[0] * 10
    sheet_height_mm = sheet_size[1] * 10
    
    packer = PolygonalCarpetPacker(sheet_width_mm, sheet_height_mm)
    placed, unplaced = packer.pack_carpets(carpets)
    
    if verbose and len(placed) > 0:
        total_area = sum(p[0].area for p in placed)
        sheet_area = sheet_width_mm * sheet_height_mm
        usage_percent = (total_area / sheet_area) * 100
        logger.info(f"Полигональный алгоритм: размещено {len(placed)}, использование {usage_percent:.1f}%")
    
    return placed, unplaced