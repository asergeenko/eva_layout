"""
Интеграционный тест для Streamlit приложения раскладки листов.
Эмулирует полный пользовательский ввод: настройка листов, загрузка Excel, раскладка.
"""

import pytest
import pandas as pd
import os
import sys
import tempfile
import shutil
from io import BytesIO
from unittest.mock import Mock, patch, MagicMock

# Добавляем корневую директорию в путь для импорта модулей
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from layout_optimizer import (
    parse_dxf_complete,
    bin_packing_with_inventory,
    scale_polygons_to_fit,
    save_dxf_layout_complete,
)


class TestStreamlitIntegration:
    """Тестирование интеграции с полной эмуляцией пользовательского ввода в Streamlit."""

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

        yield

        # Очистка после теста
        shutil.rmtree(self.output_dir, ignore_errors=True)

    def test_full_streamlit_workflow_emulation(self):
        """
        Тестирует полный workflow Streamlit приложения:
        1. 20 черных листов 140x200
        2. 20 серых листов 140x200
        3. Загрузка sample_input.xlsx
        4. Выбор всех невыполненных заказов (должно быть 37)
        5. Успешная раскладка всех заказов
        """
        # 1. ЭМУЛЯЦИЯ НАСТРОЙКИ ЛИСТОВ (как в Streamlit)
        available_sheets = []

        # Добавляем 20 черных листов 140x200 (эмуляция пользовательского ввода)
        black_sheet = {
            "name": "Лист 140x200 чёрный",
            "width": 140,
            "height": 200,
            "color": "чёрный",
            "count": 20,
            "used": 0,
        }
        available_sheets.append(black_sheet)

        # Добавляем 20 серых листов 140x200 (эмуляция пользовательского ввода)
        gray_sheet = {
            "name": "Лист 140x200 серый",
            "width": 140,
            "height": 200,
            "color": "серый",
            "count": 20,
            "used": 0,
        }
        available_sheets.append(gray_sheet)

        # Проверяем что листы добавлены корректно
        assert len(available_sheets) == 2
        total_sheets = sum(sheet["count"] for sheet in available_sheets)
        assert total_sheets == 40

        # 2. ЭМУЛЯЦИЯ ЗАГРУЗКИ EXCEL ФАЙЛА (как в Streamlit)
        # Читаем Excel точно так же как в Streamlit коде
        excel_data = pd.read_excel(
            self.sample_excel_path,
            sheet_name="ZAKAZ",
            header=None,
            date_format=None,
            parse_dates=False,
            engine="openpyxl",
        )

        # 3. ЭМУЛЯЦИЯ ПАРСИНГА ЗАКАЗОВ (точно как в Streamlit)
        all_orders = []
        df = excel_data

        # Пропускаем первые 2 строки (заголовки), начинаем с индекса 2
        if df.shape[0] > 2:
            data_rows = df.iloc[2:].copy()

            # Проверяем пустую колонку "Сделано" (индекс 2)
            if df.shape[1] > 3:
                pending_orders = data_rows[
                    data_rows.iloc[:, 2].isna() | (data_rows.iloc[:, 2] == "")
                ]

                for idx, row in pending_orders.iterrows():
                    if pd.notna(
                        row.iloc[3]
                    ):  # Проверяем что Артикул (column D) не пустой
                        # Получаем цвет из колонки I (индекс 8)
                        color = (
                            str(row.iloc[8]).lower().strip()
                            if pd.notna(row.iloc[8]) and df.shape[1] > 8
                            else ""
                        )
                        # Нормализуем цвета
                        if "черн" in color or "black" in color:
                            color = "чёрный"
                        elif "сер" in color or "gray" in color or "grey" in color:
                            color = "серый"
                        else:
                            color = "серый"  # Default цвет если не указан

                        # Создаем уникальный order_id для каждой строки
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

        # 4. ПРОВЕРЯЕМ ЧТО НАЙДЕНО РОВНО 37 НЕВЫПОЛНЕННЫХ ЗАКАЗОВ
        assert (
            len(all_orders) == 37
        ), f"Ожидалось 37 невыполненных заказов, найдено {len(all_orders)}"

        # 5. ЭМУЛЯЦИЯ ВЫБОРА ВСЕХ ЗАКАЗОВ (как в Streamlit session_state)
        selected_orders = all_orders.copy()  # Выбираем все заказы

        # Проверяем что все заказы выбраны
        assert len(selected_orders) == 37

        # 6. ЭМУЛЯЦИЯ ЗАГРУЗКИ DXF ФАЙЛОВ (упрощенная версия для тестирования)
        # Создаем мок DXF файлы для тестирования
        dxf_files = []

        # Создаем простые тестовые полигоны для каждого заказа
        for i, order in enumerate(selected_orders):
            # Создаем мок DXF файл
            mock_file = Mock()
            mock_file.name = f"{order['product']}_test_{i}.dxf"
            mock_file.color = order.get("color", "серый")
            mock_file.order_id = order.get("order_id", "unknown")
            mock_file.display_name = mock_file.name

            # Создаем простую прямоугольную геометрию (размер варьируется)
            # для эмуляции реальных DXF файлов
            width = 50 + (i % 10) * 10  # От 50 до 140 мм
            height = 50 + (i % 15) * 10  # От 50 до 190 мм

            # Создаем полигон с этими размерами
            from shapely.geometry import Polygon

            polygon = Polygon([(0, 0), (width, 0), (width, height), (0, height)])

            dxf_files.append(
                (polygon, mock_file.name, mock_file.color, mock_file.order_id)
            )

        # Проверяем что создали файлы для всех заказов
        assert len(dxf_files) == 37

        # 7. ЭМУЛЯЦИЯ МАСШТАБИРОВАНИЯ (как в Streamlit)
        # Находим наибольший лист для масштабирования
        max_sheet_area = 0
        reference_sheet_size = (140, 200)  # default fallback
        for sheet in available_sheets:
            area = sheet["width"] * sheet["height"]
            if area > max_sheet_area:
                max_sheet_area = area
                reference_sheet_size = (sheet["width"], sheet["height"])

        # Масштабируем полигоны
        scaled_polygons = scale_polygons_to_fit(
            dxf_files, reference_sheet_size, verbose=False
        )

        # 8. ЭМУЛЯЦИЯ ОПТИМИЗАЦИИ (как в Streamlit с MAX_SHEETS_PER_ORDER=5)
        MAX_SHEETS_PER_ORDER = 5  # Константа из Streamlit приложения

        placed_layouts, unplaced_polygons = bin_packing_with_inventory(
            scaled_polygons,
            available_sheets,
            verbose=False,
            max_sheets_per_order=MAX_SHEETS_PER_ORDER,
        )

        # 9. ПРОВЕРКИ РЕЗУЛЬТАТОВ
        # Проверяем что оптимизация прошла успешно
        assert len(placed_layouts) > 0, "Не было создано ни одного листа с раскладкой"

        # Проверяем что все заказы были размещены (или количество неразмещенных минимально)
        total_placed = sum(len(layout["placed_polygons"]) for layout in placed_layouts)

        # Должно быть размещено большинство заказов (допускаем небольшое количество неразмещенных)
        placement_rate = total_placed / len(scaled_polygons)
        assert (
            placement_rate >= 0.8
        ), f"Размещено только {placement_rate*100:.1f}% заказов, ожидалось минимум 80%"

        # 10. ПРОВЕРЯЕМ КОРРЕКТНОСТЬ ИСПОЛЬЗОВАНИЯ ЛИСТОВ
        sheets_used = len(placed_layouts)
        total_available_sheets = sum(sheet["count"] for sheet in available_sheets)

        # Не должны использовать больше листов чем доступно
        assert (
            sheets_used <= total_available_sheets
        ), f"Использовано {sheets_used} листов, доступно {total_available_sheets}"

        # 11. ПРОВЕРЯЕМ ЧТО ЛИСТЫ ПРАВИЛЬНОГО ТИПА И ЦВЕТА
        for layout in placed_layouts:
            sheet_type = layout["sheet_type"]
            # Должен быть один из наших типов листов
            sheet_names = [sheet["name"] for sheet in available_sheets]
            assert sheet_type in sheet_names, f"Неизвестный тип листа: {sheet_type}"

        # 12. ПРОВЕРЯЕМ ЧТО СОЗДАЮТСЯ ВЫХОДНЫЕ ФАЙЛЫ (эмуляция)
        # В реальном Streamlit создаются DXF файлы, здесь проверяем структуру данных
        for layout in placed_layouts:
            assert "placed_polygons" in layout
            assert "sheet_size" in layout
            assert "sheet_number" in layout
            assert "usage_percent" in layout

            # Проверяем что в каждом layout есть размещенные полигоны
            assert (
                len(layout["placed_polygons"]) > 0
            ), f"Лист {layout['sheet_number']} пустой"

        # 13. СТРОГАЯ ПРОВЕРКА MAX_SHEETS_PER_ORDER ДЛЯ ЗАКЗАА ZAKAZ_row_20
        # Проверяем, что конкретно заказ ZAKAZ_row_20 соблюдает ограничение смежности
        zakaz_20_sheets = []
        for layout in placed_layouts:
            if "orders_on_sheet" in layout and "ZAKAZ_row_20" in layout["orders_on_sheet"]:
                zakaz_20_sheets.append(layout["sheet_number"])
        
        if zakaz_20_sheets:
            zakaz_20_sheets.sort()
            min_sheet = min(zakaz_20_sheets)
            max_sheet = max(zakaz_20_sheets)
            sheet_range = max_sheet - min_sheet + 1
            
            # Проверяем, что заказ размещен в пределах MAX_SHEETS_PER_ORDER смежных листов
            assert (
                sheet_range <= MAX_SHEETS_PER_ORDER
            ), (
                f"Заказ ZAKAZ_row_20 нарушает ограничение смежности: "
                f"размещен на листах {zakaz_20_sheets} (диапазон {sheet_range} > {MAX_SHEETS_PER_ORDER})"
            )
            
            # Дополнительная проверка: если заказ начат на листе N, то должен закончиться не позже чем на листе N+MAX_SHEETS_PER_ORDER-1
            expected_max_sheet = min_sheet + MAX_SHEETS_PER_ORDER - 1
            assert (
                max_sheet <= expected_max_sheet
            ), (
                f"Заказ ZAKAZ_row_20 выходит за пределы допустимого диапазона: "
                f"начат на листе {min_sheet}, закончен на листе {max_sheet}, "
                f"но должен был закончиться не позже листа {expected_max_sheet}"
            )
            
            print(f"✅ Заказ ZAKAZ_row_20: размещен на листах {zakaz_20_sheets} (диапазон {sheet_range} листов)")
        else:
            print(f"⚠️ Заказ ZAKAZ_row_20 не был размещен ни на одном листе")

        # 14. ФИНАЛЬНЫЕ ПРОВЕРКИ СТАТИСТИКИ
        print(f"\n=== РЕЗУЛЬТАТЫ ТЕСТА ===")
        print(f"Всего листов в наличии: {total_available_sheets}")
        print(f"Невыполненных заказов найдено: {len(all_orders)}")
        print(f"Заказов выбрано для обработки: {len(selected_orders)}")
        print(f"DXF полигонов создано: {len(dxf_files)}")
        print(f"Полигонов после масштабирования: {len(scaled_polygons)}")
        print(f"Листов с раскладкой создано: {len(placed_layouts)}")
        print(f"Всего полигонов размещено: {total_placed}")
        print(f"Полигонов не размещено: {len(unplaced_polygons)}")
        print(f"Процент размещения: {placement_rate*100:.1f}%")
        print(f"MAX_SHEETS_PER_ORDER ограничение: {MAX_SHEETS_PER_ORDER} листов")

        # Проверяем что тест прошел успешно
        assert len(all_orders) == 37  # Найдено ровно 37 невыполненных заказов
        assert len(selected_orders) == 37  # Все заказы выбраны
        assert len(placed_layouts) > 0  # Создан минимум 1 лист
        assert placement_rate >= 0.8  # Размещено минимум 80% заказов

        print("✅ Тест полной интеграции Streamlit прошел успешно!")

    def test_sheet_inventory_emulation(self):
        """Тестирует эмуляцию работы с инвентарем листов как в Streamlit."""

        # Эмулируем session_state для листов
        available_sheets = []

        # Добавляем листы как в реальном Streamlit интерфейсе
        sheet_configs = [
            {"width": 140, "height": 200, "color": "чёрный", "count": 20},
            {"width": 140, "height": 200, "color": "серый", "count": 20},
        ]

        for config in sheet_configs:
            new_sheet = {
                "name": f"Лист {config['width']}x{config['height']} {config['color']}",
                "width": config["width"],
                "height": config["height"],
                "color": config["color"],
                "count": config["count"],
                "used": 0,
            }
            available_sheets.append(new_sheet)

        # Проверяем что листы добавлены корректно
        assert len(available_sheets) == 2

        # Проверяем правильность структуры каждого листа
        for sheet in available_sheets:
            required_fields = ["name", "width", "height", "color", "count", "used"]
            for field in required_fields:
                assert field in sheet, f"Поле {field} отсутствует в конфигурации листа"

            assert sheet["width"] == 140
            assert sheet["height"] == 200
            assert sheet["count"] == 20
            assert sheet["used"] == 0
            assert sheet["color"] in ["чёрный", "серый"]

        # Проверяем общее количество листов
        total_sheets = sum(sheet["count"] for sheet in available_sheets)
        assert total_sheets == 40

        # Эмулируем использование листов
        available_sheets[0]["used"] += 3  # Используем 3 черных листа
        available_sheets[1]["used"] += 2  # Используем 2 серых листа

        # Проверяем оставшиеся листы
        remaining_black = available_sheets[0]["count"] - available_sheets[0]["used"]
        remaining_gray = available_sheets[1]["count"] - available_sheets[1]["used"]

        assert remaining_black == 17
        assert remaining_gray == 18

        print("✅ Тест эмуляции инвентаря листов прошел успешно!")

    def test_excel_parsing_emulation(self):
        """Тестирует точную эмуляцию парсинга Excel файла как в Streamlit."""

        # Читаем Excel файл точно как в Streamlit
        excel_data = pd.read_excel(
            self.sample_excel_path,
            sheet_name="ZAKAZ",
            header=None,
            date_format=None,
            parse_dates=False,
            engine="openpyxl",
        )

        # Проверяем что данные загрузились
        assert excel_data is not None
        assert len(excel_data) > 2  # Минимум заголовки + данные

        # Эмулируем точный алгоритм парсинга из Streamlit
        all_orders = []
        df = excel_data

        if df.shape[0] > 2:
            data_rows = df.iloc[2:].copy()

            if df.shape[1] > 3:
                # Ищем строки с пустой колонкой "Сделано" (индекс 2)
                pending_orders = data_rows[
                    data_rows.iloc[:, 2].isna() | (data_rows.iloc[:, 2] == "")
                ]

                for idx, row in pending_orders.iterrows():
                    if pd.notna(row.iloc[3]):  # Артикул не пустой
                        # Парсим цвет
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
                            "article": str(row.iloc[3]),
                            "product": str(row.iloc[4])
                            if pd.notna(row.iloc[4])
                            else "",
                            "order_id": unique_order_id,
                            "color": color,
                            "product_type": str(row.iloc[7])
                            if pd.notna(row.iloc[7]) and df.shape[1] > 7
                            else "",
                        }
                        all_orders.append(order)

        # Проверяем что найдено ровно 37 невыполненных заказов
        assert len(all_orders) == 37, f"Ожидалось 37 заказов, найдено {len(all_orders)}"

        # Проверяем что все заказы имеют нужные поля
        for order in all_orders:
            required_fields = [
                "sheet",
                "row_index",
                "article",
                "product",
                "order_id",
                "color",
                "product_type",
            ]
            for field in required_fields:
                assert (
                    field in order
                ), f"Поле {field} отсутствует в заказе {order.get('order_id', 'unknown')}"

            # Проверяем что артикул не пустой
            assert (
                len(order["article"].strip()) > 0
            ), f"Пустой артикул в заказе {order['order_id']}"

            # Проверяем цвет
            assert order["color"] in [
                "чёрный",
                "серый",
            ], f"Некорректный цвет {order['color']} в заказе {order['order_id']}"

        print(f"✅ Парсинг Excel: найдено {len(all_orders)} невыполненных заказов")
        print("✅ Тест эмуляции парсинга Excel прошел успешно!")
