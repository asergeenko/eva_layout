#!/usr/bin/env python3
"""
Проверка несоответствия ключей между original_dxf_data_map и placed_polygons.
"""

def debug_key_mismatch():
    """Простая проверка проблемы с ключами."""
    print("=== ДИАГНОСТИКА ПРОБЛЕМЫ КЛЮЧЕЙ ===")
    
    # Симулируем проблему
    display_name = "Лодка АГУЛ 270_2.dxf"  # Как хранится в original_dxf_data_map
    file_name = "Лодка АГУЛ 270_2.dxf"     # Как приходит из placed_polygons
    
    print(f"Display name: '{display_name}'")
    print(f"File name:    '{file_name}'")
    print(f"Ключи совпадают: {display_name == file_name}")
    
    # Проверим с различными вариантами
    test_cases = [
        ("Лодка АГУЛ 270_2.dxf", "Лодка АГУЛ 270_2.dxf"),
        ("../Лодка АГУЛ 270_2.dxf", "Лодка АГУЛ 270_2.dxf"),
        ("uploads/Лодка АГУЛ 270_2.dxf", "Лодка АГУЛ 270_2.dxf"),
        ("Лодка АГУЛ 270_2.dxf", "../Лодка АГУЛ 270_2.dxf"),
    ]
    
    print("\nПроверка различных комбинаций:")
    for display, filename in test_cases:
        match = display == filename
        print(f"  '{display}' == '{filename}': {match}")
        
        # Проверим нормализацию путей
        import os
        display_norm = os.path.basename(display)
        filename_norm = os.path.basename(filename)
        norm_match = display_norm == filename_norm
        print(f"    После basename: '{display_norm}' == '{filename_norm}': {norm_match}")
    
    return True

if __name__ == "__main__":
    debug_key_mismatch()