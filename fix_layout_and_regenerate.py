#!/usr/bin/env python3
"""
Исправляет раскрой и генерирует новый корректный DXF файл.
"""

import os
from layout_optimizer import (
    parse_dxf_complete, 
    bin_packing, 
    save_dxf_layout_complete
)

def fix_and_regenerate_layout():
    """Заново создает правильный раскрой."""
    print("=== ИСПРАВЛЕНИЕ И ПЕРЕГЕНЕРАЦИЯ РАСКРОЯ ===")
    
    # Используем те же файлы, что и в предыдущем тесте
    source_files = [
        "/home/sasha/proj/2025/eva_layout/dxf_samples/Лодка Азимут Эверест 385/2.dxf",
        "/home/sasha/proj/2025/eva_layout/dxf_samples/Лодка АГУЛ 270/2.dxf", 
        "/home/sasha/proj/2025/eva_layout/dxf_samples/TOYOTA COROLLA VERSO/2.dxf",
        "/home/sasha/proj/2025/eva_layout/dxf_samples/ДЕКА KUGOO M4 PRO JILONG/1.dxf"
    ]
    
    # Проверяем существование файлов
    existing_files = []
    for file_path in source_files:
        if os.path.exists(file_path):
            existing_files.append(file_path)
            print(f"✅ {os.path.basename(file_path)}")
        else:
            print(f"❌ {os.path.basename(file_path)} - не найден")
    
    if not existing_files:
        print("❌ Нет доступных исходных файлов!")
        return False
    
    print(f"\\n📊 Парсим {len(existing_files)} файлов...")
    
    # Парсим файлы
    polygons = []
    original_dxf_data_map = {}
    
    for file_path in existing_files:
        print(f"\\n📖 Парсим: {os.path.basename(file_path)}")
        try:
            with open(file_path, 'rb') as f:
                parsed_data = parse_dxf_complete(f, verbose=False)
            
            if parsed_data['combined_polygon']:
                file_name = os.path.basename(file_path)
                color = "черный"
                
                polygon_tuple = (parsed_data['combined_polygon'], file_name, color)
                polygons.append(polygon_tuple)
                original_dxf_data_map[file_name] = parsed_data
                
                bounds = parsed_data['combined_polygon'].bounds
                print(f"  ✅ Bounds: ({bounds[0]:.1f}, {bounds[1]:.1f}, {bounds[2]:.1f}, {bounds[3]:.1f})")
                print(f"  📊 Entities: {len(parsed_data['original_entities'])}")
                
                if parsed_data.get('real_spline_bounds'):
                    print(f"  📊 Real SPLINE bounds: {parsed_data['real_spline_bounds']}")
            else:
                print(f"  ❌ Не удалось создать полигон")
                
        except Exception as e:
            print(f"  ❌ Ошибка: {e}")
    
    if not polygons:
        print("❌ Нет полигонов для раскроя!")
        return False
    
    print(f"\\n🔄 Запускаем bin packing для {len(polygons)} полигонов...")
    
    # ВАЖНО: Правильный размер листа - 200x140 см = 2000x1400 мм
    sheet_size = (200.0, 140.0)  # см
    
    try:
        placed_elements, rejected_elements = bin_packing(
            polygons, 
            sheet_size, 
            max_attempts=1000, 
            verbose=True
        )
        
        print(f"\\n📊 Результат bin packing:")
        print(f"  Размещено: {len(placed_elements)} элементов")
        print(f"  Отклонено: {len(rejected_elements)} элементов")
        
        if not placed_elements:
            print("❌ Нет размещенных элементов!")
            return False
        
        # Показываем детали размещения
        for i, element in enumerate(placed_elements):
            if len(element) >= 5:
                polygon, x_offset, y_offset, rotation_angle, file_name = element[:5]
                final_bounds = polygon.bounds
                print(f"  {i+1}. {file_name}:")
                print(f"     Offset: ({x_offset:.1f}, {y_offset:.1f}), Rotation: {rotation_angle:.1f}°")
                print(f"     Final bounds: ({final_bounds[0]:.1f}, {final_bounds[1]:.1f}, {final_bounds[2]:.1f}, {final_bounds[3]:.1f})")
                
                # Проверяем, что элемент в пределах листа
                sheet_mm = (sheet_size[0] * 10, sheet_size[1] * 10)  # см -> мм
                in_bounds = (
                    final_bounds[0] >= -1 and final_bounds[1] >= -1 and
                    final_bounds[2] <= sheet_mm[0] + 1 and final_bounds[3] <= sheet_mm[1] + 1
                )
                print(f"     В пределах листа {sheet_mm}: {'✅' if in_bounds else '❌'}")
        
        # Сохраняем результат
        output_path = "/home/sasha/proj/2025/eva_layout/200_140_1_black.dxf"
        print(f"\\n💾 Сохраняем исправленный результат: {output_path}")
        
        save_dxf_layout_complete(placed_elements, sheet_size, output_path, original_dxf_data_map)
        
        print(f"✅ Исправленный файл сохранен!")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка bin packing: {e}")
        return False

if __name__ == "__main__":
    print("🔧 Исправление раскроя и генерация корректного DXF")
    print("=" * 60)
    
    success = fix_and_regenerate_layout()
    
    print("\\n" + "=" * 60)
    if success:
        print("✅ РАСКРОЙ ИСПРАВЛЕН И ПЕРЕГЕНЕРИРОВАН!")
        print("🎯 Теперь запустите layout_optimizer.py для обновления visualization.png")
    else:
        print("❌ ОШИБКА ПРИ ИСПРАВЛЕНИИ РАСКРОЯ")