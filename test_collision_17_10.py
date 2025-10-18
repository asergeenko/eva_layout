#!/usr/bin/env python3
"""
Тест для воспроизведения пересечения между EXEED VX/2.dxf и HONDA FREED 2+/10.dxf
из файла "17.10 день.xlsx"
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from excel_loader import parse_orders_from_excel
from layout_optimizer import bin_packing, check_collision
import logging
import pandas as pd

# Настраиваем логирование
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    # Загружаем заказы из Excel
    excel_file = "17.10 день.xlsx"

    logger.info(f"Загружаем заказы из {excel_file}...")

    # Читаем Excel файл
    df = pd.read_excel(excel_file, sheet_name="ZAKAZ", engine="openpyxl")
    logger.info(f"Загружен DataFrame: {df.shape[0]} строк, {df.shape[1]} столбцов")

    orders = parse_orders_from_excel(df)

    if not orders:
        logger.error("Не удалось загрузить заказы!")
        return

    logger.info(
        f"Загружено {len(orders)} заказов (но загрузим только проблемные ковры)"
    )

    # Загружаем только проблемные ковры
    from carpet import Carpet
    from dxf_utils import parse_dxf

    test_carpets = [
        ("data/EXEED VX/2.dxf", "EXEED VX/2.dxf", "чёрный"),
        ("data/HONDA FREED 2+/10.dxf", "HONDA FREED 2+/10.dxf", "чёрный"),
    ]

    all_carpets = []
    for dxf_path, filename, color in test_carpets:
        try:
            logger.info(f"Загружаем: {dxf_path}")
            polygon = parse_dxf(dxf_path, verbose=False)
            if polygon:
                carpet = Carpet(
                    polygon=polygon,
                    filename=filename,
                    color=color,
                    order_id="test",
                    priority=1,
                )
                all_carpets.append(carpet)
                logger.info(f"✓ Загружен: {filename}, bounds: {polygon.bounds}")
            else:
                logger.error(f"Не удалось разобрать DXF: {dxf_path}")
        except Exception as e:
            logger.error(f"Ошибка загрузки {dxf_path}: {e}")

    logger.info(f"Всего загружено ковров: {len(all_carpets)}")

    # Настройки листа
    sheet_size = (140, 200)  # 140x200 см
    sheet_width_mm = sheet_size[0] * 10
    sheet_height_mm = sheet_size[1] * 10

    logger.info(
        f"Размер листа: {sheet_size[0]}x{sheet_size[1]} см ({sheet_width_mm}x{sheet_height_mm} мм)"
    )

    # Запускаем bin_packing только для первого листа
    logger.info("Запускаем bin_packing для первого листа...")
    placed, unplaced = bin_packing(all_carpets, sheet_size=sheet_size)

    logger.info(f"Размещено ковров: {len(placed)}")
    logger.info(f"Не размещено ковров: {len(unplaced)}")

    # Проверяем на пересечения
    logger.info("\n🔍 ПРОВЕРКА НА ПЕРЕСЕЧЕНИЯ:")
    collision_found = False

    for i in range(len(placed)):
        for j in range(i + 1, len(placed)):
            if check_collision(
                placed[i].polygon,
                placed[j].polygon,
                min_gap=10.0,
            ):
                collision_found = True
                logger.error("\n❌ ОБНАРУЖЕНО ПЕРЕСЕЧЕНИЕ!")
                logger.error(f"   Ковёр {i}: {placed[i].filename}")
                logger.error(f"   Ковёр {j}: {placed[j].filename}")
                logger.error(
                    f"   X offset {i}: {placed[i].x_offset:.1f}, Y offset: {placed[i].y_offset:.1f}"
                )
                logger.error(
                    f"   X offset {j}: {placed[j].x_offset:.1f}, Y offset: {placed[j].y_offset:.1f}"
                )
                logger.error(f"   Bounds {i}: {placed[i].polygon.bounds}")
                logger.error(f"   Bounds {j}: {placed[j].polygon.bounds}")

                # Проверяем конкретно искомые файлы
                if (
                    "EXEED VX/2.dxf" in placed[i].filename
                    and "HONDA FREED 2+/10.dxf" in placed[j].filename
                ) or (
                    "EXEED VX/2.dxf" in placed[j].filename
                    and "HONDA FREED 2+/10.dxf" in placed[i].filename
                ):
                    logger.error("\n⚠️  ЭТО ИМЕННО ТО ПЕРЕСЕЧЕНИЕ ИЗ ЗАДАЧИ!")

    if not collision_found:
        logger.info("✓ Пересечений не обнаружено")
    else:
        logger.error("\n❌ ВСЕГО ОБНАРУЖЕНО ПЕРЕСЕЧЕНИЙ: найдено хотя бы одно")

    return collision_found


if __name__ == "__main__":
    has_collision = main()
    sys.exit(1 if has_collision else 0)
