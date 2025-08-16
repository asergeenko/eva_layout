#!/usr/bin/env python3
"""
Создает точную копию test_minimal.dxf, но с реальными SPLINE элементами.
"""

import ezdxf
import os
from layout_optimizer import parse_dxf_complete

def create_exact_spline_copy():
    """Создает DXF с SPLINE элементами в точных позициях test_minimal.dxf."""
    print("=== СОЗДАНИЕ ТОЧНОЙ КОПИИ С SPLINE ===")
    
    # Определяем точные позиции из test_minimal.dxf
    target_positions = {
        "azimut": {
            "bounds": (50, 50, 450, 1350),  # Левый прямоугольник
            "source_file": "/home/sasha/proj/2025/eva_layout/dxf_samples/Лодка Азимут Эверест 385/2.dxf"
        },
        "agul": {
            "bounds": (700, 50, 1300, 800),  # Правый нижний
            "source_file": "/home/sasha/proj/2025/eva_layout/dxf_samples/Лодка АГУЛ 270/2.dxf"
        }
    }
    
    # Создаем новый DXF документ
    doc = ezdxf.new('R2010')
    doc.header['$INSUNITS'] = 4  # миллиметры
    doc.header['$LUNITS'] = 2    # десятичные единицы
    
    msp = doc.modelspace()
    
    # Добавляем границы листа (точно как в test_minimal.dxf)
    sheet_corners = [(0, 0), (2000, 0), (2000, 1400), (0, 1400), (0, 0)]
    msp.add_lwpolyline(sheet_corners, dxfattribs={"layer": "SHEET_BOUNDARY", "color": 1})
    
    # Обрабатываем каждый файл
    for name, config in target_positions.items():
        print(f"\\n📖 Обрабатываем {name}: {os.path.basename(config['source_file'])}")
        
        if not os.path.exists(config['source_file']):
            print(f"  ❌ Файл не найден")
            continue
        
        try:
            # Парсим исходный файл
            with open(config['source_file'], 'rb') as f:
                parsed_data = parse_dxf_complete(f, verbose=False)
            
            if not parsed_data['original_entities']:
                print(f"  ❌ Нет элементов для обработки")
                continue
            
            # Получаем bounds исходных SPLINE элементов
            spline_entities = [e for e in parsed_data['original_entities'] if e['type'] == 'SPLINE']
            print(f"  📊 Найдено {len(spline_entities)} SPLINE элементов")
            
            if not spline_entities:
                continue
            
            # Вычисляем исходные bounds всех SPLINE
            all_x = []
            all_y = []
            
            for entity_data in spline_entities:
                entity = entity_data['entity']
                control_points = entity.control_points
                if control_points:
                    for cp in control_points:
                        if hasattr(cp, 'x') and hasattr(cp, 'y'):
                            all_x.append(cp.x)
                            all_y.append(cp.y)
                        elif len(cp) >= 2:
                            all_x.append(float(cp[0]))
                            all_y.append(float(cp[1]))
            
            if not all_x or not all_y:
                print(f"  ❌ Нет координат SPLINE")
                continue
            
            original_bounds = (min(all_x), min(all_y), max(all_x), max(all_y))
            target_bounds = config['bounds']
            
            print(f"  📐 Исходные bounds: {original_bounds}")
            print(f"  🎯 Целевые bounds: {target_bounds}")
            
            # Вычисляем трансформацию
            orig_width = original_bounds[2] - original_bounds[0]
            orig_height = original_bounds[3] - original_bounds[1]
            target_width = target_bounds[2] - target_bounds[0]
            target_height = target_bounds[3] - target_bounds[1]
            
            # Простое масштабирование и смещение (без поворота)
            scale_x = target_width / orig_width if orig_width > 0 else 1.0
            scale_y = target_height / orig_height if orig_height > 0 else 1.0
            
            # Используем одинаковый масштаб для сохранения пропорций
            scale = min(scale_x, scale_y)
            
            # Центрируем в целевой области
            scaled_width = orig_width * scale
            scaled_height = orig_height * scale
            center_offset_x = (target_width - scaled_width) / 2
            center_offset_y = (target_height - scaled_height) / 2
            
            offset_x = target_bounds[0] - original_bounds[0] * scale + center_offset_x
            offset_y = target_bounds[1] - original_bounds[1] * scale + center_offset_y
            
            print(f"  🔄 Трансформация: scale={scale:.3f}, offset=({offset_x:.1f}, {offset_y:.1f})")
            
            # Применяем трансформацию к каждому SPLINE
            transformed_count = 0
            for entity_data in spline_entities:
                try:
                    # Клонируем элемент
                    new_entity = entity_data['entity'].copy()
                    
                    # Трансформируем контрольные точки
                    control_points = new_entity.control_points
                    if control_points:
                        transformed_points = []
                        
                        for cp in control_points:
                            if hasattr(cp, 'x') and hasattr(cp, 'y'):
                                x, y = cp.x, cp.y
                                z = getattr(cp, 'z', 0.0)
                            elif len(cp) >= 2:
                                x, y = float(cp[0]), float(cp[1])
                                z = float(cp[2]) if len(cp) > 2 else 0.0
                            else:
                                continue
                            
                            # Применяем простую трансформацию
                            new_x = (x - original_bounds[0]) * scale + target_bounds[0] + center_offset_x
                            new_y = (y - original_bounds[1]) * scale + target_bounds[1] + center_offset_y
                            
                            from ezdxf.math import Vec3
                            transformed_points.append(Vec3(new_x, new_y, z))
                        
                        if transformed_points:
                            new_entity.control_points = transformed_points
                            
                            # Устанавливаем слой
                            new_entity.dxf.layer = f"{name}_spline"
                            
                            # Добавляем в документ
                            msp.add_entity(new_entity)
                            transformed_count += 1
                
                except Exception as e:
                    print(f"    ⚠️ Ошибка трансформации: {e}")
            
            print(f"  ✅ Трансформировано {transformed_count} SPLINE элементов")
            
        except Exception as e:
            print(f"  ❌ Ошибка обработки файла: {e}")
    
    # Сохраняем результат
    output_path = "/home/sasha/proj/2025/eva_layout/spline_exact_copy.dxf"
    doc.saveas(output_path)
    
    print(f"\\n✅ Файл создан: {output_path}")
    
    # Проверяем результат
    try:
        check_doc = ezdxf.readfile(output_path)
        check_msp = check_doc.modelspace()
        
        splines = [e for e in check_msp if e.dxftype() == 'SPLINE']
        print(f"📊 SPLINE элементов в результате: {len(splines)}")
        
        if splines:
            # Проверяем bounds всех SPLINE
            all_x = []
            all_y = []
            
            for spline in splines:
                control_points = spline.control_points
                if control_points:
                    for cp in control_points:
                        if hasattr(cp, 'x') and hasattr(cp, 'y'):
                            all_x.append(cp.x)
                            all_y.append(cp.y)
                        elif len(cp) >= 2:
                            all_x.append(float(cp[0]))
                            all_y.append(float(cp[1]))
            
            if all_x and all_y:
                result_bounds = (min(all_x), min(all_y), max(all_x), max(all_y))
                print(f"📊 Итоговые bounds SPLINE: {result_bounds}")
                
                in_bounds = (result_bounds[0] >= 0 and result_bounds[1] >= 0 and 
                           result_bounds[2] <= 2000 and result_bounds[3] <= 1400)
                print(f"📊 В пределах листа: {'✅' if in_bounds else '❌'}")
        
    except Exception as e:
        print(f"⚠️ Ошибка проверки: {e}")
    
    return output_path

if __name__ == "__main__":
    print("🎯 Создание точной копии с SPLINE элементами")
    print("=" * 50)
    
    result = create_exact_spline_copy()
    
    print("\\n" + "=" * 50)
    if result:
        print("✅ ТОЧНАЯ КОПИЯ С SPLINE СОЗДАНА!")
        print("🎯 Проверьте файл spline_exact_copy.dxf в AutoDesk Viewer")
        print("   Ожидается: SPLINE элементы в тех же позициях, что и прямоугольники в test_minimal.dxf")
    else:
        print("❌ ОШИБКА ПРИ СОЗДАНИИ КОПИИ")