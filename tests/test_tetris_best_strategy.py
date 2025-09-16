from pathlib import Path
import time

from dxf_utils import parse_dxf_complete
from layout_optimizer import Carpet, bin_packing_with_inventory


def test_tetris_best_strategy():
    # Создаем листы
    available_sheets = [{
        "name": f"Черный лист",
        "width": 144,
        "height": 200,
        "color": "чёрный",
        "count": 1,
        "used": 0
    }]

    # Создаем полигоны приоритета 1
    #########################################
    priority1_polygons = []
    paths = [Path(f'dxf_samples/SKODA KODIAQ/{i}.dxf') for i in (1,1,1,4)]
    for i, dxf_file in enumerate(paths):
        try:
            # Используем verbose=False чтобы избежать Streamlit вызовов
            polygon_data = parse_dxf_complete(dxf_file.as_posix(), verbose=False)
            if polygon_data and polygon_data.get("combined_polygon"):
                base_polygon = polygon_data["combined_polygon"]
                priority1_polygons.append(Carpet(base_polygon, dxf_file.name, "чёрный", f"group_{i}", 1))

        except Exception as e:
            print(f"⚠️ Ошибка загрузки {dxf_file}: {e}")
            return []
    #########################################
    print(f"📊 Всего полигонов для размещения: {len(priority1_polygons)}")

    # Масштабируем полигоны
    if not priority1_polygons:
        print("❌ Нет полигонов для обработки")
        return

    placed_layouts, unplaced = bin_packing_with_inventory(
        priority1_polygons,
        available_sheets,
        verbose=True,
    )

    # Анализ результатов с детальными метриками плотности
    print("\n=== РЕЗУЛЬТАТЫ ЭФФЕКТИВНОСТИ РАЗМЕЩЕНИЯ ===")

    actual_placed_count = len(priority1_polygons) - len(unplaced)

    # Вычисляем общую площадь ковриков
    total_carpet_area_mm2 = sum(carpet.polygon.area for carpet in priority1_polygons)
    # FIXED: Convert unplaced to set of carpet_ids for proper comparison
    unplaced_ids = set(u.carpet_id for u in unplaced)
    placed_carpet_area_mm2 = sum(
        carpet.polygon.area for carpet in priority1_polygons
        if carpet.carpet_id not in unplaced_ids
    )

    # Площадь листов
    sheet_area_mm2 = (available_sheets[0]['width'] * 10) * (available_sheets[0]['height'] * 10)
    used_sheets_area_mm2 = len(placed_layouts) * sheet_area_mm2
    theoretical_min_sheets = total_carpet_area_mm2 / sheet_area_mm2

    # Процент использования материала
    material_utilization = (placed_carpet_area_mm2 / used_sheets_area_mm2) * 100 if used_sheets_area_mm2 > 0 else 0

    print(
        f"📊 Размещено полигонов: {actual_placed_count}/{len(priority1_polygons)} ({actual_placed_count / len(priority1_polygons) * 100:.1f}%)")
    print(f"📄 Использовано листов: {len(placed_layouts)}")
    print(f"📐 Общая площадь ковриков: {total_carpet_area_mm2 / 100:.0f} см²")
    print(f"📐 Площадь использованных листов: {used_sheets_area_mm2 / 100:.0f} см²")
    print(f"🎯 Использование материала: {material_utilization:.1f}%")
    print(f"📊 Теоретический минимум: {theoretical_min_sheets:.2f} листа")
    print(f"❌ Неразмещенных полигонов: {len(unplaced)}")

    if placed_layouts:
        print(f"\n📄 ДЕТАЛИ ПО ЛИСТАМ:")
        total_sheet_usage = 0
        for i, layout in enumerate(placed_layouts, 1):
            carpet_count = len(layout.placed_polygons)
            usage = layout.usage_percent
            total_sheet_usage += usage
            print(f"   Лист {i}: {carpet_count} ковриков, {usage:.1f}% заполнение")

        avg_sheet_usage = total_sheet_usage / len(placed_layouts)
        print(f"   Среднее заполнение листов: {avg_sheet_usage:.1f}%")

    assert len(unplaced) == 0, f"Все ковры должны быть размещены, неразмещенных: {len(unplaced)}"

    return {
        'sheets_used': len(placed_layouts),
        'carpets_placed': actual_placed_count,
        'carpets_total': len(priority1_polygons),
        'material_utilization': material_utilization,
    }