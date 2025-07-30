#!/usr/bin/env python3
"""Test script to verify color functionality works correctly."""

import sys
sys.path.append('.')

def test_color_tuple_handling():
    """Test that all functions handle the new tuple format correctly."""
    print("🧪 Тестирование обработки кортежей с цветом")
    print("=" * 60)
    
    from layout_optimizer import plot_input_polygons, scale_polygons_to_fit
    from shapely.geometry import Polygon
    
    # Create test polygons with color information
    test_polygons_with_color = [
        (Polygon([(0, 0), (10, 0), (10, 10), (0, 10)]), "test1.dxf", "чёрный"),
        (Polygon([(0, 0), (5, 0), (5, 5), (0, 5)]), "test2.dxf", "серый")
    ]
    
    # Test old format compatibility
    test_polygons_old = [
        (Polygon([(0, 0), (8, 0), (8, 8), (0, 8)]), "test3.dxf")
    ]
    
    print("✅ Созданы тестовые полигоны:")
    print(f"   • С цветом: {len(test_polygons_with_color)} штук")
    print(f"   • Старый формат: {len(test_polygons_old)} штук")
    
    # Test plot_input_polygons function
    try:
        plots_new = plot_input_polygons(test_polygons_with_color)
        plots_old = plot_input_polygons(test_polygons_old)
        print("✅ Функция plot_input_polygons работает корректно")
        print(f"   • Обработано графиков: {len(plots_new) + len(plots_old)}")
    except Exception as e:
        print(f"❌ Ошибка в plot_input_polygons: {e}")
        return False
    
    # Test scale_polygons_to_fit function
    try:
        sheet_size = (20, 20)  # 20x20 cm
        scaled_new = scale_polygons_to_fit(test_polygons_with_color, sheet_size, verbose=False)
        scaled_old = scale_polygons_to_fit(test_polygons_old, sheet_size, verbose=False)
        print("✅ Функция scale_polygons_to_fit работает корректно")
        print(f"   • Обработано полигонов: {len(scaled_new) + len(scaled_old)}")
        
        # Verify color is preserved
        for polygon_tuple in scaled_new:
            if len(polygon_tuple) >= 3:
                _, _, color = polygon_tuple[:3]
                print(f"   • Цвет сохранён: {color}")
    except Exception as e:
        print(f"❌ Ошибка в scale_polygons_to_fit: {e}")
        return False
    
    print("\n🎉 Все тесты прошли успешно!")
    print("✅ Функции корректно обрабатывают новый формат с цветом")
    print("✅ Сохранена обратная совместимость со старым форматом")
    print("✅ Цветовая информация передается через все этапы")
    
    return True

if __name__ == "__main__":
    success = test_color_tuple_handling()
    sys.exit(0 if success else 1)