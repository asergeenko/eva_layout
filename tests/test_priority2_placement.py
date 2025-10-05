from pathlib import Path
import time

import pytest

from dxf_utils import parse_dxf_complete
from layout_optimizer import Carpet, bin_packing_with_inventory

#@pytest.mark.skip
def test_priority2_placement():
    # Создаем листы
    available_sheets = [{
        "name": f"Черный лист",
        "width": 140,
        "height": 200,
        "color": "чёрный",
        "count": 5,
        "used": 0
    }]

    base_path = Path('tests/priority2_dxf')
    # Создаем полигоны приоритета 1
    #########################################

    priority1_polygons = []
    priority1_ids = [1,2,3,4,5,11,12,13,14,21,22,23,24,25]
    for i in priority1_ids:
        dxf_file = base_path / f"{i}.dxf"
        polygon_data = parse_dxf_complete(dxf_file.as_posix(), verbose=False)
        if polygon_data and polygon_data.get("combined_polygon"):
            base_polygon = polygon_data["combined_polygon"]
            priority1_polygons.append(Carpet(base_polygon, dxf_file.name, "чёрный", f"group_1", 1))
    #########################################
    print(f"📊 Всего полигонов для размещения: {len(priority1_polygons)}")
    # Масштабируем полигоны
    if not priority1_polygons:
        print("❌ Нет полигонов для обработки")
        return

    priority2_polygons = []
    dxf_file = base_path / "priority2.dxf"
    polygon_data = parse_dxf_complete(dxf_file.as_posix(), verbose=False)
    if polygon_data and polygon_data.get("combined_polygon"):
        base_polygon = polygon_data["combined_polygon"]
        for i in range(15):
            priority2_polygons.append(Carpet(base_polygon, f"{dxf_file.name}_копия_{i}", "чёрный", f"group_2", 2))

    all_polygons = priority1_polygons + priority2_polygons
    placed_layouts, unplaced = bin_packing_with_inventory(
        all_polygons,
        available_sheets,
        verbose=True,
    )

    # Анализ результатов с детальными метриками плотности
    print("\n=== РЕЗУЛЬТАТЫ ЭФФЕКТИВНОСТИ РАЗМЕЩЕНИЯ ===")

    start_time = time.time()
    actual_placed_count = len(all_polygons) - len(unplaced)

    # Вычисляем общую площадь ковриков (ИСПРАВЛЕНО: используем all_polygons)
    total_carpet_area_mm2 = sum(carpet.polygon.area for carpet in all_polygons)
    # FIXED: Convert unplaced to set of carpet_ids for proper comparison
    unplaced_ids = set(u.carpet_id for u in unplaced)
    placed_carpet_area_mm2 = sum(
        carpet.polygon.area for carpet in all_polygons 
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
    
    # Детальная диагностика по приоритетам
    priority1_unplaced = [c for c in unplaced if hasattr(c, 'priority') and c.priority == 1]
    priority2_unplaced = [c for c in unplaced if hasattr(c, 'priority') and c.priority == 2]
    
    priority1_placed = len(priority1_polygons) - len(priority1_unplaced)
    priority2_placed = len(priority2_polygons) - len(priority2_unplaced)
    
    print(f"🔸 Приоритет 1: {priority1_placed}/{len(priority1_polygons)} размещено")
    print(f"🔸 Приоритет 2: {priority2_placed}/{len(priority2_polygons)} размещено")

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


    target_utilization = 78.1  # как рассчитано в benchmark

    print(f"\n🏆 ЦЕЛЬ КЛИЕНТА:")
    print(f"   Листов: ≤3 (текущий: {len(placed_layouts)})")
    print(f"   Использование: ≥{target_utilization:.1f}% (текущий: {material_utilization:.1f}%)")

    client_goal_achieved = (len(placed_layouts) <= 3 and
                            len(unplaced) == 0
                            )

    if client_goal_achieved:
        print("   ✅ ЦЕЛЬ КЛИЕНТА ДОСТИГНУТА!")
    else:
        print("   ❌ ЦЕЛЬ КЛИЕНТА НЕ ДОСТИГНУТА")

    assert len(unplaced) == 0, f"Все ковры должны быть размещены, неразмещенных: {len(unplaced)}"


    return {
        'sheets_used': len(placed_layouts),
        'carpets_placed': actual_placed_count,
        'carpets_total': len(all_polygons),
        'material_utilization': material_utilization,
        'client_goal_achieved': client_goal_achieved
    }