from pathlib import Path
from dxf_utils import parse_dxf_complete
from layout_optimizer import Carpet

print("Checking areas of priority2 DXF polygons...")

base_path = Path('tests/priority2_dxf')

# Проверяем площади полигонов приоритета 1
priority1_ids = [1, 2, 3]  # Возьмем первые 3 для проверки
priority1_areas = []

for i in priority1_ids:
    dxf_file = base_path / f"{i}.dxf"
    if dxf_file.exists():
        polygon_data = parse_dxf_complete(dxf_file.as_posix(), verbose=False)
        if polygon_data and polygon_data.get("combined_polygon"):
            area = polygon_data["combined_polygon"].area
            priority1_areas.append(area)
            print(f"Priority 1 - {i}.dxf: area = {area:.0f} mm²")

# Проверяем площадь полигона приоритета 2
dxf_file = base_path / "priority2.dxf"
priority2_area = 0
if dxf_file.exists():
    polygon_data = parse_dxf_complete(dxf_file.as_posix(), verbose=False)
    if polygon_data and polygon_data.get("combined_polygon"):
        priority2_area = polygon_data["combined_polygon"].area
        print(f"Priority 2 - priority2.dxf: area = {priority2_area:.0f} mm²")

# Расчет площадей
total_priority1_area = sum(priority1_areas) * (14/3)  # Экстраполируем на 14 элементов
total_priority2_area = priority2_area * 15

print(f"\nРасчетные общие площади:")
print(f"Priority 1 (14 ковров): {total_priority1_area:.0f} mm² ≈ {total_priority1_area/100:.0f} см²") 
print(f"Priority 2 (15 ковров): {total_priority2_area:.0f} mm² ≈ {total_priority2_area/100:.0f} см²")
print(f"Общая площадь всех ковров: {(total_priority1_area + total_priority2_area):.0f} mm² ≈ {(total_priority1_area + total_priority2_area)/100:.0f} см²")

# Площадь листа
sheet_area = (140 * 10) * (200 * 10)  # 140cm x 200cm в мм²
print(f"Площадь одного листа: {sheet_area} mm² ≈ {sheet_area/100:.0f} см²")

theoretical_utilization = ((total_priority1_area + total_priority2_area) / sheet_area) * 100
print(f"Теоретическая утилизация одного листа: {theoretical_utilization:.1f}%")

if theoretical_utilization > 100:
    min_sheets = ((total_priority1_area + total_priority2_area) / sheet_area)
    print(f"❗ Требуется минимум {min_sheets:.1f} листа")
    
    # Проверим, помещаются ли все priority1 на одном листе
    priority1_utilization = (total_priority1_area / sheet_area) * 100
    print(f"Priority 1 утилизация одного листа: {priority1_utilization:.1f}%")
    
    if priority1_utilization > 100:
        print("❌ ПРОБЛЕМА: Priority 1 ковры не помещаются на одном листе!")
    elif priority1_utilization > 80:
        print("⚠️ Priority 1 ковры занимают большую часть листа")
    else:
        print("✅ Priority 1 ковры нормально помещаются на одном листе")