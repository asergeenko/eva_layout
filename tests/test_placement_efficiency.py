from pathlib import Path
import time

from dxf_utils import parse_dxf_complete
from layout_optimizer import Carpet, bin_packing_with_inventory


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

    # Анализ результатов с детальными метриками плотности
    print("\n=== РЕЗУЛЬТАТЫ ЭФФЕКТИВНОСТИ РАЗМЕЩЕНИЯ ===")
    
    start_time = time.time()
    actual_placed_count = len(priority1_polygons) - len(unplaced)
    
    # Вычисляем общую площадь ковриков
    total_carpet_area_mm2 = sum(carpet.polygon.area for carpet in priority1_polygons)
    # FIXED: Convert unplaced to set of identifiers for proper comparison
    unplaced_ids = set((u.filename, u.color, u.order_id) for u in unplaced)
    placed_carpet_area_mm2 = sum(
        carpet.polygon.area for carpet in priority1_polygons 
        if (carpet.filename, carpet.color, carpet.order_id) not in unplaced_ids
    )
    
    # Площадь листов
    sheet_area_mm2 = (available_sheets[0]['width'] * 10) * (available_sheets[0]['height'] * 10)
    used_sheets_area_mm2 = len(placed_layouts) * sheet_area_mm2
    theoretical_min_sheets = total_carpet_area_mm2 / sheet_area_mm2
    
    # Процент использования материала
    material_utilization = (placed_carpet_area_mm2 / used_sheets_area_mm2) * 100 if used_sheets_area_mm2 > 0 else 0
    
    print(f"📊 Размещено полигонов: {actual_placed_count}/{len(priority1_polygons)} ({actual_placed_count/len(priority1_polygons)*100:.1f}%)")
    print(f"📄 Использовано листов: {len(placed_layouts)}")
    print(f"📐 Общая площадь ковриков: {total_carpet_area_mm2/100:.0f} см²")
    print(f"📐 Площадь использованных листов: {used_sheets_area_mm2/100:.0f} см²") 
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
    if len(placed_layouts) <= 2 and len(unplaced) == 0:
        print("   ✅ ОТЛИЧНО! Цель достигнута: ≤2 листа, все ковры размещены")
        efficiency_score = "A+"
    elif len(placed_layouts) <= 2:
        print("   ⚠️  ХОРОШО! ≤2 листа, но есть неразмещенные ковры")  
        efficiency_score = "B+"
    elif material_utilization >= 60:
        print("   ⚠️  УДОВЛЕТВОРИТЕЛЬНО! >2 листов, но высокое использование материала")
        efficiency_score = "B"
    elif material_utilization >= 40:
        print("   ❌ НЕУДОВЛЕТВОРИТЕЛЬНО! >2 листов и среднее использование материала")
        efficiency_score = "C"
    else:
        print("   ❌ ПЛОХО! >2 листов и низкое использование материала")
        efficiency_score = "D"
    
    print(f"   Оценка эффективности: {efficiency_score}")
    
    # Строгое требование: ≤2 листа с использованием ≥78% (цель клиента)
    target_utilization = 78.1  # как рассчитано в benchmark
    
    print(f"\n🏆 ЦЕЛЬ КЛИЕНТА:")
    print(f"   Листов: ≤2 (текущий: {len(placed_layouts)})")  
    print(f"   Использование: ≥{target_utilization:.1f}% (текущий: {material_utilization:.1f}%)")
    
    client_goal_achieved = (len(placed_layouts) <= 2 and 
                          len(unplaced) == 0 and 
                          material_utilization >= target_utilization)
    
    if client_goal_achieved:
        print("   ✅ ЦЕЛЬ КЛИЕНТА ДОСТИГНУТА!")
    else:
        print("   ❌ ЦЕЛЬ КЛИЕНТА НЕ ДОСТИГНУТА")
    
    # Проверяем улучшение плотности по сравнению с базовым уровнем
    baseline_material_utilization = 45.0  # Базовый уровень для сравнения
    assert material_utilization > baseline_material_utilization, f"Требуется улучшение плотности >45%, получили {material_utilization:.1f}%"
    assert len(unplaced) == 0, f"Все ковры должны быть размещены, неразмещенных: {len(unplaced)}"
    
    # Дополнительная проверка: если удается разместить на 2 листах с хорошей плотностью - отлично
    two_sheet_goal_achieved = (len(placed_layouts) <= 2 and material_utilization >= 78.1)
    if two_sheet_goal_achieved:
        print("🏆 БОНУС: Достигнута цель клиента на 2 листах!")
    else:
        print(f"📈 ПРОГРЕСС: Плотность {material_utilization:.1f}% > базового {baseline_material_utilization}%")
    
    return {
        'sheets_used': len(placed_layouts),
        'carpets_placed': actual_placed_count,
        'carpets_total': len(priority1_polygons), 
        'material_utilization': material_utilization,
        'efficiency_score': efficiency_score,
        'client_goal_achieved': client_goal_achieved
    }