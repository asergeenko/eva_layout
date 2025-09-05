"""
Тест функции прогресса в bin_packing_with_inventory.
"""

import sys
import os
from shapely.geometry import Polygon

# Добавляем корневую директорию в путь для импорта модулей
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from layout_optimizer import (
    bin_packing_with_inventory,
)


class TestProgressCallback:
    """Тесты прогресса оптимизации."""
    
    def test_progress_callback_called(self):
        """
        Тест: проверяем что прогресс-колбек вызывается.
        """
        # Настройка листов
        available_sheets = [
            {
                "name": "Лист 100x100 чёрный",
                "width": 100,
                "height": 100,
                "color": "чёрный", 
                "count": 5,
                "used": 0
            }
        ]
        
        # Создаем полигоны
        polygons = []
        
        # Priority 1 полигоны (создадут листы)
        for i in range(5):
            polygon = Polygon([(0, 0), (300, 0), (300, 300), (0, 300)])  # 30x30 мм
            polygons.append((
                polygon,
                f"priority1_file_{i}.dxf",
                "чёрный",
                f"excel_order_{i}",
                1  # Priority 1
            ))
        

        
        # Отслеживание вызовов прогресса
        progress_calls = []
        
        def track_progress(percent, status):
            progress_calls.append((percent, status))
            print(f"Progress: {percent}% - {status}")
        
        # Тестируем с колбеком
        layouts, unplaced = bin_packing_with_inventory(
            polygons,
            available_sheets,
            verbose=False,
            progress_callback=track_progress
        )
        
        # Проверки
        assert len(layouts) > 0, "Должны быть созданы листы"
        assert len(progress_calls) > 0, "Колбек прогресса должен был вызываться"
        
        # Проверяем что есть финальный вызов с 100%
        final_call = progress_calls[-1]
        assert final_call[0] == 100, f"Финальный прогресс должен быть 100%, получен {final_call[0]}"
        assert "Завершено" in final_call[1], f"Финальное сообщение должно содержать 'Завершено': {final_call[1]}"
        
        # Проверяем что прогресс увеличивается
        percentages = [call[0] for call in progress_calls]
        for i in range(1, len(percentages)):
            assert percentages[i] >= percentages[i-1], f"Прогресс должен увеличиваться: {percentages}"
        
        print(f"✅ Колбек прогресса вызван {len(progress_calls)} раз")
        print(f"Диапазон прогресса: {min(percentages)}% - {max(percentages)}%")
        
    def test_progress_callback_with_priority2(self):
        """
        Тест: проверяем прогресс с файлами приоритета 2.
        """
        # Настройка листов
        available_sheets = [
            {
                "name": "Лист 100x100 чёрный",
                "width": 100,
                "height": 100,
                "color": "чёрный", 
                "count": 2,
                "used": 0
            }
        ]
        
        # Создаем полигоны
        polygons = []
        
        # Priority 1 полигоны
        for i in range(2):
            polygon = Polygon([(0, 0), (300, 0), (300, 300), (0, 300)])
            polygons.append((
                polygon,
                f"priority1_file_{i}.dxf",
                "чёрный",
                f"excel_order_{i}",
                1  # Priority 1
            ))
        
        # Priority 2 полигоны
        for i in range(2):
            polygon = Polygon([(0, 0), (200, 0), (200, 200), (0, 200)])
            polygons.append((
                polygon,
                f"priority2_file_{i}.dxf",
                "чёрный",
                f"group_priority2_{i}",
                2  # Priority 2
            ))
        

        # Отслеживание вызовов прогресса
        progress_calls = []
        
        def track_progress(percent, status):
            progress_calls.append((percent, status))
            print(f"Progress: {percent}% - {status}")
        
        # Тестируем с колбеком
        layouts, unplaced = bin_packing_with_inventory(
            polygons,
            available_sheets,
            verbose=False,
            progress_callback=track_progress
        )
        
        # Проверки
        assert len(layouts) > 0, "Должны быть созданы листы"
        assert len(progress_calls) > 0, "Колбек прогресса должен был вызываться"
        
        # Проверяем что есть сообщения о priority 2
        priority2_messages = [call[1] for call in progress_calls if "приоритета 2" in call[1]]
        if len([p for p in polygons if len(p) >= 5 and p[4] == 2]) > 0:  # If there are priority 2 files
            assert len(priority2_messages) > 0, "Должно быть сообщение о приоритете 2"
        
        # Проверяем финальный прогресс
        final_call = progress_calls[-1]
        assert final_call[0] == 100, "Финальный прогресс должен быть 100%"
        
        print(f"✅ Прогресс с priority 2: {len(progress_calls)} вызовов")
        if priority2_messages:
            print(f"Сообщения о priority 2: {priority2_messages}")
            
    def test_no_progress_callback(self):
        """
        Тест: проверяем что функция работает без колбека прогресса.
        """
        # Настройка листов
        available_sheets = [
            {
                "name": "Лист 100x100 чёрный",
                "width": 100,
                "height": 100,
                "color": "чёрный", 
                "count": 2,
                "used": 0
            }
        ]
        
        # Создаем полигоны
        polygons = []
        
        # Priority 1 полигоны
        for i in range(2):
            polygon = Polygon([(0, 0), (300, 0), (300, 300), (0, 300)])
            polygons.append((
                polygon,
                f"priority1_file_{i}.dxf",
                "чёрный",
                f"excel_order_{i}",
                1  # Priority 1
            ))
        

        # Тестируем БЕЗ колбека
        layouts, unplaced = bin_packing_with_inventory(
            polygons,
            available_sheets,
            verbose=False
            # progress_callback НЕ передается
        )
        
        # Проверки - должно работать нормально
        assert len(layouts) > 0, "Должны быть созданы листы"
        
        print("✅ Функция работает без колбека прогресса")