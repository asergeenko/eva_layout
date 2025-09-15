from pathlib import Path
import time

from dxf_utils import parse_dxf_complete
from excel_loader import DXF_ROOT_DIR
from layout_optimizer import Carpet, bin_packing_with_inventory


def test_volvo():
    # Создаем листы
    available_sheets = [{
        "name": f"Черный лист",
        "width": 140,
        "height": 200,
        "color": "чёрный",
        "count": 5,
        "used": 0
    }]

    # Создаем полигоны приоритета 1
    #########################################
    models = ["VOLVO XC70 2"]
    priority1_polygons = []
    for group_id, group in enumerate(models, 1):
        path = Path('dxf_samples') / group
        files = path.rglob("*.dxf", case_sensitive=False)
        for dxf_file in files:
            try:
                # Используем verbose=False чтобы избежать Streamlit вызовов
                polygon_data = parse_dxf_complete(dxf_file.as_posix(), verbose=False)
                if polygon_data and polygon_data.get("combined_polygon"):
                    base_polygon = polygon_data["combined_polygon"]
                    priority1_polygons.append(Carpet(base_polygon, f"{dxf_file.name}", "чёрный", f"group_{group_id}", 1))

            except Exception as e:
                print(f"⚠️ Ошибка загрузки {dxf_file}: {e}")
                return []

    priority2_polygons = []
    dxf_file = Path(DXF_ROOT_DIR) / "ДЕКА KUGOO M4 PRO JILONG/1.dxf"
    polygon_data = parse_dxf_complete(dxf_file.as_posix(), verbose=False)
    if polygon_data and polygon_data.get("combined_polygon"):
        base_polygon = polygon_data["combined_polygon"]
        for i in range(20):
            priority2_polygons.append(Carpet(base_polygon, f"{dxf_file.name}_копия_{i}", "чёрный", f"group_10", 2))

    all_polygons = priority1_polygons + priority2_polygons
    #########################################
    placed_layouts, unplaced = bin_packing_with_inventory(
        all_polygons,
        available_sheets,
        verbose=True,
    )

    actual_placed_count = len(all_polygons) - len(unplaced)

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
        f"📊 Размещено полигонов: {actual_placed_count}/{len(all_polygons)} ({actual_placed_count / len(all_polygons) * 100:.1f}%)")
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

    # Оценка эффективности
    print(f"\n🎯 ОЦЕНКА ЭФФЕКТИВНОСТИ:")
    if len(placed_layouts) <= 3 and len(unplaced) == 0:
        print("   ✅ ОТЛИЧНО! Цель достигнута: ≤3 листа, все ковры размещены")
        efficiency_score = "A+"
    else:
        print("   ❌ ПЛОХО! >4 листов и низкое использование материала")
        efficiency_score = "D"

    print(f"   Оценка эффективности: {efficiency_score}")

    client_goal_achieved = (len(placed_layouts) <= 3 and
                            len(unplaced) == 0
                            )

    if client_goal_achieved:
        print("   ✅ ЦЕЛЬ КЛИЕНТА ДОСТИГНУТА!")
    else:
        print("   ❌ ЦЕЛЬ КЛИЕНТА НЕ ДОСТИГНУТА")

    # Проверяем улучшение плотности по сравнению с базовым уровнем
    assert len(unplaced) == 0, f"Все ковры должны быть размещены, неразмещенных: {len(unplaced)}"
    assert len(placed_layouts) <= 3, f"Нужно разместить заказы на 3 листах: {len(placed_layouts)}"

    return {
        'sheets_used': len(placed_layouts),
        'carpets_placed': actual_placed_count,
        'carpets_total': len(all_polygons),

        'material_utilization': material_utilization,
        'efficiency_score': efficiency_score,
        'client_goal_achieved': client_goal_achieved
    }