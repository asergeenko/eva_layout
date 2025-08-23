#!/usr/bin/env python3

import ezdxf
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from shapely.geometry import Polygon
import os

def check_inter_file_overlaps():
    """Проверяем пересечения только МЕЖДУ разными файлами"""
    
    print("=== ПРОВЕРКА ПЕРЕСЕЧЕНИЙ МЕЖДУ ФАЙЛАМИ ===")
    
    dxf_file = "200_140_1_black.dxf"
    
    if not os.path.exists(dxf_file):
        print(f"❌ Файл {dxf_file} не найден")
        return False
    
    try:
        doc = ezdxf.readfile(dxf_file)
        msp = doc.modelspace()
        
        # Группируем элементы по исходным файлам
        files_data = {}
        
        for entity in msp:
            if entity.dxftype() == 'SPLINE':
                layer = getattr(entity.dxf, 'layer', '0')
                
                # Извлекаем номер исходного файла из названия слоя
                # Формат: "dxf_samples_TANK_300_1_layer 1" -> файл "1"
                source_file = "unknown"
                if "dxf_samples_TANK_300_" in layer:
                    parts = layer.split("_")
                    for i, part in enumerate(parts):
                        if part == "300" and i + 1 < len(parts):
                            source_file = parts[i + 1]
                            break
                
                if source_file not in files_data:
                    files_data[source_file] = []
                
                # Извлекаем control points и создаем polygon
                if hasattr(entity, 'control_points') and entity.control_points:
                    points = []
                    for cp in entity.control_points:
                        if hasattr(cp, 'x') and hasattr(cp, 'y'):
                            points.append((cp.x, cp.y))
                        elif len(cp) >= 2:
                            points.append((float(cp[0]), float(cp[1])))
                    
                    if len(points) >= 3:
                        try:
                            polygon = Polygon(points)
                            if polygon.is_valid:
                                files_data[source_file].append({
                                    'polygon': polygon,
                                    'layer': layer,
                                    'bounds': polygon.bounds,
                                    'area': polygon.area
                                })
                        except Exception as e:
                            pass
        
        print(f"\n📊 ФАЙЛЫ НА ЛИСТЕ:")
        total_elements = 0
        for file_name, elements in files_data.items():
            if elements:
                total_area = sum(elem['area'] for elem in elements)
                print(f"   Файл {file_name}: {len(elements)} элементов, общая площадь: {total_area:.0f} мм²")
                total_elements += len(elements)
        print(f"   Всего: {total_elements} элементов из {len(files_data)} файлов")
        
        # Проверяем пересечения ТОЛЬКО между разными файлами
        print(f"\n🔍 ПРОВЕРКА ПЕРЕСЕЧЕНИЙ МЕЖДУ ФАЙЛАМИ:")
        
        inter_file_overlaps = []
        files_list = [f for f in files_data.keys() if f != "unknown" and files_data[f]]
        
        for i in range(len(files_list)):
            for j in range(i + 1, len(files_list)):
                file1 = files_list[i]
                file2 = files_list[j]
                
                elements1 = files_data[file1]
                elements2 = files_data[file2]
                
                file_pair_overlaps = []
                
                # Проверяем все элементы файла 1 против всех элементов файла 2
                for elem1 in elements1:
                    for elem2 in elements2:
                        if elem1['polygon'].intersects(elem2['polygon']):
                            intersection = elem1['polygon'].intersection(elem2['polygon'])
                            if hasattr(intersection, 'area') and intersection.area > 1.0:  # минимум 1 мм²
                                file_pair_overlaps.append({
                                    'elem1': elem1,
                                    'elem2': elem2,
                                    'overlap_area': intersection.area,
                                    'intersection': intersection
                                })
                
                if file_pair_overlaps:
                    total_overlap_area = sum(ovl['overlap_area'] for ovl in file_pair_overlaps)
                    print(f"   ❌ ПЕРЕСЕЧЕНИЕ: Файл {file1} ↔ Файл {file2}")
                    print(f"      Найдено {len(file_pair_overlaps)} пересечений, общая площадь: {total_overlap_area:.1f} мм²")
                    inter_file_overlaps.extend(file_pair_overlaps)
                else:
                    print(f"   ✅ OK: Файл {file1} ↔ Файл {file2}")
        
        # Создаем визуализацию
        create_inter_file_visualization(files_data, inter_file_overlaps)
        
        print(f"\n📊 ФИНАЛЬНЫЙ РЕЗУЛЬТАТ:")
        if inter_file_overlaps:
            total_overlap_area = sum(ovl['overlap_area'] for ovl in inter_file_overlaps)
            print(f"   ❌ НАЙДЕНО {len(inter_file_overlaps)} ПЕРЕСЕЧЕНИЙ МЕЖДУ ФАЙЛАМИ!")
            print(f"   📐 Общая площадь пересечений: {total_overlap_area:.1f} мм²")
            print(f"   ⚠️  Требуется увеличение buffer или корректировка алгоритма")
            return False
        else:
            print(f"   ✅ ПЕРЕСЕЧЕНИЙ МЕЖДУ ФАЙЛАМИ НЕ НАЙДЕНО!")
            print(f"   🎉 Алгоритм работает корректно - файлы не пересекаются")
            return True
            
    except Exception as e:
        print(f"❌ Ошибка анализа: {e}")
        return False

def create_inter_file_visualization(files_data, overlaps):
    """Создает визуализацию с выделением пересечений между файлами"""
    
    fig, ax = plt.subplots(1, 1, figsize=(18, 14))
    ax.set_title("Inter-file overlap analysis (only between different source files)", 
                fontsize=16, fontweight='bold')
    
    colors = ['red', 'blue', 'green', 'orange', 'purple', 'brown', 'pink', 'gray']
    color_idx = 0
    
    # Рисуем элементы по файлам с разными цветами
    legend_elements = []
    for file_name, elements in files_data.items():
        if elements and file_name != "unknown":
            color = colors[color_idx % len(colors)]
            color_idx += 1
            
            # Находим bounding box всего файла
            all_bounds = [elem['bounds'] for elem in elements]
            file_min_x = min(b[0] for b in all_bounds)
            file_min_y = min(b[1] for b in all_bounds)
            file_max_x = max(b[2] for b in all_bounds)
            file_max_y = max(b[3] for b in all_bounds)
            
            # Рисуем общую рамку файла
            file_width = file_max_x - file_min_x
            file_height = file_max_y - file_min_y
            
            file_rect = patches.Rectangle(
                (file_min_x, file_min_y),
                file_width, file_height,
                linewidth=3,
                edgecolor=color,
                facecolor=color,
                alpha=0.2,
                label=f'File {file_name}'
            )
            ax.add_patch(file_rect)
            
            # Центральная точка файла
            center_x = file_min_x + file_width/2
            center_y = file_min_y + file_height/2
            ax.text(center_x, center_y, f'FILE\n{file_name}', 
                   fontsize=14, fontweight='bold', 
                   ha='center', va='center', color=color,
                   bbox=dict(boxstyle="round,pad=0.3", facecolor='white', alpha=0.8))
    
    # Выделяем области пересечений красными крестами
    for overlap in overlaps:
        intersection = overlap['intersection']
        if hasattr(intersection, 'bounds'):
            bounds = intersection.bounds
            center_x = (bounds[0] + bounds[2]) / 2
            center_y = (bounds[1] + bounds[3]) / 2
            
            # Красный крест в области пересечения
            ax.plot(center_x, center_y, 'r+', markersize=20, markeredgewidth=4)
            ax.text(center_x, center_y + 50, f'{overlap["overlap_area"]:.0f}mm²', 
                   fontsize=10, ha='center', va='bottom', color='red', fontweight='bold',
                   bbox=dict(boxstyle="round,pad=0.2", facecolor='yellow', alpha=0.8))
    
    # Границы листа (200x140 см = 2000x1400 мм)
    sheet_rect = patches.Rectangle((0, 0), 2000, 1400, 
                                 linewidth=4, edgecolor='black', 
                                 facecolor='none', linestyle='-')
    ax.add_patch(sheet_rect)
    
    ax.set_xlim(-200, 2200)
    ax.set_ylim(-200, 1600)
    ax.set_aspect('equal')
    ax.grid(True, alpha=0.3)
    ax.legend(loc='upper right')
    
    # Добавляем текст о результатах
    if overlaps:
        ax.text(1000, -100, f"❌ FOUND {len(overlaps)} INTER-FILE OVERLAPS", 
               fontsize=16, fontweight='bold', ha='center', color='red')
    else:
        ax.text(1000, -100, f"✅ NO INTER-FILE OVERLAPS", 
               fontsize=16, fontweight='bold', ha='center', color='green')
    
    plt.tight_layout()
    plt.savefig('autodesk.png', dpi=150, bbox_inches='tight')
    print(f"   📊 Визуализация сохранена: autodesk.png")

def main():
    """Основная функция проверки"""
    
    print("🔍 ПРОВЕРКА ПЕРЕСЕЧЕНИЙ МЕЖДУ РАЗНЫМИ ФАЙЛАМИ")
    print("(пересечения внутри одного файла - нормальны)")
    
    success = check_inter_file_overlaps()
    
    if success:
        print(f"\n🎉 УСПЕХ! ПЕРЕСЕЧЕНИЙ МЕЖДУ ФАЙЛАМИ НЕТ!")
        print(f"✅ Система работает корректно")
        print(f"📁 Проверьте autodesk.png для визуального подтверждения")
    else:
        print(f"\n❌ ПРОБЛЕМА: ЕСТЬ ПЕРЕСЕЧЕНИЯ МЕЖДУ ФАЙЛАМИ")
        print(f"⚠️  Требуется увеличение буферов или настройка алгоритма")
    
    return success

if __name__ == "__main__":
    main()