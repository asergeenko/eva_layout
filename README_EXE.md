# Eva Layout Optimizer - Создание EXE версии

Это руководство поможет создать исполняемый EXE файл для Windows из приложения Eva Layout Optimizer.

## Требования

- Python 3.8+ установленный в системе
- Все зависимости из `requirements.txt`
- PyInstaller (автоматически устанавливается)

## Способы сборки

### 1. Автоматическая сборка (Windows)

Для Windows пользователей - просто запустите:

```batch
build_exe.bat
```

### 2. Автоматическая сборка (любая ОС)

```bash
python build_exe.py
```

### 3. Ручная сборка

```bash
# Установка зависимостей
pip install -r requirements.txt

# Сборка
pyinstaller --clean eva_layout.spec
```

## Результат сборки

После успешной сборки:

- EXE файл: `dist/EvaLayoutOptimizer/EvaLayoutOptimizer.exe`
- Папка для распространения: `dist/EvaLayoutOptimizer/`

## Запуск EXE приложения

1. Скопируйте всю папку `EvaLayoutOptimizer` на целевой компьютер
2. Запустите `EvaLayoutOptimizer.exe`
3. Приложение автоматически откроет браузер с интерфейсом

## Структура файлов

```
eva_layout.spec         # Конфигурация PyInstaller
run_streamlit.py        # Лаунчер для Streamlit
build_exe.py           # Скрипт сборки (Python)
build_exe.bat          # Скрипт сборки (Windows)
requirements.txt       # Зависимости (обновлен для PyInstaller)
```

## Настройки PyInstaller

В файле `eva_layout.spec`:

- **Основной файл**: `streamlit_demo.py`
- **Имя EXE**: `EvaLayoutOptimizer.exe`
- **Тип**: Консольное приложение (для логов)
- **Иконка**: `logo.png` (если присутствует)
- **Включены**: Все необходимые модули и данные

## Устранение проблем

### Ошибка "модуль не найден"
Добавьте отсутствующий модуль в `hiddenimports` в `eva_layout.spec`

### Ошибка "файл не найден"
Добавьте файл в `datas` в `eva_layout.spec`

### Приложение не запускается
Проверьте консольный вывод - запустите EXE из командной строки

### Медленный запуск
Это нормально для PyInstaller - первый запуск может занять 10-30 секунд

## Дополнительные опции

### Создание одного файла (медленнее, но проще распространять)

Измените в `eva_layout.spec`:

```python
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,    # Добавить эту строку
    a.zipfiles,    # Добавить эту строку
    a.datas,       # Добавить эту строку
    [],
    name='EvaLayoutOptimizer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    onefile=True,  # Добавить эту строку
)
```

### Убрать консольное окно

Измените в `eva_layout.spec`:

```python
console=False,  # Вместо True
```

**Внимание**: Без консоли труднее диагностировать проблемы!

## Тестирование

После сборки протестируйте:

1. Запуск EXE файла
2. Загрузку Excel файла
3. Загрузку DXF файлов
4. Выполнение оптимизации
5. Скачивание результатов

## Размер файлов

Ожидаемый размер:
- Папка `EvaLayoutOptimizer`: ~150-300 MB
- Одиночный EXE файл: ~200-400 MB

Это нормально для приложений с NumPy, Pandas и Matplotlib.