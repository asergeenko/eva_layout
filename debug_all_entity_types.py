#!/usr/bin/env python3

import ezdxf
from collections import defaultdict

def analyze_all_dxf_entity_types():
    """Анализ всех типов сущностей в DXF файле"""
    
    print("=== АНАЛИЗ ВСЕХ ТИПОВ СУЩНОСТЕЙ В DXF ===")
    
    dxf_file = "200_140_1_black.dxf"
    
    try:
        doc = ezdxf.readfile(dxf_file)
        msp = doc.modelspace()
        
        # Подсчет типов сущностей
        entity_types = defaultdict(int)
        entity_samples = defaultdict(list)
        
        for entity in msp:
            entity_type = entity.dxftype()
            entity_types[entity_type] += 1
            
            # Сохраняем первые 3 примера каждого типа
            if len(entity_samples[entity_type]) < 3:
                entity_samples[entity_type].append(entity)
        
        print(f"Найдено типов сущностей: {len(entity_types)}")
        print("\nСтатистика по типам:")
        
        for entity_type, count in sorted(entity_types.items()):
            print(f"  {entity_type}: {count}")
        
        print("\n=== ДЕТАЛЬНЫЙ АНАЛИЗ КАЖДОГО ТИПА ===")
        
        # Анализ TEXT сущностей
        if 'TEXT' in entity_types:
            print(f"\n📝 TEXT СУЩНОСТИ ({entity_types['TEXT']}):")
            for i, text_entity in enumerate(entity_samples['TEXT']):
                try:
                    text_content = getattr(text_entity.dxf, 'text', 'NO_TEXT')
                    text_x = getattr(text_entity.dxf, 'insert', (0, 0))[0] if hasattr(text_entity.dxf, 'insert') else 'NO_X'
                    text_y = getattr(text_entity.dxf, 'insert', (0, 0))[1] if hasattr(text_entity.dxf, 'insert') else 'NO_Y'
                    text_height = getattr(text_entity.dxf, 'height', 'NO_HEIGHT')
                    text_layer = getattr(text_entity.dxf, 'layer', 'NO_LAYER')
                    
                    print(f"  TEXT {i+1}: '{text_content}' at ({text_x}, {text_y}), height={text_height}, layer={text_layer}")
                except Exception as e:
                    print(f"  TEXT {i+1}: Ошибка анализа: {e}")
        
        # Анализ SPLINE сущностей 
        if 'SPLINE' in entity_types:
            print(f"\n🔄 SPLINE СУЩНОСТИ ({entity_types['SPLINE']}):")
            for i, spline_entity in enumerate(entity_samples['SPLINE'][:2]):  # Только первые 2
                try:
                    control_points = spline_entity.control_points
                    if control_points and len(control_points) > 0:
                        x_coords = []
                        y_coords = []
                        for cp in control_points:
                            if hasattr(cp, 'x') and hasattr(cp, 'y'):
                                x_coords.append(cp.x)
                                y_coords.append(cp.y)
                        
                        if x_coords and y_coords:
                            min_x, max_x = min(x_coords), max(x_coords)
                            min_y, max_y = min(y_coords), max(y_coords)
                            layer = getattr(spline_entity.dxf, 'layer', 'NO_LAYER')
                            
                            print(f"  SPLINE {i+1}: bounds X[{min_x:.1f}, {max_x:.1f}] Y[{min_y:.1f}, {max_y:.1f}], layer={layer}")
                except Exception as e:
                    print(f"  SPLINE {i+1}: Ошибка анализа: {e}")
        
        # Анализ других типов
        for entity_type in sorted(entity_types.keys()):
            if entity_type not in ['TEXT', 'SPLINE']:
                print(f"\n🔧 {entity_type} СУЩНОСТИ ({entity_types[entity_type]}):")
                for i, entity in enumerate(entity_samples[entity_type]):
                    try:
                        layer = getattr(entity.dxf, 'layer', 'NO_LAYER')
                        print(f"  {entity_type} {i+1}: layer={layer}")
                        
                        # Дополнительная информация в зависимости от типа
                        if entity_type == 'LWPOLYLINE':
                            points = list(entity.get_points())
                            if points:
                                x_coords = [p[0] for p in points]
                                y_coords = [p[1] for p in points]
                                min_x, max_x = min(x_coords), max(x_coords)
                                min_y, max_y = min(y_coords), max(y_coords)
                                print(f"    bounds X[{min_x:.1f}, {max_x:.1f}] Y[{min_y:.1f}, {max_y:.1f}]")
                        elif hasattr(entity.dxf, 'insert'):
                            insert_point = entity.dxf.insert
                            print(f"    position: ({insert_point[0]:.1f}, {insert_point[1]:.1f})")
                    except Exception as e:
                        print(f"  {entity_type} {i+1}: Ошибка анализа: {e}")
        
        print("\n=== ПРОВЕРКА КООРДИНАТ ===")
        
        # Собираем все координаты для проверки общих границ
        all_x = []
        all_y = []
        
        for entity in msp:
            try:
                if entity.dxftype() == 'SPLINE':
                    control_points = entity.control_points
                    if control_points:
                        for cp in control_points:
                            if hasattr(cp, 'x') and hasattr(cp, 'y'):
                                all_x.append(cp.x)
                                all_y.append(cp.y)
                elif entity.dxftype() == 'LWPOLYLINE':
                    for point in entity.get_points():
                        all_x.append(point[0])
                        all_y.append(point[1])
                elif entity.dxftype() == 'TEXT':
                    if hasattr(entity.dxf, 'insert'):
                        insert_point = entity.dxf.insert
                        all_x.append(insert_point[0])
                        all_y.append(insert_point[1])
            except Exception as e:
                print(f"Ошибка обработки {entity.dxftype()}: {e}")
        
        if all_x and all_y:
            min_x, max_x = min(all_x), max(all_x)
            min_y, max_y = min(all_y), max(all_y)
            
            print(f"Общие границы всех сущностей: X[{min_x:.1f}, {max_x:.1f}] Y[{min_y:.1f}, {max_y:.1f}]")
            print(f"Размер: {max_x - min_x:.1f} x {max_y - min_y:.1f}")
            
            # Ожидаемые границы листа
            expected_width = 1400  # 140см
            expected_height = 2000  # 200см
            
            if max_x > expected_width or max_y > expected_height or min_x < 0 or min_y < 0:
                print(f"⚠️  КООРДИНАТЫ ВЫХОДЯТ ЗА ГРАНИЦЫ ЛИСТА!")
                print(f"   Ожидаемые границы: X[0, {expected_width}] Y[0, {expected_height}]")
                if min_x < 0:
                    print(f"   Отрицательные X: {min_x:.1f}")
                if min_y < 0:
                    print(f"   Отрицательные Y: {min_y:.1f}")
                if max_x > expected_width:
                    print(f"   Превышение по X: {max_x:.1f} > {expected_width}")
                if max_y > expected_height:
                    print(f"   Превышение по Y: {max_y:.1f} > {expected_height}")
            else:
                print("✅ Все координаты в пределах листа")
        
        return entity_types
        
    except Exception as e:
        print(f"Ошибка анализа DXF файла: {e}")
        return None

if __name__ == "__main__":
    result = analyze_all_dxf_entity_types()
    if result:
        print(f"\nВсего типов сущностей: {len(result)}")
        print("Анализ завершен.")