#!/usr/bin/env python3
import ezdxf

def analyze_dxf_structure(dxf_path):
    """Проанализировать структуру DXF файла."""
    
    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()
    
    print(f"Анализ структуры файла: {dxf_path}")
    print("="*60)
    
    # Слои
    print("\nСлои в файле:")
    for layer in doc.layers:
        print(f"  - {layer.dxf.name} (цвет: {layer.dxf.color})")
    
    # Типы объектов
    entity_types = {}
    layer_stats = {}
    
    print("\nОбъекты в модельном пространстве:")
    for entity in msp:
        entity_type = entity.dxftype()
        layer_name = getattr(entity.dxf, 'layer', 'Unknown')
        
        # Статистика по типам
        entity_types[entity_type] = entity_types.get(entity_type, 0) + 1
        
        # Статистика по слоям
        if layer_name not in layer_stats:
            layer_stats[layer_name] = {}
        layer_stats[layer_name][entity_type] = layer_stats[layer_name].get(entity_type, 0) + 1
        
        # Подробности для первых 20 объектов
        if sum(entity_types.values()) <= 20:
            print(f"  {entity_type} на слое '{layer_name}'")
            if hasattr(entity.dxf, 'color'):
                print(f"    цвет: {entity.dxf.color}")
            
            # Для полилиний - показать точки
            if entity_type in ['POLYLINE', 'LWPOLYLINE']:
                try:
                    if entity_type == 'POLYLINE':
                        points = [(v.dxf.location.x, v.dxf.location.y) for v in entity.vertices]
                    else:  # LWPOLYLINE
                        points = [(p[0], p[1]) for p in entity.get_points()]
                    print(f"    точек: {len(points)}")
                    if points:
                        print(f"    первая точка: ({points[0][0]:.2f}, {points[0][1]:.2f})")
                except Exception as e:
                    print(f"    ошибка чтения точек: {e}")
    
    print(f"\nИтого объектов: {sum(entity_types.values())}")
    print("\nСтатистика по типам объектов:")
    for etype, count in sorted(entity_types.items()):
        print(f"  {etype}: {count}")
    
    print("\nСтатистика по слоям:")
    for layer_name, types in sorted(layer_stats.items()):
        print(f"  Слой '{layer_name}':")
        for etype, count in sorted(types.items()):
            print(f"    {etype}: {count}")

if __name__ == "__main__":
    analyze_dxf_structure("/home/sasha/proj/2025/eva_layout/200_140_1_black.dxf")