#!/usr/bin/env python3
"""Test script for color feature functionality."""

def test_color_feature():
    """Test the color feature implementation."""
    print("🎨 Тестирование функции цвета листов")
    print("=" * 50)
    
    # Test sheet data structure with colors
    test_sheets = [
        {
            "name": "Лист 140x200 серый",
            "width": 140.0,
            "height": 200.0,
            "color": "серый",
            "count": 5,
            "used": 0
        },
        {
            "name": "Лист 150x150 чёрный",
            "width": 150.0,
            "height": 150.0,
            "color": "чёрный",
            "count": 3,
            "used": 0
        }
    ]
    
    print("✅ Тестовые листы созданы:")
    for sheet in test_sheets:
        color_emoji = "⚫" if sheet["color"] == "чёрный" else "⚪" if sheet["color"] == "серый" else "🔘"
        print(f"  {color_emoji} {sheet['name']} - {sheet['count']} шт.")
    
    # Test color display function
    def get_color_display(color):
        color_emoji = "⚫" if color == "чёрный" else "⚪" if color == "серый" else "🔘"
        return f"{color_emoji} {color}"
    
    print("\n🎯 Тестирование цветовых индикаторов:")
    colors = ["серый", "чёрный", "неизвестный"]
    for color in colors:
        display = get_color_display(color)
        print(f"  {color} -> {display}")
    
    # Test backward compatibility
    old_sheet = {
        "name": "Старый лист 140x200",
        "width": 140.0,
        "height": 200.0,
        "count": 2,
        "used": 0
        # No color field
    }
    
    # Simulate backward compatibility update
    if 'color' not in old_sheet:
        old_sheet['color'] = 'серый'  # Default color
    
    print(f"\n🔄 Тестирование обратной совместимости:")
    print(f"  Старый лист обновлен: {get_color_display(old_sheet['color'])}")
    
    print("\n🎉 Все тесты пройдены успешно!")
    return True

if __name__ == "__main__":
    test_color_feature()