#!/usr/bin/env python3
"""
Тест нового оптимизированного алгоритма размещения ковров.
Этот тест проверяет улучшенный алгоритм на данных из tmp_test.
"""

import sys
import os
from pathlib import Path

# Добавляем путь к модулям проекта
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from layout_optimizer import bin_packing_with_inventory
from carpet import Carpet
from dxf_utils import parse_dxf
from plot import plot_layout
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def test_optimized_algorithm():
    """Тестирует новый оптимизированный алгоритм на данных из tmp_test."""

    # Путь к DXF файлам
    dxf_path = Path(__file__).parent / "tmp_test"
    dxf_files = list(dxf_path.glob("*.dxf"))

    if not dxf_files:
        logger.error("Не найдены DXF файлы в tmp_test")
        return

    logger.info(f"Найдено {len(dxf_files)} DXF файлов")

    # Загружаем ковры
    carpets = []
    for dxf_file in dxf_files[:10]:  # Берем первые 10 для теста
        try:
            polygon = parse_dxf(str(dxf_file), verbose=False)
            if polygon:
                # Создаем ковер с приоритетом 1 (чтобы попал в основной алгоритм)
                carpet = Carpet(
                    polygon=polygon,  # Берем полигон
                    filename=dxf_file.name,
                    color="чёрный",  # Все одного цвета для упрощения
                    order_id=f"order_{dxf_file.stem}",
                    priority=1,
                )
                carpets.append(carpet)
                logger.info(
                    f"Загружен ковер {dxf_file.name}, площадь: {carpet.polygon.area:.0f}"
                )
        except Exception as e:
            logger.warning(f"Не удалось загрузить {dxf_file}: {e}")

    if not carpets:
        logger.error("Не удалось загрузить ни одного ковра")
        return

    # Сортируем по площади для демонстрации проблемы
    carpets.sort(key=lambda c: c.polygon.area, reverse=True)
    logger.info("Ковры отсортированы по площади (крупные первые)")

    # Определяем доступные листы
    available_sheets = [
        {
            "name": "Черный лист 140x200",
            "width": 140,
            "height": 200,
            "color": "чёрный",
            "count": 10,
            "used": 0,
        }
    ]

    logger.info("=== ЗАПУСК ОПТИМИЗИРОВАННОГО АЛГОРИТМА ===")

    try:
        # Запускаем новый оптимизированный алгоритм
        placed_layouts, unplaced_carpets = bin_packing_with_inventory(
            carpets=carpets, available_sheets=available_sheets, verbose=True
        )

        # Выводим результаты
        logger.info("\n=== РЕЗУЛЬТАТЫ ===")
        logger.info(f"Использовано листов: {len(placed_layouts)}")
        logger.info(f"Неразмещенных ковров: {len(unplaced_carpets)}")

        total_usage = 0
        for i, layout in enumerate(placed_layouts):
            logger.info(
                f"Лист {i+1}: {len(layout.placed_polygons)} ковров, "
                f"заполнение {layout.usage_percent:.1f}%"
            )
            total_usage += layout.usage_percent

        if placed_layouts:
            avg_usage = total_usage / len(placed_layouts)
            logger.info(f"Среднее заполнение листов: {avg_usage:.1f}%")

        # Создаем визуализацию результатов
        output_dir = Path(__file__).parent / "tmp_test" / "optimized_results"
        output_dir.mkdir(exist_ok=True)

        if placed_layouts:
            for i, layout in enumerate(placed_layouts):
                plot_filename = output_dir / f"optimized_sheet_{i+1}.png"
                plot_result = plot_layout(layout.placed_polygons, layout.sheet_size)
                with open(plot_filename, "wb") as f:
                    f.write(plot_result.getvalue())
            logger.info(f"Результаты сохранены в {output_dir}")

            # Сравнение с предыдущими результатами
            logger.info("\n=== СРАВНЕНИЕ ===")
            logger.info("Оригинальный алгоритм: 6 листов (по изображениям)")
            logger.info(f"Новый алгоритм: {len(placed_layouts)} листов")

            if len(placed_layouts) < 6:
                logger.info("🎉 УЛУЧШЕНИЕ! Используется меньше листов!")
            elif len(placed_layouts) == 6:
                logger.info(
                    "Количество листов не изменилось, но плотность могла улучшиться"
                )
            else:
                logger.warning("Возможна проблема - используется больше листов")

    except Exception as e:
        logger.error(f"Ошибка при выполнении алгоритма: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_optimized_algorithm()
