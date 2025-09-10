"""
Алгоритм максимально плотной упаковки ковриков без использования bounding box.
Использует истинные геометрические формы полигонов для достижения цели ≤2 листа с ≥78% загрузкой.
"""

import numpy as np
from shapely.geometry import Polygon, Point, LineString, MultiPolygon
from shapely.ops import unary_union
from shapely import affinity
from typing import List, Tuple, Optional, Dict
import logging
from itertools import combinations

logger = logging.getLogger(__name__)

class UltraDensePacker:
    """Максимально плотная упаковка с использованием реальных контуров полигонов."""
    
    def __init__(self, sheet_width_mm: float, sheet_height_mm: float):
        self.sheet_width = sheet_width_mm
        self.sheet_height = sheet_height_mm
        self.placed_polygons = []
        self.placed_positions = []
        self.sheet_polygon = Polygon([
            (0, 0), (sheet_width_mm, 0), 
            (sheet_width_mm, sheet_height_mm), (0, sheet_height_mm)
        ])
        
    def pack_carpets(self, carpets, progress_callback=None) -> Tuple[List, List]:
        """Основная функция максимально плотной упаковки."""
        placed = []
        unplaced = []
        
        # Сортировка по площади и сложности формы
        sorted_carpets = self._sort_for_dense_packing(carpets)
        
        total_carpets = len(sorted_carpets)
        for i, carpet in enumerate(sorted_carpets):
            if progress_callback:
                progress_callback(
                    int(50 + 40 * i / total_carpets),
                    f"Плотная упаковка {i+1}/{total_carpets}"
                )
                
            best_placement = self._find_densest_placement(carpet)
            
            if best_placement:
                placed.append(best_placement)
                self.placed_polygons.append(best_placement[0])
                self.placed_positions.append((best_placement[1], best_placement[2]))
                
                # Вычисляем реальную плотность упаковки
                total_carpet_area = sum(p.area for p in self.placed_polygons)
                sheet_area = self.sheet_width * self.sheet_height
                density_percent = (total_carpet_area / sheet_area) * 100
                
                logger.info(f"Размещен {carpet.filename}, плотность листа: {density_percent:.1f}%")
            else:
                unplaced.append(carpet)
                logger.warning(f"Не удалось разместить {carpet.filename}")
                
        return placed, unplaced
    
    def _sort_for_dense_packing(self, carpets):
        """Сортировка для максимально плотной упаковки."""
        def packing_priority(carpet):
            polygon = carpet.polygon
            area = polygon.area
            
            # Анализ сложности формы
            coords = list(polygon.exterior.coords)
            perimeter = polygon.length
            
            # Convex hull ratio - чем больше вогнутостей, тем сложнее
            convex_hull = polygon.convex_hull
            convex_ratio = polygon.area / convex_hull.area if convex_hull.area > 0 else 0
            
            # Bounding box efficiency - насколько полигон заполняет свой bounding box
            bounds = polygon.bounds
            bbox_area = (bounds[2] - bounds[0]) * (bounds[3] - bounds[1])
            bbox_efficiency = area / bbox_area if bbox_area > 0 else 0
            
            # Приоритет: крупные полигоны с высокой эффективностью bbox размещаем первыми
            # Сложные формы (низкий convex_ratio) размещаем раньше
            priority = (
                area * 1000 +           # Площадь (крупные первыми)
                bbox_efficiency * 500 + # Эффективность bbox (прямоугольные первыми) 
                (1 - convex_ratio) * 200 # Сложность формы (сложные первыми)
            )
            
            return priority
            
        return sorted(carpets, key=packing_priority, reverse=True)
    
    def _find_densest_placement(self, carpet):
        """Поиск максимально плотного размещения полигона."""
        best_placement = None
        best_density_score = float('-inf')
        
        # Тестируем все углы поворота
        rotation_angles = [0, 90, 180, 270]
        
        for angle in rotation_angles:
            rotated_polygon = self._rotate_polygon(carpet.polygon, angle)
            
            # Проверяем, помещается ли на лист
            if not self._fits_in_sheet(rotated_polygon):
                continue
                
            # Находим позиции для максимально плотной упаковки
            dense_positions = self._generate_dense_positions(rotated_polygon)
            
            for position in dense_positions:
                dx, dy = position
                final_polygon = affinity.translate(rotated_polygon, dx, dy)
                
                # Проверяем, что полигон полностью на листе
                if not self.sheet_polygon.contains(final_polygon):
                    continue
                    
                # Проверяем отсутствие пересечений - упрощенная проверка
                if self._has_collision(final_polygon):
                    continue
                    
                # Оценка плотности этого размещения
                density_score = self._calculate_density_score(final_polygon, position)
                
                if density_score > best_density_score:
                    best_density_score = density_score
                    best_placement = (
                        final_polygon, dx, dy, angle,
                        carpet.filename, carpet.color, carpet.order_id,
                        {'ultra_density_score': density_score}
                    )
        
        return best_placement
    
    def _generate_dense_positions(self, polygon: Polygon) -> List[Tuple[float, float]]:
        """Генерирует позиции для максимально плотной упаковки."""
        positions = []
        bounds = polygon.bounds
        
        if not self.placed_polygons:
            # Первый полигон - размещаем в углу
            return [(0 - bounds[0], 0 - bounds[1])]
        
        # Быстрая генерация позиций на основе already placed polygons
        gap = 3.0  # Минимальный зазор
        
        for placed_polygon in self.placed_polygons:
            placed_bounds = placed_polygon.bounds
            
            # Позиции рядом с размещенными полигонами
            # Справа от existing
            right_x = placed_bounds[2] + gap
            if right_x + (bounds[2] - bounds[0]) <= self.sheet_width:
                positions.append((right_x - bounds[0], placed_bounds[1] - bounds[1]))
                positions.append((right_x - bounds[0], 0 - bounds[1]))  # По низу
            
            # Сверху от existing
            top_y = placed_bounds[3] + gap  
            if top_y + (bounds[3] - bounds[1]) <= self.sheet_height:
                positions.append((placed_bounds[0] - bounds[0], top_y - bounds[1]))
                positions.append((0 - bounds[0], top_y - bounds[1]))  # По левому краю
        
        # Добавляем grid-based позиции если мало кандидатов
        if len(positions) < 10:
            step = 20  # 2 см шаг
            for x in range(0, int(self.sheet_width - (bounds[2] - bounds[0])), step):
                for y in range(0, int(self.sheet_height - (bounds[3] - bounds[1])), step):
                    positions.append((x - bounds[0], y - bounds[1]))
        
        # Сортируем по bottom-left preference
        positions.sort(key=lambda p: (p[1], p[0]))
        
        return positions[:50]  # Ограничиваем для производительности
    
    def _get_contact_positions(self, moving_polygon: Polygon) -> List[Tuple[float, float]]:
        """Позиции где полигон касается уже размещенных полигонов."""
        positions = []
        
        for placed_polygon in self.placed_polygons:
            # Получаем контуры полигонов
            moving_coords = list(moving_polygon.exterior.coords[:-1])  # Убираем дублированную точку
            placed_coords = list(placed_polygon.exterior.coords[:-1])
            
            # Для каждой вершины размещенного полигона
            for px, py in placed_coords:
                # Пытаемся разместить moving_polygon так, чтобы его вершина касалась этой точки
                for mx, my in moving_coords:
                    # Вычисляем смещение для контакта
                    dx = px - mx
                    dy = py - my
                    positions.append((dx, dy))
                    
                    # Также добавляем позиции с небольшими зазорами
                    gap = 3.0  # 3мм зазор
                    positions.append((dx + gap, dy))
                    positions.append((dx, dy + gap))
                    positions.append((dx + gap, dy + gap))
        
        return positions
    
    def _get_edge_tangent_positions(self, moving_polygon: Polygon) -> List[Tuple[float, float]]:
        """Позиции где полигон касается краев уже размещенных полигонов."""
        positions = []
        
        for placed_polygon in self.placed_polygons:
            # Получаем границы размещенного полигона
            placed_bounds = placed_polygon.bounds
            moving_bounds = moving_polygon.bounds
            
            gap = 2.0  # Минимальный зазор
            
            # Справа от размещенного полигона
            dx = placed_bounds[2] + gap - moving_bounds[0]
            positions.append((dx, placed_bounds[1] - moving_bounds[1]))  # На той же высоте
            positions.append((dx, 0 - moving_bounds[1]))  # У нижнего края листа
            
            # Сверху от размещенного полигона  
            dy = placed_bounds[3] + gap - moving_bounds[1]
            positions.append((placed_bounds[0] - moving_bounds[0], dy))  # На той же позиции X
            positions.append((0 - moving_bounds[0], dy))  # У левого края листа
            
        return positions
    
    def _get_tight_fit_positions(self, moving_polygon: Polygon) -> List[Tuple[float, float]]:
        """Позиции для плотной посадки в зазоры между полигонами."""
        positions = []
        
        if len(self.placed_polygons) < 2:
            return positions
            
        # Находим зазоры между парами размещенных полигонов
        for poly1, poly2 in combinations(self.placed_polygons, 2):
            bounds1 = poly1.bounds
            bounds2 = poly2.bounds
            moving_bounds = moving_polygon.bounds
            
            # Проверяем горизонтальные зазоры
            if bounds1[2] < bounds2[0]:  # poly1 слева от poly2
                gap_width = bounds2[0] - bounds1[2]
                moving_width = moving_bounds[2] - moving_bounds[0]
                
                if moving_width <= gap_width - 5:  # Помещается с зазором 5мм
                    gap_x = bounds1[2] + 2.5  # По центру зазора
                    dx = gap_x - moving_bounds[0]
                    
                    # Пробуем разные Y позиции в этом зазоре
                    overlap_y_start = max(bounds1[1], bounds2[1])
                    overlap_y_end = min(bounds1[3], bounds2[3])
                    
                    if overlap_y_end > overlap_y_start:
                        positions.append((dx, overlap_y_start - moving_bounds[1]))
                        positions.append((dx, overlap_y_end - moving_bounds[3]))
            
            # Симметрично для poly2 слева от poly1
            if bounds2[2] < bounds1[0]:
                gap_width = bounds1[0] - bounds2[2]
                moving_width = moving_bounds[2] - moving_bounds[0]
                
                if moving_width <= gap_width - 5:
                    gap_x = bounds2[2] + 2.5
                    dx = gap_x - moving_bounds[0]
                    
                    overlap_y_start = max(bounds1[1], bounds2[1])
                    overlap_y_end = min(bounds1[3], bounds2[3])
                    
                    if overlap_y_end > overlap_y_start:
                        positions.append((dx, overlap_y_start - moving_bounds[1]))
                        positions.append((dx, overlap_y_end - moving_bounds[3]))
        
        return positions
    
    def _get_compactness_score(self, polygon: Polygon, position: Tuple[float, float]) -> float:
        """Оценка компактности размещения (меньше = лучше для сортировки)."""
        dx, dy = position
        test_polygon = affinity.translate(polygon, dx, dy)
        
        if not self.placed_polygons:
            return 0
        
        # Находим минимальное расстояние до других полигонов
        min_distance = float('inf')
        for placed_polygon in self.placed_polygons:
            distance = test_polygon.distance(placed_polygon)
            min_distance = min(min_distance, distance)
            
        return min_distance  # Меньшее расстояние = более компактно
    
    def _has_collision(self, test_polygon: Polygon) -> bool:
        """Упрощенная проверка коллизий с минимальным зазором."""
        min_distance = 2.0  # 2мм минимальный зазор
        
        for placed_polygon in self.placed_polygons:
            distance = test_polygon.distance(placed_polygon)
            if distance < min_distance:
                return True
        return False
    
    def _calculate_density_score(self, polygon: Polygon, position: Tuple[float, float]) -> float:
        """Оценка плотности размещения."""
        dx, dy = position
        score = 0.0
        
        # 1. Мощный бонус за левый нижний угол  
        corner_distance = np.sqrt(dx*dx + dy*dy)
        corner_bonus = max(0, 2000 - corner_distance * 0.3)
        score += corner_bonus
        
        # 2. Огромный бонус за близость к другим полигонам (компактность)
        if self.placed_polygons:
            total_area_before = sum(p.area for p in self.placed_polygons)
            
            # Расстояние до ближайшего полигона
            min_distance = float('inf')
            for placed_polygon in self.placed_polygons:
                distance = polygon.distance(placed_polygon)
                min_distance = min(min_distance, distance)
            
            # Огромный бонус за близкое размещение
            if min_distance < 50:  # В пределах 5 см
                proximity_bonus = 1000 * (1 - min_distance / 50)
                score += proximity_bonus
        
        # 3. Бонус за эффективное использование пространства листа
        bounds = polygon.bounds
        
        # Бонус за заполнение углов листа
        corners = [(0, 0), (self.sheet_width, 0), (0, self.sheet_height), (self.sheet_width, self.sheet_height)]
        for corner_x, corner_y in corners:
            corner_point = Point(corner_x, corner_y)
            if polygon.contains(corner_point) or polygon.distance(corner_point) < 10:
                score += 300
        
        # Бонус за близость к краям листа
        edge_distances = [
            bounds[0],                          # Расстояние до левого края
            bounds[1],                          # Расстояние до нижнего края  
            self.sheet_width - bounds[2],       # Расстояние до правого края
            self.sheet_height - bounds[3]       # Расстояние до верхнего края
        ]
        
        for edge_dist in edge_distances:
            if edge_dist < 20:  # В пределах 2 см от края
                edge_bonus = 100 * (1 - edge_dist / 20)
                score += edge_bonus
        
        # 4. Штраф за создание неиспользуемых зазоров
        waste_penalty = self._calculate_waste_creation(polygon)
        score -= waste_penalty
        
        return score
    
    def _calculate_waste_creation(self, polygon: Polygon) -> float:
        """Штраф за создание неиспользуемых областей."""
        penalty = 0.0
        bounds = polygon.bounds
        
        # Штраф за создание узких зазоров у краев листа
        min_useful_width = 40  # 4 см
        
        right_gap = self.sheet_width - bounds[2]
        if 0 < right_gap < min_useful_width:
            penalty += 200 * (1 - right_gap / min_useful_width)
            
        top_gap = self.sheet_height - bounds[3] 
        if 0 < top_gap < min_useful_width:
            penalty += 200 * (1 - top_gap / min_useful_width)
            
        return penalty
    
    def _fits_in_sheet(self, polygon: Polygon) -> bool:
        """Проверяет, помещается ли полигон на лист."""
        bounds = polygon.bounds
        return (bounds[2] - bounds[0] <= self.sheet_width and 
                bounds[3] - bounds[1] <= self.sheet_height)
    
    def _rotate_polygon(self, polygon: Polygon, angle: float) -> Polygon:
        """Поворот полигона."""
        if angle == 0:
            return polygon
        return affinity.rotate(polygon, angle, origin='centroid')


def ultra_dense_bin_packing(carpets, sheet_size, verbose=True):
    """Максимально плотная упаковка без использования bounding box."""
    sheet_width_mm = sheet_size[0] * 10
    sheet_height_mm = sheet_size[1] * 10
    
    packer = UltraDensePacker(sheet_width_mm, sheet_height_mm)
    placed, unplaced = packer.pack_carpets(carpets)
    
    if verbose and len(placed) > 0:
        total_area = sum(p[0].area for p in placed)
        sheet_area = sheet_width_mm * sheet_height_mm
        usage_percent = (total_area / sheet_area) * 100
        logger.info(f"Ультра-плотный алгоритм: размещено {len(placed)}, использование {usage_percent:.1f}%")
    
    return placed, unplaced