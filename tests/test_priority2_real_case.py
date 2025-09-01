"""
Тест приоритета 2 для ручно загружаемых файлов.
Проверяет, что файлы приоритета 2 размещаются только в пустоты на существующих листах
и не создают новые листы.
"""

import pytest
import pandas as pd
import os
import sys
import tempfile
import shutil
from io import BytesIO
from unittest.mock import Mock, patch, MagicMock
from shapely.geometry import Polygon

# Добавляем корневую директорию в путь для импорта модулей
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from layout_optimizer import (
    parse_dxf_complete,
    bin_packing_with_inventory,
    scale_polygons_to_fit,
    save_dxf_layout_complete,
)


class TestPriority2RealCase:
    """Тестирование приоритета 2 для ручно загружаемых файлов на реальном случае."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Настройка тестовой среды."""
        # Создаем временную папку для выходных файлов
        self.output_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()

        # Убеждаемся что sample_input.xlsx существует
        self.sample_excel_path = os.path.join(self.original_cwd, "sample_input.xlsx")
        assert os.path.exists(
            self.sample_excel_path
        ), "Файл sample_input.xlsx не найден"

        # Проверяем наличие тестового DXF файла
        self.test_dxf_path = os.path.join(
            self.original_cwd, "dxf_samples/ДЕКА KUGOO M4 PRO JILONG/1.dxf"
        )
        if not os.path.exists(self.test_dxf_path):
            pytest.skip(f"Тестовый DXF файл не найден: {self.test_dxf_path}")

        yield

        # Очистка после теста
        shutil.rmtree(self.output_dir, ignore_errors=True)

    def test_priority2_with_real_dxf_file(self):
        """
        Тест приоритета 2 с реальными данными из test_full_streamlit_workflow_emulation
        и дополнительным файлом "dxf_samples/ДЕКА KUGOO M4 PRO JILONG/1.dxf"
        с цветом черный, приоритетом 2 и количеством 20.
        """
        # 1. НАСТРОЙКА ЛИСТОВ (как в оригинальном тесте)
        available_sheets = []

        # Добавляем 20 черных листов 140x200
        black_sheet = {
            "name": "Лист 140x200 чёрный",
            "width": 140,
            "height": 200,
            "color": "чёрный",
            "count": 20,
            "used": 0,
        }
        available_sheets.append(black_sheet)

        # Добавляем 20 серых листов 140x200
        gray_sheet = {
            "name": "Лист 140x200 серый",
            "width": 140,
            "height": 200,
            "color": "серый",
            "count": 20,
            "used": 0,
        }
        available_sheets.append(gray_sheet)

        # 2. ЗАГРУЗКА И ПАРСИНГ EXCEL (как в оригинальном тесте)
        excel_data = pd.read_excel(
            self.sample_excel_path,
            sheet_name="ZAKAZ",
            header=None,
            date_format=None,
            parse_dates=False,
            engine="openpyxl",
        )

        # 3. ПАРСИНГ ЗАКАЗОВ (как в оригинальном тесте)
        all_orders = []
        df = excel_data

        if df.shape[0] > 2:
            data_rows = df.iloc[2:].copy()

            if df.shape[1] > 3:
                pending_orders = data_rows[
                    data_rows.iloc[:, 2].isna() | (data_rows.iloc[:, 2] == "")
                ]

                for idx, row in pending_orders.iterrows():
                    if pd.notna(row.iloc[3]):
                        color = (
                            str(row.iloc[8]).lower().strip()
                            if pd.notna(row.iloc[8]) and df.shape[1] > 8
                            else ""
                        )
                        if "черн" in color or "black" in color:
                            color = "чёрный"
                        elif "сер" in color or "gray" in color or "grey" in color:
                            color = "серый"
                        else:
                            color = "серый"

                        unique_order_id = f"ZAKAZ_row_{idx}"

                        order = {
                            "sheet": "ZAKAZ",
                            "row_index": idx,
                            "date": str(row.iloc[0]) if pd.notna(row.iloc[0]) else "",
                            "article": str(row.iloc[3]),
                            "product": str(row.iloc[4])
                            if pd.notna(row.iloc[4])
                            else "",
                            "client": str(row.iloc[5])
                            if pd.notna(row.iloc[5])
                            else ""
                            if df.shape[1] > 5
                            else "",
                            "order_id": unique_order_id,
                            "color": color,
                            "product_type": str(row.iloc[7])
                            if pd.notna(row.iloc[7]) and df.shape[1] > 7
                            else "",
                            "border_color": row.iloc[10] if df.shape[1] > 10 else None,
                        }
                        all_orders.append(order)

        # Проверяем что найдено 37 заказов
        assert len(all_orders) == 37, f"Ожидалось 37 заказов, найдено {len(all_orders)}"

        # 4. СОЗДАНИЕ DXF ФАЙЛОВ ИЗ ЗАКАЗОВ (упрощенная версия для тестирования)
        dxf_files = []

        for i, order in enumerate(all_orders):
            # Создаем простые тестовые полигоны
            width = 50 + (i % 10) * 10  # От 50 до 140 мм
            height = 50 + (i % 15) * 10  # От 50 до 190 мм

            polygon = Polygon([(0, 0), (width, 0), (width, height), (0, height)])

            dxf_files.append(
                (
                    polygon,
                    f"{order['product']}_test_{i}.dxf",
                    order.get("color", "серый"),
                    order.get("order_id", "unknown"),
                    1,  # Priority 1 for Excel files
                )
            )

        # 5. ДОБАВЛЯЕМ PRIORITY 2 ФАЙЛЫ
        # Загружаем реальный DXF файл
        with open(self.test_dxf_path, "rb") as f:
            dxf_content = f.read()

        # Парсим реальный DXF файл
        dxf_bytesio = BytesIO(dxf_content)
        parsed_data = parse_dxf_complete(dxf_bytesio, verbose=False)

        assert parsed_data is not None, "Не удалось парсить тестовый DXF файл"
        assert (
            parsed_data["combined_polygon"] is not None
        ), "В DXF файле нет валидного полигона"

        # Создаем 20 копий файла с приоритетом 2 и черным цветом
        priority2_count = 20
        for i in range(priority2_count):
            priority2_file = (
                parsed_data["combined_polygon"],
                f"ДЕКА_KUGOO_M4_PRO_JILONG_1_копия_{i+1}.dxf",
                "чёрный",  # черный цвет как указано в условии
                f"group_priority2_{i+1}",
                2,  # Priority 2
            )
            dxf_files.append(priority2_file)

        print(
            f"Создано {len(dxf_files)} полигонов: {len(all_orders)} из Excel + {priority2_count} приоритета 2"
        )

        # 6. МАСШТАБИРОВАНИЕ
        reference_sheet_size = (140, 200)
        scaled_polygons = scale_polygons_to_fit(
            dxf_files, reference_sheet_size, verbose=False
        )

        # 7. ПОДСЧЕТ ЛИСТОВ ДО ОПТИМИЗАЦИИ
        initial_sheets_count = sum(
            sheet["count"] - sheet["used"] for sheet in available_sheets
        )

        # 8. ОПТИМИЗАЦИЯ С ПРИОРИТЕТАМИ
        MAX_SHEETS_PER_ORDER = 5

        placed_layouts, unplaced_polygons = bin_packing_with_inventory(
            scaled_polygons,
            available_sheets,
            verbose=True,
            max_sheets_per_order=MAX_SHEETS_PER_ORDER,
        )

        # 9. ПРОВЕРКИ РЕЗУЛЬТАТОВ

        # 9.1 Проверяем что оптимизация прошла успешно
        assert len(placed_layouts) > 0, "Не было создано ни одного листа с раскладкой"

        # 9.2 Проверяем использование листов - не должно превышать количество без priority 2 файлов
        sheets_used = len(placed_layouts)

        # Запускаем тест без priority 2 файлов для сравнения
        excel_only_polygons = [p for p in scaled_polygons if len(p) < 5 or p[4] != 2]
        excel_only_layouts, _ = bin_packing_with_inventory(
            excel_only_polygons,
            [sheet.copy() for sheet in available_sheets],  # Fresh copy
            verbose=False,
            max_sheets_per_order=MAX_SHEETS_PER_ORDER,
        )
        excel_only_sheets = len(excel_only_layouts)

        print(f"Листов с priority 2: {sheets_used}")
        print(f"Листов без priority 2: {excel_only_sheets}")

        # 9.3 КЛЮЧЕВАЯ ПРОВЕРКА: Priority 2 файлы не должны создавать новые листы
        assert (
            sheets_used == excel_only_sheets
        ), f"Priority 2 файлы создали новые листы: {sheets_used} vs {excel_only_sheets}"

        # 9.4 Подсчитываем размещенные priority 2 файлы
        priority2_placed_count = 0
        priority2_unplaced_count = 0

        # В размещенных
        for layout in placed_layouts:
            for placed_tuple in layout["placed_polygons"]:
                if len(placed_tuple) >= 5:
                    filename = placed_tuple[4]
                    if "priority2" in filename or "ДЕКА_KUGOO" in filename:
                        priority2_placed_count += 1

        # В неразмещенных
        for unplaced_tuple in unplaced_polygons:
            if len(unplaced_tuple) >= 2:
                filename = unplaced_tuple[1]
                if "priority2" in filename or "ДЕКА_KUGOO" in filename:
                    priority2_unplaced_count += 1

        print(
            f"Priority 2 файлы: размещено {priority2_placed_count}, не размещено {priority2_unplaced_count}"
        )

        # 9.5 Проверяем что priority 2 файлы могли быть размещены только частично
        total_priority2 = priority2_placed_count + priority2_unplaced_count
        assert (
            total_priority2 == priority2_count
        ), f"Потеряны priority 2 файлы: {total_priority2} != {priority2_count}"

        # 9.6 Проверяем что Excel файлы были размещены (должны иметь приоритет)
        excel_placed_count = (
            sum(len(layout["placed_polygons"]) for layout in placed_layouts)
            - priority2_placed_count
        )
        excel_placement_rate = excel_placed_count / len(all_orders)
        assert (
            excel_placement_rate >= 0.8
        ), f"Excel файлы размещены плохо: {excel_placement_rate*100:.1f}%"

        # 10. РЕЗУЛЬТАТЫ ТЕСТА
        print(f"\n=== РЕЗУЛЬТАТЫ ТЕСТА ПРИОРИТЕТА 2 ===")
        print(f"Всего листов доступно: {initial_sheets_count}")
        print(f"Excel заказов: {len(all_orders)}")
        print(f"Priority 2 файлов: {priority2_count}")
        print(f"Листов использовано: {sheets_used}")
        print(f"Листов использовано без priority 2: {excel_only_sheets}")
        print(f"Priority 2 файлов размещено: {priority2_placed_count}")
        print(f"Priority 2 файлов не размещено: {priority2_unplaced_count}")
        print(
            f"Excel файлов размещено: {excel_placed_count}/{len(all_orders)} ({excel_placement_rate*100:.1f}%)"
        )

        # ФИНАЛЬНЫЕ ПРОВЕРКИ
        assert sheets_used == excel_only_sheets  # Priority 2 не создает новые листы
        assert excel_placement_rate >= 0.8  # Excel файлы размещены хорошо
        assert total_priority2 == priority2_count  # Все priority 2 файлы учтены

        # Если есть размещенные priority 2 файлы, проверяем что они только на существующих листах
        if priority2_placed_count > 0:
            print(
                f"✅ {priority2_placed_count} файлов приоритета 2 успешно размещены в пустоты существующих листов"
            )

        if priority2_unplaced_count > 0:
            print(
                f"⚠️ {priority2_unplaced_count} файлов приоритета 2 не размещены (новые листы не создаются)"
            )

        print("✅ Тест приоритета 2 с реальным DXF файлом прошел успешно!")

        # Дополнительная проверка: убеждаемся что неразмещенные priority 2 действительно не поместились
        # а не из-за ошибки в алгоритме
        total_sheet_area = sum(
            layout["sheet_size"][0] * layout["sheet_size"][1]
            for layout in placed_layouts
        )
        total_placed_area = 0
        for layout in placed_layouts:
            for placed_tuple in layout["placed_polygons"]:
                if len(placed_tuple) >= 1:
                    polygon = placed_tuple[0]
                    total_placed_area += polygon.area / 100  # Convert mm² to cm²

        usage_rate = total_placed_area / total_sheet_area if total_sheet_area > 0 else 0
        print(f"Общий коэффициент использования материала: {usage_rate*100:.1f}%")

        # Если коэффициент использования низкий, но файлы не размещены, возможно есть проблема
        if usage_rate < 0.7 and priority2_unplaced_count > 0:
            print(
                f"⚠️ Предупреждение: низкий коэффициент использования ({usage_rate*100:.1f}%) при неразмещенных priority 2 файлах"
            )
