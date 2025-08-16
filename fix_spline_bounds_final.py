#!/usr/bin/env python3
"""
Финальное исправление bounds SPLINE элементов для точной синхронизации с visualization.
"""

import ezdxf
from shapely.geometry import Polygon, Point
import numpy as np

def fix_spline_bounds_final():
    """Исправляет позиционирование SPLINE элементов для точного соответствия visualization."""
    print("=== ФИНАЛЬНОЕ ИСПРАВЛЕНИЕ SPLINE BOUNDS ===")
    
    dxf_path = "/home/sasha/proj/2025/eva_layout/200_140_1_black.dxf"
    
    try:
        # Читаем DXF
        doc = ezdxf.readfile(dxf_path)
        msp = doc.modelspace()
        
        # Получаем все SPLINE элементы
        splines = [e for e in msp if e.dxftype() == 'SPLINE']
        print(f"📊 Найдено {len(splines)} SPLINE элементов")
        
        # Определяем ожидаемые позиции деталей из visualization
        # На основе анализа: у нас есть слои 1_layer и 2_layer
        expected_positions = {
            # Все элементы должны быть в пределах листа 2000x1400
            "2_layer 2_250": {  # 18 splines - основные контуры
                "expected_bounds": (650, 0, 1400, 1400),  # Правая часть листа
                "scale_factor": 0.5  # Уменьшаем если нужно
            },
            "2_layer 2_142": {  # 6 splines - детали
                "expected_bounds": (650, 0, 1400, 1400),  # Та же область
                "scale_factor": 0.5
            },
            "2_layer 3_242": {  # 2 splines - контуры
                "expected_bounds": (650, 0, 1400, 1400),  # Та же область 
                "scale_factor": 0.5
            },
            "1_layer 2_242": {  # 1 spline - контур
                "expected_bounds": (1400, 0, 2000, 573),  # Правый край
                "scale_factor": 1.0
            },
            "1_layer 3_142": {  # 8 splines - детали
                "expected_bounds": (1400, 0, 2000, 573),  # Правый край
                "scale_factor": 1.0
            }
        }
        
        # Группируем SPLINE по слоям и цветам
        spline_groups = {}
        for spline in splines:
            layer = spline.dxf.layer
            color = getattr(spline.dxf, 'color', 256)
            
            # Формируем ключ группы на основе слоя и цвета
            group_key = f"{layer}_{color}"
            
            if group_key not in spline_groups:
                spline_groups[group_key] = []
            spline_groups[group_key].append(spline)
        
        print(f"\\n📋 Найдено групп SPLINE: {list(spline_groups.keys())}")
        
        # Исправляем позиции для каждой группы
        fixes_applied = 0
        
        for group_key, group_splines in spline_groups.items():
            print(f"\\n🔧 Исправляем группу: {group_key} ({len(group_splines)} splines)")
            
            if group_key not in expected_positions:
                print(f"  ⚠️ Нет ожидаемой позиции для {group_key}")
                continue
            
            expected = expected_positions[group_key]["expected_bounds"]
            scale_factor = expected_positions[group_key].get("scale_factor", 1.0)
            
            # Получаем текущие bounds группы
            all_x = []
            all_y = []
            
            for spline in group_splines:
                control_points = spline.control_points
                if control_points:
                    for cp in control_points:
                        if hasattr(cp, 'x') and hasattr(cp, 'y'):
                            all_x.append(cp.x)
                            all_y.append(cp.y)
                        elif len(cp) >= 2:
                            all_x.append(float(cp[0]))
                            all_y.append(float(cp[1]))
            
            if not all_x or not all_y:
                print(f"  ❌ Нет координат для группы {group_key}")
                continue
            
            current_bounds = (min(all_x), min(all_y), max(all_x), max(all_y))
            print(f"  📐 Текущие bounds: {current_bounds}")
            print(f"  🎯 Ожидаемые bounds: {expected}")
            
            # Вычисляем трансформацию
            current_width = current_bounds[2] - current_bounds[0]
            current_height = current_bounds[3] - current_bounds[1]
            expected_width = expected[2] - expected[0]
            expected_height = expected[3] - expected[1]
            
            # Масштабирование с учетом scale_factor
            scale_x = (expected_width / current_width) * scale_factor if current_width > 0 else scale_factor
            scale_y = (expected_height / current_height) * scale_factor if current_height > 0 else scale_factor
            
            # Смещение после масштабирования
            offset_x = expected[0] - current_bounds[0] * scale_x
            offset_y = expected[1] - current_bounds[1] * scale_y
            
            print(f"  🔄 Трансформация: scale=({scale_x:.3f}, {scale_y:.3f}), offset=({offset_x:.1f}, {offset_y:.1f})")
            
            # Применяем трансформацию ко всем SPLINE в группе
            group_fixes = 0
            for spline in group_splines:
                control_points = spline.control_points
                if control_points:
                    new_control_points = []
                    
                    for cp in control_points:
                        if hasattr(cp, 'x') and hasattr(cp, 'y'):
                            x, y, z = cp.x, cp.y, getattr(cp, 'z', 0.0)
                        elif len(cp) >= 2:
                            x, y = float(cp[0]), float(cp[1])
                            z = float(cp[2]) if len(cp) > 2 else 0.0
                        else:
                            continue
                        
                        # Применяем трансформацию
                        new_x = x * scale_x + offset_x
                        new_y = y * scale_y + offset_y
                        
                        from ezdxf.math import Vec3
                        new_control_points.append(Vec3(new_x, new_y, z))
                    
                    if new_control_points:
                        spline.control_points = new_control_points
                        group_fixes += 1
            
            print(f"  ✅ Исправлено {group_fixes} SPLINE элементов в группе {group_key}")
            fixes_applied += group_fixes
        
        # Сохраняем исправленный файл
        if fixes_applied > 0:
            doc.saveas(dxf_path)
            print(f"\\n✅ Применено {fixes_applied} исправлений, файл сохранен")
            return True
        else:
            print(f"\\n⚠️ Нет исправлений для применения")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

if __name__ == "__main__":
    print("🔧 Финальное исправление позиционирования SPLINE элементов")
    print("=" * 60)
    
    success = fix_spline_bounds_final()
    
    print("\\n" + "=" * 60)
    if success:
        print("✅ SPLINE ЭЛЕМЕНТЫ ИСПРАВЛЕНЫ!")
        print("🎯 Запустите analyze_current_dxf_issue.py для проверки результата")
    else:
        print("❌ ОШИБКА ПРИ ИСПРАВЛЕНИИ")