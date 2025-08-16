#!/usr/bin/env python3

"""
Быстрая проверка проблемы с IMAGE координатами
"""

import ezdxf

def check_current_dxf():
    """Проверяем текущий DXF файл"""
    
    print("=== АНАЛИЗ ТЕКУЩЕГО DXF ФАЙЛА ===")
    
    dxf_file = "200_140_1_black.dxf"
    
    try:
        doc = ezdxf.readfile(dxf_file)
        msp = doc.modelspace()
        
        # Проверяем все IMAGE сущности
        image_entities = [e for e in msp if e.dxftype() == 'IMAGE']
        print(f"Найдено {len(image_entities)} IMAGE сущностей")
        
        sheet_bounds = (0, 0, 1400, 2000)  # ожидаемые границы листа
        
        for i, img in enumerate(image_entities):
            if hasattr(img.dxf, 'insert'):
                pos = img.dxf.insert
                layer = getattr(img.dxf, 'layer', 'NO_LAYER')
                
                # Проверяем, в границах ли листа
                in_bounds = (sheet_bounds[0] <= pos[0] <= sheet_bounds[2] and 
                           sheet_bounds[1] <= pos[1] <= sheet_bounds[3])
                
                status = "✅" if in_bounds else "❌"
                print(f"  IMAGE {i+1}: {status} ({pos[0]:.1f}, {pos[1]:.1f}) layer={layer}")
                
                if not in_bounds:
                    print(f"    Превышение: X={pos[0]:.1f} (ожидается 0-{sheet_bounds[2]}), Y={pos[1]:.1f} (ожидается 0-{sheet_bounds[3]})")
    
    except Exception as e:
        print(f"Ошибка: {e}")

def check_visualization():
    """Проверяем visualization.png"""
    
    print("\n=== ПРОВЕРКА VISUALIZATION ===")
    
    try:
        import matplotlib.pyplot as plt
        from PIL import Image
        
        # Читаем visualization.png
        img = Image.open("visualization.png")
        print(f"Visualization размер: {img.size}")
        
        # Читаем autodesk.png для сравнения  
        img2 = Image.open("autodesk.png")
        print(f"AutoDesk размер: {img2.size}")
        
        print("\nСравните файлы:")
        print("  visualization.png - показывает правильное размещение")
        print("  autodesk.png - показывает что получается в DXF")
        
    except Exception as e:
        print(f"Ошибка при чтении изображений: {e}")

if __name__ == "__main__":
    check_current_dxf()
    check_visualization()