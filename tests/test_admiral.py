from pathlib import Path

from dxf_utils import parse_dxf_complete
from layout_optimizer import Carpet, bin_packing_with_inventory


def test_admiral():
    """
    Тест плотности Admiral: 3 одинаковых ковра должны плотно стыковаться.
    Проблема: средний ковер может иметь неправильный угол, не стыкуясь с соседями.
    Цель: все 3 ковра на одном листе с одинаковым углом для плотной стыковки.
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

    # Создаем 3 одинаковых ковра Admiral
    priority1_polygons = []
    dxf_file = Path('data/Лодка ADMIRAL 340/1.dxf')
    try:
        polygon_data = parse_dxf_complete(dxf_file.as_posix(), verbose=False)
        if polygon_data and polygon_data.get("combined_polygon"):
            base_polygon = polygon_data["combined_polygon"]
            for i in range(1, 4):
                priority1_polygons.append(
                    Carpet(base_polygon, f"{dxf_file.name}_копия_{i}", "серый", f"group_{i}", 1)
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
        print(f"\n📄 ДЕТАЛИ ПО ЛИСТАМ:")
        for i, layout in enumerate(placed_layouts, 1):
            carpet_count = len(layout.placed_polygons)
            usage = layout.usage_percent
            print(f"   Лист {i}: {carpet_count} ковриков, {usage:.1f}% заполнение")

            # Проверяем углы - все должны быть одинаковые для плотной стыковки
            angles = [p.angle for p in layout.placed_polygons]
            print(f"   Углы: {angles}")

            # Все одинаковые ковры должны иметь одинаковый угол
            if len(set(angles)) > 1:
                print(f"   ⚠️ ПРЕДУПРЕЖДЕНИЕ: разные углы для одинаковых ковров!")

    # Проверки
    assert len(unplaced) == 0, f"Все ковры должны быть размещены, неразмещенных: {len(unplaced)}"
    assert len(placed_layouts) == 1, f"Нужно разместить на 1 листе: {len(placed_layouts)}"

    # Проверяем что все ковры имеют одинаковый угол для плотной стыковки
    if placed_layouts:
        angles = [p.angle for p in placed_layouts[0].placed_polygons]
        unique_angles = set(angles)
        assert len(unique_angles) == 1, f"Одинаковые ковры должны иметь одинаковый угол, но углы: {angles}"

    print(f"\n✅ ТЕСТ ПРОЙДЕН: {len(priority1_polygons)} ковров на 1 листе с одинаковым углом")

    return {
        'sheets_used': len(placed_layouts),
        'carpets_placed': len(priority1_polygons) - len(unplaced),
        'carpets_total': len(priority1_polygons),
    }
