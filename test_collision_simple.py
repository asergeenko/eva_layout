#!/usr/bin/env python3
"""
Упрощённый тест для отладки пересечения двух ковров
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from carpet import Carpet
from layout_optimizer import bin_packing, check_collision
from dxf_utils import parse_dxf
import logging

# Настраиваем детальное логирование (только важные сообщения от layout_optimizer)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Включаем DEBUG только для layout_optimizer
logging.getLogger("layout_optimizer").setLevel(logging.DEBUG)

# Загружаем два проблемных ковра
logger.info("Загружаем EXEED VX/2.dxf...")
exeed_polygon = parse_dxf("data/EXEED VX/2.dxf", verbose=False)
logger.info(f"EXEED bounds: {exeed_polygon.bounds}")

logger.info("Загружаем HONDA FREED 2+/10.dxf...")
honda_polygon = parse_dxf("data/HONDA FREED 2+/10.dxf", verbose=False)
logger.info(f"HONDA bounds: {honda_polygon.bounds}")

# Создаём ковры
exeed = Carpet(
    polygon=exeed_polygon,
    filename="EXEED VX/2.dxf",
    color="чёрный",
    order_id="1",
    priority=1,
)
honda = Carpet(
    polygon=honda_polygon,
    filename="HONDA FREED 2+/10.dxf",
    color="чёрный",
    order_id="2",
    priority=1,
)

# Размещаем
logger.info("\n" + "=" * 80)
logger.info("ЗАПУСК BIN_PACKING")
logger.info("=" * 80)

placed, unplaced = bin_packing([honda, exeed], sheet_size=(140, 200))

logger.info("\n" + "=" * 80)
logger.info("РЕЗУЛЬТАТ РАЗМЕЩЕНИЯ")
logger.info("=" * 80)

for i, carpet in enumerate(placed):
    bounds = carpet.polygon.bounds
    logger.info(f"Ковёр {i}: {carpet.filename}")
    logger.info(f"  Bounds: {bounds}")
    logger.info(
        f"  X: {bounds[0]:.1f} to {bounds[2]:.1f} (width={bounds[2]-bounds[0]:.1f})"
    )
    logger.info(
        f"  Y: {bounds[1]:.1f} to {bounds[3]:.1f} (height={bounds[3]-bounds[1]:.1f})"
    )

# Проверяем зазор
if len(placed) >= 2:
    logger.info("\n" + "=" * 80)
    logger.info("АНАЛИЗ ЗАЗОРА")
    logger.info("=" * 80)

    bounds0 = placed[0].polygon.bounds
    bounds1 = placed[1].polygon.bounds

    # Вертикальный зазор
    if bounds1[1] > bounds0[3]:  # Второй выше первого
        v_gap = bounds1[1] - bounds0[3]
        logger.info(f"Вертикальный зазор: {v_gap:.1f}мм (ковёр 1 выше ковра 0)")
    elif bounds0[1] > bounds1[3]:  # Первый выше второго
        v_gap = bounds0[1] - bounds1[3]
        logger.info(f"Вертикальный зазор: {v_gap:.1f}мм (ковёр 0 выше ковра 1)")
    else:
        overlap = min(bounds0[3], bounds1[3]) - max(bounds0[1], bounds1[1])
        logger.error(f"❌ ВЕРТИКАЛЬНОЕ ПЕРЕСЕЧЕНИЕ: {overlap:.1f}мм")

    # Горизонтальный зазор
    if bounds1[0] > bounds0[2]:  # Второй правее первого
        h_gap = bounds1[0] - bounds0[2]
        logger.info(f"Горизонтальный зазор: {h_gap:.1f}мм (ковёр 1 правее ковра 0)")
    elif bounds0[0] > bounds1[2]:  # Первый правее второго
        h_gap = bounds0[0] - bounds1[2]
        logger.info(f"Горизонтальный зазор: {h_gap:.1f}мм (ковёр 0 правее ковра 1)")
    else:
        overlap = min(bounds0[2], bounds1[2]) - max(bounds0[0], bounds1[0])
        logger.error(f"❌ ГОРИЗОНТАЛЬНОЕ ПЕРЕСЕЧЕНИЕ: {overlap:.1f}мм")

    # Проверка check_collision
    logger.info("\nПроверка check_collision с min_gap=10.0:")
    has_collision = check_collision(placed[0].polygon, placed[1].polygon, min_gap=10.0)
    logger.info(f"check_collision результат: {has_collision}")

    if has_collision:
        logger.error("❌ check_collision ОБНАРУЖИЛ коллизию (правильно!)")
    else:
        logger.error("❌ check_collision НЕ ОБНАРУЖИЛ коллизию (БАГ!)")
