from pathlib import Path

from dxf_utils import parse_dxf_complete
from layout_optimizer import Carpet, bin_packing_with_inventory


def test_admiral_corolla():
    """
    Тест плотности Admiral + Corolla: разные ковры должны размещаться компактно.
    Проблема: Corolla может запирать пространство справа, не прижимаясь к левому краю.
    Цель: максимальная плотность с минимумом блокированного пространства.
    """
    # Создаем листы - серые
    available_sheets = [{
        "name": "Серый лист",
        "width": 140,
        "height": 200,
        "color": "серый",
        "count": 1,
        "used": 0
    }]

    priority1_polygons = []

    # 1 Admiral
    dxf_file = Path('data/Лодка ADMIRAL 340/1.dxf')
    try:
        polygon_data = parse_dxf_complete(dxf_file.as_posix(), verbose=False)
        if polygon_data and polygon_data.get("combined_polygon"):
            priority1_polygons.append(
                Carpet(polygon_data["combined_polygon"], dxf_file.name, "серый", "admiral_1", 1)
            )
    except Exception as e:
        print(f"⚠️ Ошибка загрузки {dxf_file}: {e}")
        return []

    # 2 Corolla (разные order_id)
    dxf_file = Path('data/TOYOTA COROLLA 9/2.dxf')
    try:
        polygon_data = parse_dxf_complete(dxf_file.as_posix(), verbose=False)
        if polygon_data and polygon_data.get("combined_polygon"):
            base_polygon = polygon_data["combined_polygon"]
            for i in range(1, 3):
                priority1_polygons.append(
                    Carpet(base_polygon, f"{dxf_file.name}_копия_{i}", "серый", f"corolla_{i}", 1)
                )
    except Exception as e:
        print(f"⚠️ Ошибка загрузки {dxf_file}: {e}")
        return []

    placed_layouts, unplaced = bin_packing_with_inventory(
        priority1_polygons,
        available_sheets,
        verbose=True,
    )

    # Анализ результатов
    print(f"\n📊 Размещено полигонов: {len(priority1_polygons) - len(unplaced)}/{len(priority1_polygons)}")
    print(f"📄 Использовано листов: {len(placed_layouts)}")

    if placed_layouts:
        print(f"\n📄 ДЕТАЛИ РАЗМЕЩЕНИЯ:")
        for i, poly in enumerate(placed_layouts[0].placed_polygons, 1):
            bounds = poly.polygon.bounds
            left_edge = bounds[0]
            print(f"   {i}. {poly.order_id}: X=[{bounds[0]:.1f}, {bounds[2]:.1f}], angle={poly.angle}°, left_edge={left_edge:.1f}mm")

        # Проверяем что хотя бы один ковер прижат к левому краю (X < 10mm)
        left_edges = [p.polygon.bounds[0] for p in placed_layouts[0].placed_polygons]
        min_left_edge = min(left_edges)
        print(f"\n   Минимальный left_edge: {min_left_edge:.1f}mm")

        if min_left_edge > 10:
            print(f"   ⚠️ ПРЕДУПРЕЖДЕНИЕ: ни один ковер не прижат к левому краю!")

        usage = placed_layouts[0].usage_percent
        print(f"   Заполнение листа: {usage:.1f}%")

    # Проверки
    assert len(unplaced) == 0, f"Все ковры должны быть размещены, неразмещенных: {len(unplaced)}"
    assert len(placed_layouts) == 1, f"Нужно разместить на 1 листе: {len(placed_layouts)}"

    # Проверяем что есть ковер прижатый к левому краю для максимальной плотности
    if placed_layouts:
        left_edges = [p.polygon.bounds[0] for p in placed_layouts[0].placed_polygons]
        min_left_edge = min(left_edges)
        assert min_left_edge < 10, f"Хотя бы один ковер должен быть прижат к левому краю (X<10mm), но min_left={min_left_edge:.1f}mm"

        # Заполнение должно быть разумным
        usage = placed_layouts[0].usage_percent
        assert usage >= 45, f"Заполнение листа должно быть >= 45%, но {usage:.1f}%"

    print(f"\n✅ ТЕСТ ПРОЙДЕН: плотное размещение с прижатостью к краям")

    return {
        'sheets_used': len(placed_layouts),
        'carpets_placed': len(priority1_polygons) - len(unplaced),
        'carpets_total': len(priority1_polygons),
    }
