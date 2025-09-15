from pathlib import Path
from dxf_utils import parse_dxf_complete
from layout_optimizer import Carpet, bin_packing_with_inventory

def test_specific_overlap():
    """Тест для воспроизведения наложения ковров приоритета 2"""

    # Создаем листы
    available_sheets = [{
        "name": f"Черный лист",
        "width": 140,
        "height": 200,
        "color": "чёрный",
        "count": 5,
        "used": 0
    }]

    # 3 копии всех ковров из VOLVO XC70 2 (приоритет 1)
    priority1_polygons = []
    volvo_path = Path('dxf_samples/VOLVO XC70 2')
    files = list(volvo_path.rglob("*.dxf", case_sensitive=False))

    for dxf_file in files:
        try:
            polygon_data = parse_dxf_complete(dxf_file.as_posix(), verbose=False)
            if polygon_data and polygon_data.get("combined_polygon"):
                base_polygon = polygon_data["combined_polygon"]
                # 3 копии каждого ковра
                for i in range(1, 4):
                    priority1_polygons.append(Carpet(
                        base_polygon,
                        f"{dxf_file.name}_копия_{i}",
                        "чёрный",
                        f"volvo_group",
                        1
                    ))
        except Exception as e:
            print(f"⚠️ Ошибка загрузки {dxf_file}: {e}")

    print(f"📊 Загружено ковров приоритета 1: {len(priority1_polygons)}")

    # 1 копия ковра приоритета 2
    priority2_polygons = []
    kugoo_file = Path('dxf_samples/ДЕКА KUGOO M4 PRO JILONG/1.dxf')
    polygon_data = parse_dxf_complete(kugoo_file.as_posix(), verbose=False)
    if polygon_data and polygon_data.get("combined_polygon"):
        base_polygon = polygon_data["combined_polygon"]
        priority2_polygons.append(Carpet(
            base_polygon,
            f"{kugoo_file.name}_priority2",
            "чёрный",
            f"kugoo_group",
            2
        ))

    print(f"📊 Загружено ковров приоритета 2: {len(priority2_polygons)}")

    all_polygons = priority1_polygons + priority2_polygons
    print(f"📊 Всего ковров: {len(all_polygons)}")

    # Запускаем размещение
    placed_layouts, unplaced = bin_packing_with_inventory(
        all_polygons,
        available_sheets,
        verbose=True,
    )

    print(f"\n📄 Результат:")
    print(f"📊 Размещено: {len(all_polygons) - len(unplaced)}/{len(all_polygons)}")
    print(f"📄 Использовано листов: {len(placed_layouts)}")
    print(f"❌ Неразмещенных: {len(unplaced)}")

    # Анализ по листам
    for i, layout in enumerate(placed_layouts, 1):
        print(f"\n📄 Лист {i}: {len(layout.placed_polygons)} ковров")
        for j, carpet in enumerate(layout.placed_polygons):
            print(f"   {j+1}. {carpet.filename} (приоритет {carpet.priority})")

if __name__ == "__main__":
    test_specific_overlap()