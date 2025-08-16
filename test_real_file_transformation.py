#!/usr/bin/env python3
"""
Тест трансформации на реальном файле с параметрами из алгоритма размещения.
"""

import tempfile
import os
import ezdxf
import numpy as np
from layout_optimizer import parse_dxf_complete, save_dxf_layout_complete, apply_placement_transform, rotate_polygon
from shapely.geometry import Polygon
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MPLPolygon

def test_real_file_transformation():
    """Тестирует трансформацию на реальном файле."""
    print("=== ТЕСТ ТРАНСФОРМАЦИИ НА РЕАЛЬНОМ ФАЙЛЕ ===")
    
    source_dxf = "/home/sasha/proj/2025/eva_layout/200_140_1_black.dxf"
    
    print(f"📁 Тестируем файл: {source_dxf}")
    
    # Парсим исходный DXF
    with open(source_dxf, 'rb') as f:
        parsed_data = parse_dxf_complete(f, verbose=False)
    
    original_polygon = parsed_data['combined_polygon']
    print(f"📊 Combined polygon bounds: {original_polygon.bounds}")
    
    # Попробуем различные трансформации для проверки
    test_cases = [
        ("Без трансформации", 0, 0, 0),
        ("Сдвиг влево", -500, 0, 0), 
        ("Сдвиг вверх", 0, 300, 0),
        ("Поворот на 90°", 0, 0, 90),
        ("Комбинированная", -300, 200, 45),
    ]
    
    fig, axes = plt.subplots(2, 3, figsize=(18, 12))
    axes = axes.flatten()
    
    for i, (name, x_offset, y_offset, rotation_angle) in enumerate(test_cases):
        if i >= len(axes):
            break
            
        print(f"\\n🔄 Тест {i+1}: {name}")
        print(f"  Параметры: x_offset={x_offset}, y_offset={y_offset}, rotation={rotation_angle}°")
        
        # Создаем трансформированный полигон для сравнения
        expected_polygon = apply_placement_transform(original_polygon, x_offset, y_offset, rotation_angle)
        print(f"  Ожидаемые bounds: {expected_polygon.bounds}")
        
        file_name = f"test_case_{i+1}.dxf"
        color = "черный"
        
        # Создаем placed_element
        placed_element = (expected_polygon, x_offset, y_offset, rotation_angle, file_name, color)
        placed_elements = [placed_element]
        
        # Создаем original_dxf_data_map
        original_dxf_data_map = {
            file_name: parsed_data
        }
        
        sheet_size = (200, 140)  # см
        
        # Сохраняем результат
        with tempfile.NamedTemporaryFile(suffix='.dxf', delete=False) as tmp_file:
            output_path = tmp_file.name
        
        try:
            save_dxf_layout_complete(placed_elements, sheet_size, output_path, original_dxf_data_map)
            
            # Читаем результат и анализируем SPLINE'ы
            result_doc = ezdxf.readfile(output_path)
            result_msp = result_doc.modelspace()
            
            splines = [e for e in result_msp if e.dxftype() == 'SPLINE']
            print(f"  Результат: {len(splines)} SPLINE'ов")
            
            if splines:
                # Извлекаем bounds всех SPLINE'ов
                all_xs = []
                all_ys = []
                
                for spline in splines:
                    try:
                        control_points = spline.control_points
                        if control_points:
                            for cp in control_points:
                                if hasattr(cp, 'x') and hasattr(cp, 'y'):
                                    all_xs.append(cp.x)
                                    all_ys.append(cp.y)
                                elif len(cp) >= 2:
                                    all_xs.append(float(cp[0]))
                                    all_ys.append(float(cp[1]))
                    except:
                        continue
                
                if all_xs and all_ys:
                    actual_bounds = (min(all_xs), min(all_ys), max(all_xs), max(all_ys))
                    print(f"  Реальные bounds: {actual_bounds}")
                    
                    # Сравниваем с ожидаемыми
                    expected_bounds = expected_polygon.bounds
                    tolerance = 50  # 50мм допуск
                    
                    bounds_match = all(
                        abs(actual_bounds[j] - expected_bounds[j]) < tolerance
                        for j in range(4)
                    )
                    
                    if bounds_match:
                        print(f"  ✅ Трансформация КОРРЕКТНА!")
                    else:
                        diff = [actual_bounds[j] - expected_bounds[j] for j in range(4)]
                        print(f"  ⚠️ Небольшое расхождение: {diff}")
                        print(f"  📏 Макс. отклонение: {max(abs(d) for d in diff):.2f}мм")
                    
                    # Визуализируем результат
                    ax = axes[i]
                    
                    # Рисуем ожидаемый полигон
                    if hasattr(expected_polygon, 'exterior'):
                        expected_coords = list(expected_polygon.exterior.coords)
                        expected_patch = MPLPolygon(expected_coords, alpha=0.5, facecolor='blue', 
                                                  edgecolor='blue', label='Ожидаемый')
                        ax.add_patch(expected_patch)
                    
                    # Рисуем точки SPLINE'ов
                    ax.scatter(all_xs, all_ys, c='red', s=1, alpha=0.7, label='SPLINE точки')
                    
                    # Рисуем границы
                    ax.axhline(y=actual_bounds[1], color='red', linestyle='--', alpha=0.5)
                    ax.axhline(y=actual_bounds[3], color='red', linestyle='--', alpha=0.5)
                    ax.axvline(x=actual_bounds[0], color='red', linestyle='--', alpha=0.5)
                    ax.axvline(x=actual_bounds[2], color='red', linestyle='--', alpha=0.5)
                    
                    ax.set_title(f"{name}\\n{'✅ Корректно' if bounds_match else '⚠️ Расхождение'}")
                    ax.set_aspect('equal')
                    ax.grid(True, alpha=0.3)
                    ax.legend()
        
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)
    
    # Удаляем пустые subplot'ы
    for i in range(len(test_cases), len(axes)):
        axes[i].remove()
    
    plt.tight_layout()
    
    # Сохраняем визуализацию
    output_viz = "/home/sasha/proj/2025/eva_layout/spline_transformation_test.png"
    plt.savefig(output_viz, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"\\n✅ Визуализация сохранена: {output_viz}")

if __name__ == "__main__":
    print("🧪 Тест трансформации SPLINE на реальном файле")
    print("=" * 60)
    
    test_real_file_transformation()
    
    print("\\n" + "=" * 60)
    print("✅ ТЕСТ ЗАВЕРШЕН")
    print("📊 Проверьте визуализацию: spline_transformation_test.png")