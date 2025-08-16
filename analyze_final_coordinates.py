#!/usr/bin/env python3

"""
Анализ координат финального DXF файла
"""

import ezdxf

def analyze_dxf_coordinates():
    """Анализ всех координат в DXF файле"""
    print("=== АНАЛИЗ КООРДИНАТ DXF ФАЙЛА ===")
    
    try:
        doc = ezdxf.readfile("200_140_1_black.dxf")
        msp = doc.modelspace()
        
        # Счетчики по типам
        entity_counts = {}
        coordinate_ranges = {
            'x_min': float('inf'), 'x_max': float('-inf'),
            'y_min': float('inf'), 'y_max': float('-inf')
        }
        
        in_bounds_count = 0
        out_of_bounds_count = 0
        sheet_bounds = (0, 0, 1400, 2000)  # лист 140x200 см
        
        for entity in msp:
            entity_type = entity.dxftype()
            entity_counts[entity_type] = entity_counts.get(entity_type, 0) + 1
            
            coords = []
            
            if entity_type == 'SPLINE':
                if hasattr(entity, 'control_points') and entity.control_points:
                    for cp in entity.control_points:
                        if hasattr(cp, 'x') and hasattr(cp, 'y'):
                            coords.append((cp.x, cp.y))
                        elif len(cp) >= 2:
                            coords.append((float(cp[0]), float(cp[1])))
                            
            elif entity_type == 'IMAGE':
                if hasattr(entity.dxf, 'insert'):
                    pos = entity.dxf.insert
                    coords.append((pos[0], pos[1]))
                    
            elif entity_type == 'LWPOLYLINE':
                for point in entity.get_points():
                    coords.append((point[0], point[1]))
                    
            elif entity_type == 'LINE':
                coords.append((entity.dxf.start.x, entity.dxf.start.y))
                coords.append((entity.dxf.end.x, entity.dxf.end.y))
            
            # Обновляем диапазон координат
            for x, y in coords:
                coordinate_ranges['x_min'] = min(coordinate_ranges['x_min'], x)
                coordinate_ranges['x_max'] = max(coordinate_ranges['x_max'], x)
                coordinate_ranges['y_min'] = min(coordinate_ranges['y_min'], y)
                coordinate_ranges['y_max'] = max(coordinate_ranges['y_max'], y)
                
                # Проверяем, в пределах ли листа
                if (sheet_bounds[0] <= x <= sheet_bounds[2] and 
                    sheet_bounds[1] <= y <= sheet_bounds[3]):
                    in_bounds_count += 1
                else:
                    out_of_bounds_count += 1
        
        print("\n📊 Статистика сущностей:")
        for entity_type, count in sorted(entity_counts.items()):
            print(f"  {entity_type}: {count}")
        
        print("\n📏 Диапазон координат:")
        print(f"  X: [{coordinate_ranges['x_min']:.1f}, {coordinate_ranges['x_max']:.1f}]")
        print(f"  Y: [{coordinate_ranges['y_min']:.1f}, {coordinate_ranges['y_max']:.1f}]")
        
        print(f"\n📐 Размеры листа: {sheet_bounds[2]}x{sheet_bounds[3]} мм")
        
        print(f"\n🎯 Результат размещения:")
        print(f"  Точек в пределах листа: {in_bounds_count}")
        print(f"  Точек за пределами листа: {out_of_bounds_count}")
        
        # Оценка качества
        if out_of_bounds_count == 0:
            print("🎉 ОТЛИЧНО: Все элементы в пределах листа!")
        elif out_of_bounds_count < in_bounds_count * 0.1:
            print("✅ ХОРОШО: Большинство элементов в пределах листа")
        else:
            print("⚠️ ТРЕБУЕТ ДОРАБОТКИ: Много элементов за пределами листа")
            
        # Проверка IMAGE координат отдельно
        print(f"\n🖼️ Анализ IMAGE элементов:")
        image_in_bounds = 0
        image_total = 0
        
        for entity in msp:
            if entity.dxftype() == 'IMAGE':
                image_total += 1
                if hasattr(entity.dxf, 'insert'):
                    pos = entity.dxf.insert
                    if (sheet_bounds[0] <= pos[0] <= sheet_bounds[2] and 
                        sheet_bounds[1] <= pos[1] <= sheet_bounds[3]):
                        image_in_bounds += 1
                        status = "✅"
                    else:
                        status = "❌"
                    print(f"  IMAGE {image_total}: {status} ({pos[0]:.1f}, {pos[1]:.1f})")
        
        if image_total > 0:
            print(f"\n  IMAGE в пределах листа: {image_in_bounds}/{image_total}")
            if image_in_bounds == image_total:
                print("🎉 Все IMAGE элементы (текст/ярлыки) в правильных позициях!")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    analyze_dxf_coordinates()