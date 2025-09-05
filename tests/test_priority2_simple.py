"""
Простой тест приоритета 2 для проверки основной логики.
Проверяет базовые сценарии без зависимости от внешних файлов.
"""

import pytest
import sys
import os
from shapely.geometry import Polygon

# Добавляем корневую директорию в путь для импорта модулей
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from layout_optimizer import (
    bin_packing_with_inventory,
)


class TestPriority2Simple:
    """Простые тесты приоритета 2."""

    def test_priority2_no_new_sheets(self):
        """
        Тест: файлы приоритета 2 не создают новые листы.
        """
        # Настройка листов
        available_sheets = [
            {
                "name": "Лист 100x100 чёрный",
                "width": 100,
                "height": 100,
                "color": "чёрный",
                "count": 2,
                "used": 0,
            }
        ]

        # Создаем полигоны
        polygons = []

        # Priority 1 полигоны (должны создать листы)
        for i in range(2):
            polygon = Polygon(
                [(0, 0), (300, 0), (300, 300), (0, 300)]
            )  # 30x30 мм (3x3 см)
            polygons.append(
                (
                    polygon,
                    f"priority1_file_{i}.dxf",
                    "чёрный",
                    f"excel_order_{i}",
                    1,  # Priority 1
                )
            )

        # Priority 2 полигоны (не должны создать новые листы)
        for i in range(3):
            polygon = Polygon(
                [(0, 0), (200, 0), (200, 200), (0, 200)]
            )  # 20x20 мм (2x2 см)
            polygons.append(
                (
                    polygon,
                    f"priority2_file_{i}.dxf",
                    "чёрный",
                    f"group_priority2_{i}",
                    2,  # Priority 2
                )
            )

        # Полигоны остаются в исходном масштабе
        reference_sheet_size = (100, 100)

        # Тест только с priority 1
        priority1_polygons = [p for p in polygons if len(p) < 5 or p[4] != 2]
        priority1_layouts, _ = bin_packing_with_inventory(
            priority1_polygons,
            [sheet.copy() for sheet in available_sheets],
            verbose=False,
        )

        # Тест с priority 1 + priority 2
        all_layouts, unplaced = bin_packing_with_inventory(
            polygons, [sheet.copy() for sheet in available_sheets], verbose=False
        )

        # Проверки
        priority1_sheets = len(priority1_layouts)
        all_sheets = len(all_layouts)

        print(f"Листов с только priority 1: {priority1_sheets}")
        print(f"Листов с priority 1 + priority 2: {all_sheets}")

        # КЛЮЧЕВАЯ ПРОВЕРКА: количество листов не должно измениться
        assert (
            all_sheets == priority1_sheets
        ), f"Priority 2 создал новые листы: {all_sheets} != {priority1_sheets}"

        # Проверяем что priority 2 файлы могли быть частично размещены
        priority2_placed = 0
        priority2_unplaced = 0

        for layout in all_layouts:
            for placed_tuple in layout["placed_polygons"]:
                if len(placed_tuple) >= 5:
                    filename = placed_tuple[4]
                    if "priority2" in filename:
                        priority2_placed += 1

        for unplaced_tuple in unplaced:
            if len(unplaced_tuple) >= 2:
                filename = unplaced_tuple[1]
                if "priority2" in filename:
                    priority2_unplaced += 1

        total_priority2 = priority2_placed + priority2_unplaced
        assert (
            total_priority2 == 3
        ), f"Потеряны priority 2 файлы: {total_priority2} != 3"

        print(f"Priority 2 файлов размещено: {priority2_placed}")
        print(f"Priority 2 файлов не размещено: {priority2_unplaced}")
        print("✅ Тест приоритета 2 (простой) прошел успешно!")

    def test_priority2_color_matching(self):
        """
        Тест: файлы приоритета 2 размещаются только на листах совпадающего цвета.
        """
        # Настройка листов разных цветов
        available_sheets = [
            {
                "name": "Лист 100x100 чёрный",
                "width": 100,
                "height": 100,
                "color": "чёрный",
                "count": 1,
                "used": 0,
            },
            {
                "name": "Лист 100x100 серый",
                "width": 100,
                "height": 100,
                "color": "серый",
                "count": 1,
                "used": 0,
            },
        ]

        # Создаем полигоны
        polygons = []

        # Priority 1 черный полигон (создаст черный лист)
        polygon = Polygon([(0, 0), (300, 0), (300, 300), (0, 300)])  # 30x30 мм
        polygons.append(
            (
                polygon,
                "priority1_black.dxf",
                "чёрный",
                "excel_order_black",
                1,  # Priority 1
            )
        )

        # Priority 1 серый полигон (создаст серый лист)
        polygon = Polygon([(0, 0), (300, 0), (300, 300), (0, 300)])  # 30x30 мм
        polygons.append(
            (
                polygon,
                "priority1_gray.dxf",
                "серый",
                "excel_order_gray",
                1,  # Priority 1
            )
        )

        # Priority 2 черные полигоны (должны размещаться только на черном листе)
        for i in range(2):
            polygon = Polygon([(0, 0), (200, 0), (200, 200), (0, 200)])  # 20x20 мм
            polygons.append(
                (
                    polygon,
                    f"priority2_black_{i}.dxf",
                    "чёрный",
                    f"group_priority2_black_{i}",
                    2,  # Priority 2
                )
            )

        # Priority 2 серые полигоны (должны размещаться только на сером листе)
        for i in range(2):
            polygon = Polygon([(0, 0), (200, 0), (200, 200), (0, 200)])  # 20x20 мм
            polygons.append(
                (
                    polygon,
                    f"priority2_gray_{i}.dxf",
                    "серый",
                    f"group_priority2_gray_{i}",
                    2,  # Priority 2
                )
            )

        # Оптимизация без масштабирования
        reference_sheet_size = (100, 100)

        layouts, unplaced = bin_packing_with_inventory(
            polygons, available_sheets, verbose=False
        )

        # Проверки
        assert len(layouts) == 2, f"Должно быть 2 листа, создано {len(layouts)}"

        # Проверяем цветовое соответствие
        black_sheet_polygons = []
        gray_sheet_polygons = []

        for layout in layouts:
            sheet_color = None
            
            # Определяем тип листа с проверкой наличия ключа
            layout_sheet_type = layout.get("sheet_type")
            if not layout_sheet_type and "sheet_color" in layout:
                # Если нет sheet_type, попробуем найти лист по цвету и размеру
                layout_color = layout["sheet_color"]
                sheet_size = layout.get("sheet_size", (0, 0))
                for sheet in available_sheets:
                    if (sheet.get("color", "") == layout_color and 
                        sheet.get("width", 0) == sheet_size[0] and 
                        sheet.get("height", 0) == sheet_size[1]):
                        layout_sheet_type = sheet["name"]
                        break
            
            if layout_sheet_type:
                for sheet in available_sheets:
                    if sheet["name"] == layout_sheet_type:
                        sheet_color = sheet["color"]
                        break

            for placed_tuple in layout["placed_polygons"]:
                if len(placed_tuple) >= 5:
                    filename = placed_tuple[4]
                    if sheet_color == "чёрный":
                        black_sheet_polygons.append(filename)
                    elif sheet_color == "серый":
                        gray_sheet_polygons.append(filename)

        # Проверяем что черные priority 2 только на черном листе
        black_priority2_on_black = sum(
            1 for f in black_sheet_polygons if "priority2_black" in f
        )
        black_priority2_on_gray = sum(
            1 for f in gray_sheet_polygons if "priority2_black" in f
        )

        # Проверяем что серые priority 2 только на сером листе
        gray_priority2_on_gray = sum(
            1 for f in gray_sheet_polygons if "priority2_gray" in f
        )
        gray_priority2_on_black = sum(
            1 for f in black_sheet_polygons if "priority2_gray" in f
        )

        print(f"Черные priority 2 на черном листе: {black_priority2_on_black}")
        print(f"Черные priority 2 на сером листе: {black_priority2_on_gray}")
        print(f"Серые priority 2 на сером листе: {gray_priority2_on_gray}")
        print(f"Серые priority 2 на черном листе: {gray_priority2_on_black}")

        # Не должно быть неправильных цветовых размещений
        assert black_priority2_on_gray == 0, "Черные priority 2 файлы на сером листе!"
        assert gray_priority2_on_black == 0, "Серые priority 2 файлы на черном листе!"

        print("✅ Тест цветового соответствия приоритета 2 прошел успешно!")

    def test_priority2_no_existing_sheets(self):
        """
        Тест: если нет существующих листов, priority 2 файлы не размещаются.
        """
        available_sheets = [
            {
                "name": "Лист 100x100 чёрный",
                "width": 100,
                "height": 100,
                "color": "чёрный",
                "count": 1,
                "used": 0,
            }
        ]

        # Только priority 2 полигоны
        polygons = []
        for i in range(3):
            polygon = Polygon([(0, 0), (200, 0), (200, 200), (0, 200)])  # 20x20 мм
            polygons.append(
                (
                    polygon,
                    f"priority2_file_{i}.dxf",
                    "чёрный",
                    f"group_priority2_{i}",
                    2,  # Priority 2
                )
            )

        # Оптимизация без масштабирования
        reference_sheet_size = (100, 100)

        layouts, unplaced = bin_packing_with_inventory(
            polygons, available_sheets, verbose=False
        )

        # Проверки
        assert (
            len(layouts) == 0
        ), f"Не должно быть листов для только priority 2, создано {len(layouts)}"
        assert (
            len(unplaced) == 3
        ), f"Все 3 priority 2 должны быть неразмещены, неразмещено {len(unplaced)}"

        print("✅ Тест отсутствия существующих листов для priority 2 прошел успешно!")
