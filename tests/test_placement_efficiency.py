from pathlib import Path

from layout_optimizer import parse_dxf_complete, Carpet, bin_packing_with_inventory


def test_placement_efficiency():
    # Создаем листы
    available_sheets = [{
            "name": f"Черный лист",
            "width": 144,
            "height": 200,
            "color": "чёрный",
            "count": 20,
            "used": 0
        }]


    # Создаем полигоны приоритета 1
    #########################################
    models = ["AUDI Q7 (4L) 1", "BMW X5 E53 1 и рестайлинг", "BMW X5 G05-G18 4 и рестайлинг"]
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
                    priority1_polygons.append(Carpet(base_polygon, dxf_file.name, "чёрный", f"group_{group_id}", 1))

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

    # Анализ результатов
    print("\n=== РЕЗУЛЬТАТЫ ===")
    actual_placed_count = len(priority1_polygons) - len(unplaced)
    print(f"Размещено полигонов: {actual_placed_count}/{len(priority1_polygons)}")
    print(f"Использовано листов: {len(placed_layouts)}")
    print(f"Неразмещенных полигонов: {len(unplaced)}")

    assert len(placed_layouts) <= 3
    return None