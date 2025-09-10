"""
Улучшенный алгоритм раскладки с использованием No-Fit Polygon (NFP) подходов
для максимальной плотности размещения автомобильных ковриков.
"""

import numpy as np
from shapely.geometry import Polygon, Point
from shapely.ops import unary_union
from shapely import affinity
from typing import List, Tuple, Optional, Dict
import logging

logger = logging.getLogger(__name__)

class AdvancedCarpetPacker:
    """Продвинутый алгоритм размещения ковриков с использованием NFP подходов."""
    
    def __init__(self, sheet_width_mm: float, sheet_height_mm: float):
        self.sheet_width = sheet_width_mm
        self.sheet_height = sheet_height_mm
        self.placed_polygons = []
        self.placed_positions = []
        
    def pack_carpets(self, carpets, progress_callback=None) -> Tuple[List, List]:
        """Основная функция размещения ковриков."""
        placed = []
        unplaced = []
        
        # Улучшенная сортировка по нескольким критериям
        sorted_carpets = self._sort_carpets_advanced(carpets)
        
        total_carpets = len(sorted_carpets)
        for i, carpet in enumerate(sorted_carpets):
            if progress_callback:
                progress_callback(int(50 + 40 * i / total_carpets), f"Размещение коврика {i+1}/{total_carpets}")
                
            best_placement = self._find_best_placement(carpet)
            
            if best_placement:
                placed.append(best_placement)
                self.placed_polygons.append(best_placement[0])
                self.placed_positions.append((best_placement[1], best_placement[2]))
                # Extract density from the metadata if available
                density = best_placement[7].get('density', 0) if len(best_placement) > 7 and isinstance(best_placement[7], dict) else 0
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
            
            # Коэффициент сложности формы (отношение площади к площади ограничивающего прямоугольника)
            bbox_area = width * height
            complexity = area / bbox_area if bbox_area > 0 else 0
            
            # Коэффициент соотношения сторон (чем ближе к квадрату, тем легче размещать)
            aspect_ratio = max(width, height) / min(width, height) if min(width, height) > 0 else float('inf')
            
            # Приоритет: крупные, сложные, близкие к квадрату формы размещаем первыми
            return (area * 1000, complexity * 500, -aspect_ratio * 100)
            
        return sorted(carpets, key=carpet_priority, reverse=True)
    
    def _find_best_placement(self, carpet):
        """Поиск лучшего размещения для коврика с учетом всех ориентаций."""
        best_placement = None
        best_score = float('-inf')
        
        # Тестируем все возможные углы поворота
        rotation_angles = [0, 90, 180, 270]
        
        for angle in rotation_angles:
            rotated_polygon = self._rotate_carpet(carpet.polygon, angle)
            
            # Проверяем, помещается ли повернутый коврик на лист
            if not self._fits_on_sheet(rotated_polygon):
                continue
                
            # Ищем оптимальное положение для этой ориентации
            position, score = self._find_optimal_position(rotated_polygon, carpet)
            
            if position and score > best_score:
                best_score = score
                # Создаем окончательно размещенный полигон
                final_polygon = self._translate_polygon(rotated_polygon, position[0], position[1])
                best_placement = (
                    final_polygon,
                    position[0],
                    position[1], 
                    angle,
                    carpet.filename,
                    carpet.color,
                    carpet.order_id,
                    {'density': score}  # Дополнительная информация
                )
        
        return best_placement
    
    def _find_optimal_position(self, polygon: Polygon, carpet) -> Tuple[Optional[Tuple[float, float]], float]:
        """Поиск оптимального положения полигона используя улучшенный алгоритм."""
        bounds = polygon.bounds
        poly_width = bounds[2] - bounds[0]
        poly_height = bounds[3] - bounds[1]
        
        # Генерируем кандидатов для размещения
        candidates = self._generate_placement_candidates(polygon)
        
        best_position = None
        best_score = float('-inf')
        tested_positions = 0
        valid_positions = 0
        
        for x, y in candidates:
            tested_positions += 1
            # Быстрая проверка границ листа
            if (x + poly_width > self.sheet_width or 
                y + poly_height > self.sheet_height or 
                x < 0 or y < 0):
                continue
            
            # Создаем тестовый полигон в этой позиции  
            # x,y - это где должен быть левый нижний угол bounding box
            # нужно перенести полигон туда
            dx = x - bounds[0]  # сдвиг по X
            dy = y - bounds[1]  # сдвиг по Y
            test_polygon = self._translate_polygon(polygon, dx, dy)
            
            # Проверяем пересечения с уже размещенными полигонами
            if self._has_collisions(test_polygon):
                continue
            
            valid_positions += 1    
            # Оцениваем качество этого размещения
            score = self._evaluate_placement(test_polygon, x, y)
            
            if score > best_score:
                best_score = score
                best_position = (dx, dy)  # Используем уже вычисленные dx, dy
        
        # Debug info
        if best_position is None and len(self.placed_polygons) > 0:
            logger.debug(f"Не найдено место для {carpet.filename} (размер {poly_width:.0f}x{poly_height:.0f}): {tested_positions} кандидатов, {valid_positions} прошли проверки")
            # Debug first few candidates
            placed_bounds = self.placed_polygons[0].bounds if self.placed_polygons else None
            if placed_bounds:
                logger.debug(f"Первый размещенный полигон: {placed_bounds[2]-placed_bounds[0]:.0f}x{placed_bounds[3]-placed_bounds[1]:.0f} в ({placed_bounds[0]:.0f},{placed_bounds[1]:.0f})")
            if len(candidates) > 0:
                logger.debug(f"Первые кандидаты: {candidates[:5]}")
        
        return best_position, best_score
    
    def _generate_placement_candidates(self, polygon: Polygon) -> List[Tuple[float, float]]:
        """Генерирует кандидатов для размещения полигона."""
        candidates = set()
        bounds = polygon.bounds
        poly_width = bounds[2] - bounds[0]
        poly_height = bounds[3] - bounds[1]
        
        # 1. Позиции по краям листа (bottom-left fill) - только если нет размещенных полигонов
        if len(self.placed_polygons) == 0:
            step_size = min(20.0, min(poly_width, poly_height) / 5)  # Увеличенный шаг
            
            # Нижний край
            for x in np.arange(0, self.sheet_width - poly_width + step_size, step_size):
                candidates.add((x, 0))
            
            # Левый край  
            for y in np.arange(0, self.sheet_height - poly_height + step_size, step_size):
                candidates.add((0, y))
        
        # 2. Простые позиции около уже размещенных полигонов
        for placed_polygon in self.placed_polygons:
            placed_bounds = placed_polygon.bounds
            gap = 5.0  # Увеличенный зазор для надежности
            
            # Справа от размещенного полигона
            x = placed_bounds[2] + gap
            if x + poly_width <= self.sheet_width:
                candidates.add((x, placed_bounds[1]))  # На той же высоте
                candidates.add((x, 0))  # У нижнего края
                # Добавляем больше позиций по вертикали
                for offset_y in [10, 20, 50, 100]:
                    if placed_bounds[1] + offset_y + poly_height <= self.sheet_height:
                        candidates.add((x, placed_bounds[1] + offset_y))
            
            # Сверху от размещенного полигона
            y = placed_bounds[3] + gap  
            if y + poly_height <= self.sheet_height:
                candidates.add((placed_bounds[0], y))  # На той же позиции X
                candidates.add((0, y))  # У левого края
                # Добавляем больше позиций по горизонтали
                for offset_x in [10, 20, 50, 100]:
                    if placed_bounds[0] + offset_x + poly_width <= self.sheet_width:
                        candidates.add((placed_bounds[0] + offset_x, y))
        
        # 3. Случайные позиции для исследования пространства (Monte Carlo) - отключено для скорости
        # if len(self.placed_polygons) > 3:  # Только когда уже есть несколько полигонов
        #     np.random.seed(42)  # Для воспроизводимости
        #     for _ in range(5):  # Сокращено для скорости
        #         x = np.random.uniform(0, self.sheet_width - poly_width)
        #         y = np.random.uniform(0, self.sheet_height - poly_height)
        #         candidates.add((x, y))
        
        # Сортируем кандидатов по принципу bottom-left
        candidates_list = list(candidates)
        candidates_list.sort(key=lambda pos: (pos[1], pos[0]))  # Сначала по Y, потом по X
        
        # Ограничиваем количество кандидатов для производительности
        max_candidates = 50  # Сокращено для скорости 
        if len(candidates_list) > max_candidates:
            candidates_list = candidates_list[:max_candidates]
            
        return candidates_list
    
    def _evaluate_placement(self, polygon: Polygon, x: float, y: float) -> float:
        """Оценивает качество размещения полигона (больше = лучше)."""
        score = 0.0
        bounds = polygon.bounds
        
        # 1. Сильный бонус за близость к нижнему левому углу (bottom-left принцип)
        corner_score = 1000 - (x * 0.2 + y * 0.2)  # Увеличен коэффициент
        score += corner_score
        
        # 2. Мощный бонус за компактность размещения
        if self.placed_polygons:
            # Находим ближайший размещенный полигон
            min_distance = float('inf')
            for placed_polygon in self.placed_polygons:
                # Используем distance между bounding boxes для скорости
                placed_bounds = placed_polygon.bounds
                dx = max(0, max(bounds[0] - placed_bounds[2], placed_bounds[0] - bounds[2]))
                dy = max(0, max(bounds[1] - placed_bounds[3], placed_bounds[1] - bounds[3]))
                distance = np.sqrt(dx*dx + dy*dy)
                min_distance = min(min_distance, distance)
            
            # Большой бонус за близость к уже размещенным полигонам
            if min_distance < 200:  # В пределах 20 см
                compactness_bonus = 200 * (1 - min_distance / 200)  # Увеличен бонус
                score += compactness_bonus
        
        # 3. Бонус за максимальное использование пространства
        utilization_bonus = self._calculate_space_utilization_bonus(polygon)
        score += utilization_bonus
        
        # 4. Небольшой штраф за создание узких зазоров
        waste_penalty = self._calculate_waste_penalty(polygon)
        score -= waste_penalty * 0.5  # Уменьшен штраф
        
        return score
    
    def _calculate_waste_penalty(self, polygon: Polygon) -> float:
        """Рассчитывает штраф за создание непригодных областей (упрощенная версия)."""
        # Упрощенный подход - минимальный штраф, чтобы не блокировать размещение
        bounds = polygon.bounds
        
        # Небольшой штраф если полигон создает очень узкие зазоры у краев
        penalty = 0.0
        
        # Проверяем только критически узкие зазоры (менее 5 см)
        min_useful_size = 50  # 5 см в мм
        
        # Зазор справа
        right_gap = self.sheet_width - bounds[2]
        if 0 < right_gap < min_useful_size:
            penalty += 5
            
        # Зазор сверху
        top_gap = self.sheet_height - bounds[3]
        if 0 < top_gap < min_useful_size:
            penalty += 5
        
        return penalty
    
    def _calculate_space_utilization_bonus(self, polygon: Polygon) -> float:
        """Бонус за максимальное использование пространства листа."""
        bounds = polygon.bounds
        
        # Бонус за размещение близко к краям листа
        bonus = 0.0
        
        # Бонус за близость к правому краю
        right_distance = self.sheet_width - bounds[2]
        if right_distance < 100:  # В пределах 10 см от края
            bonus += 20 * (1 - right_distance / 100)
            
        # Бонус за близость к верхнему краю  
        top_distance = self.sheet_height - bounds[3]
        if top_distance < 100:  # В пределах 10 см от края
            bonus += 20 * (1 - top_distance / 100)
            
        # Бонус за заполнение промежутков между размещенными полигонами
        if len(self.placed_polygons) >= 2:
            gap_fill_bonus = self._calculate_gap_fill_bonus(polygon)
            bonus += gap_fill_bonus
            
        return bonus
    
    def _calculate_gap_fill_bonus(self, polygon: Polygon) -> float:
        """Бонус за заполнение промежутков между полигонами."""
        bounds = polygon.bounds
        bonus = 0.0
        
        # Ищем полигоны слева и справа
        left_polygons = []
        right_polygons = []
        
        for placed_polygon in self.placed_polygons:
            placed_bounds = placed_polygon.bounds
            # Полигон слева если его правый край левее нашего левого края
            if placed_bounds[2] < bounds[0]:
                left_polygons.append(placed_polygon)
            # Полигон справа если его левый край правее нашего правого края  
            elif placed_bounds[0] > bounds[2]:
                right_polygons.append(placed_polygon)
                
        # Если есть полигоны и слева и справа - это хорошее заполнение промежутка
        if left_polygons and right_polygons:
            bonus += 50
            
        return bonus
    
    def _calculate_corner_usage_bonus(self, polygon: Polygon) -> float:
        """Бонус за эффективное использование углов листа."""
        bonus = 0.0
        bounds = polygon.bounds
        
        # Углы листа
        corners = [
            (0, 0),  # Нижний левый
            (self.sheet_width, 0),  # Нижний правый
            (0, self.sheet_height),  # Верхний левый
            (self.sheet_width, self.sheet_height)  # Верхний правый
        ]
        
        for corner_x, corner_y in corners:
            # Проверяем, перекрывает ли полигон угол
            corner_point = Point(corner_x, corner_y)
            if polygon.contains(corner_point) or polygon.touches(corner_point):
                bonus += 25  # Бонус за использование угла
            else:
                # Бонус за близость к углу
                distance_to_corner = np.sqrt((bounds[0] - corner_x)**2 + (bounds[1] - corner_y)**2)
                if distance_to_corner < 50:  # В пределах 5 см
                    bonus += 10 * (1 - distance_to_corner / 50)
        
        return bonus
    
    def _rotate_carpet(self, polygon: Polygon, angle: float) -> Polygon:
        """Поворачивает коврик на заданный угол."""
        if angle == 0:
            return polygon
        return affinity.rotate(polygon, angle, origin='centroid')
    
    def _translate_polygon(self, polygon: Polygon, dx: float, dy: float) -> Polygon:
        """Перемещает полигон на заданное смещение."""
        return affinity.translate(polygon, dx, dy)
    
    def _fits_on_sheet(self, polygon: Polygon) -> bool:
        """Проверяет, помещается ли полигон на лист."""
        bounds = polygon.bounds
        width = bounds[2] - bounds[0]
        height = bounds[3] - bounds[1]
        return width <= self.sheet_width and height <= self.sheet_height
    
    def _has_collisions(self, test_polygon: Polygon) -> bool:
        """Проверяет пересечения с уже размещенными полигонами."""
        for i, placed_polygon in enumerate(self.placed_polygons):
            # Проверяем реальное пересечение площадей (не касание)
            if test_polygon.intersects(placed_polygon):
                intersection = test_polygon.intersection(placed_polygon)
                # Только значительные пересечения считаем коллизией
                if hasattr(intersection, 'area') and intersection.area > 5.0:  # > 5 мм²
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
        logger.info(f"Улучшенный алгоритм: размещено {len(placed)}, использование {usage_percent:.1f}%")
    
    return placed, unplaced