#!/usr/bin/env python3

from pathlib import Path
from dxf_utils import parse_dxf_complete
from layout_optimizer import Carpet, rotate_polygon
from shapely.geometry import Polygon
import numpy as np

def analyze_tetris_quality(carpet_polygon, angle=0):
    """Анализируем тетрисовость ковра в данной ориентации."""
    rotated = rotate_polygon(carpet_polygon, angle) if angle != 0 else carpet_polygon
    bounds = rotated.bounds

    # Bounding box площадь
    bbox_area = (bounds[2] - bounds[0]) * (bounds[3] - bounds[1])
    actual_area = rotated.area

    # Коэффициент заполнения bounding box
    fill_ratio = actual_area / bbox_area if bbox_area > 0 else 0

    # Анализ доступности нижнего пространства
    # Создаем тестовые точки под ковром для проверки доступности
    test_points = []
    for x in np.linspace(bounds[0], bounds[2], 10):
        for y in np.linspace(bounds[1] - 50, bounds[1], 5):  # 50мм под ковром
            test_points.append((x, y))

    accessible_points = sum(1 for p in test_points if not rotated.contains(Polygon([p, (p[0]+1, p[1]), (p[0]+1, p[1]+1), (p[0], p[1]+1)])))

    accessibility_ratio = accessible_points / len(test_points) if test_points else 0

    # Анализ верхнего пространства (пустота сверху в bbox)
    top_space_height = 200 - (bounds[3] - bounds[1])  # Высота листа минус высота ковра

    return {
        'angle': angle,
        'fill_ratio': fill_ratio,
        'accessibility_ratio': accessibility_ratio,
        'top_space_height': top_space_height,
        'tetris_score': fill_ratio * 0.3 + accessibility_ratio * 0.4 + (top_space_height / 200) * 0.3,
        'bounds': bounds
    }

def debug_carpet_8_orientations():
    """Анализируем все ориентации ковра 8.dxf для максимальной тетрисовости."""

    dxf_file = Path('dxf_samples/SKODA KODIAQ/8.dxf')
    if not dxf_file.exists():
        print(f"❌ File not found: {dxf_file}")
        return

    try:
        polygon_data = parse_dxf_complete(dxf_file.as_posix(), verbose=False)
        if not polygon_data or not polygon_data.get("combined_polygon"):
            print("❌ Failed to parse DXF file")
            return

        base_polygon = polygon_data["combined_polygon"]
        print(f"📊 Analyzing carpet 8.dxf")
        print(f"Area: {base_polygon.area/10000:.1f} cm²")
        print(f"Original bounds: {base_polygon.bounds}")
        print()

        # Анализируем все 4 ориентации
        orientations = []
        for angle in [0, 90, 180, 270]:
            analysis = analyze_tetris_quality(base_polygon, angle)
            orientations.append(analysis)

            print(f"🔄 Angle {angle}°:")
            print(f"  Fill ratio: {analysis['fill_ratio']:.3f} (bbox utilization)")
            print(f"  Accessibility: {analysis['accessibility_ratio']:.3f} (space below accessible)")
            print(f"  Top space: {analysis['top_space_height']:.0f}mm (free space above)")
            print(f"  TETRIS SCORE: {analysis['tetris_score']:.3f}")
            print(f"  Bounds: ({analysis['bounds'][0]:.0f}, {analysis['bounds'][1]:.0f}) to ({analysis['bounds'][2]:.0f}, {analysis['bounds'][3]:.0f})")
            print()

        # Найдем лучшую ориентацию
        best = max(orientations, key=lambda x: x['tetris_score'])
        worst = min(orientations, key=lambda x: x['tetris_score'])

        print("🏆 BEST TETRIS ORIENTATION:")
        print(f"  Angle: {best['angle']}° (score: {best['tetris_score']:.3f})")
        print(f"  Improvement over worst: {((best['tetris_score'] - worst['tetris_score']) / worst['tetris_score'] * 100):.1f}%")
        print()

        # Практические рекомендации
        print("💡 РЕКОМЕНДАЦИИ:")
        if best['angle'] != 0:
            print(f"  ✅ Поворот на {best['angle']}° улучшит тетрисовость")
        else:
            print("  ℹ️  Текущая ориентация уже оптимальна")

        if best['accessibility_ratio'] > 0.7:
            print("  ✅ Хорошая доступность пространства снизу")
        else:
            print("  ⚠️  Ковер запирает пространство снизу")

        if best['top_space_height'] > 100:
            print("  ✅ Достаточно свободного места сверху")
        else:
            print("  ⚠️  Мало свободного места сверху")

        return orientations

    except Exception as e:
        print(f"❌ Error analyzing carpet: {e}")
        return []

if __name__ == "__main__":
    debug_carpet_8_orientations()