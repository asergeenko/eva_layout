from pathlib import Path

from dxf_utils import parse_dxf_complete
from layout_optimizer import Carpet, bin_packing_with_inventory


def test_trimaran():
    """
    Тест для Тримаран 360: файлы с незамкнутыми SPLINE контурами.
    Проблема: файлы 1.dxf и 2.dxf содержат только SPLINE, которые образуют
    незамкнутые контуры (текст + контур, но контур разомкнут).
    Решение: парсер должен выдать предупреждение и пропустить файлы.
    """
    # Загружаем файлы Тримаран
    polygons = []
    warnings = []
    base_path = Path('data/Лодка Звезда Тримаран 360')

    for dxf_file in sorted(base_path.glob('*.dxf')):
        data = parse_dxf_complete(dxf_file.as_posix(), verbose=False)

        if data and data.get('combined_polygon'):
            poly = data['combined_polygon']
            bounds = poly.bounds
            width = bounds[2] - bounds[0]
            height = bounds[3] - bounds[1]

            # Проверяем что polygon нормализован к (0,0)
            assert bounds[0] < 1, f"{dxf_file.name}: X координата должна начинаться с ~0, но {bounds[0]}"
            assert bounds[1] < 1, f"{dxf_file.name}: Y координата должна начинаться с ~0, но {bounds[1]}"

            print(f"{dxf_file.name}: ✅ size={width:.0f}x{height:.0f} mm, area={poly.area:.0f} mm²")
            polygons.append(Carpet(poly, dxf_file.name, "чёрный", f"trimaran_{dxf_file.stem}", 1))
        else:
            # Файл пропущен - записываем предупреждение
            warning = data.get('parse_warning', 'Unknown error')
            warnings.append(f"{dxf_file.name}: {warning}")
            print(f"{dxf_file.name}: ⚠️  {warning}")

    # Проверяем что файлы с незамкнутыми контурами были пропущены
    print(f"\n📊 Обработано файлов: {len(list(base_path.glob('*.dxf')))}")
    print(f"✅ Успешно распознано: {len(polygons)}")
    print(f"⚠️  Предупреждений: {len(warnings)}")

    for warning in warnings:
        print(f"   - {warning}")

    # Для файлов Trimaran ожидаем что они не будут обработаны (незамкнутые контуры)
    assert len(warnings) == 2, f"Ожидалось 2 предупреждения о незамкнутых контурах, получено {len(warnings)}"
    assert len(polygons) == 0, f"Файлы с незамкнутыми контурами должны быть пропущены, но получено {len(polygons)} полигонов"

    print(f"\n✅ ТЕСТ ПРОЙДЕН: Файлы с незамкнутыми контурами корректно пропущены с предупреждениями")

    return {
        'files_total': len(list(base_path.glob('*.dxf'))),
        'files_parsed': len(polygons),
        'warnings': len(warnings),
    }
