@echo off
echo === Сборка Eva Layout Optimizer в EXE ===
echo.

REM Проверка наличия Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Ошибка: Python не найден в PATH
    echo Установите Python и добавьте его в PATH
    pause
    exit /b 1
)

REM Установка зависимостей
echo === Установка зависимостей ===
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo ❌ Ошибка установки зависимостей
    pause
    exit /b 1
)

REM Очистка предыдущих сборок
echo === Очистка предыдущих сборок ===
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

REM Сборка с PyInstaller
echo === Сборка с PyInstaller ===
python -m PyInstaller --clean eva_layout.spec
if %errorlevel% neq 0 (
    echo ❌ Ошибка сборки
    pause
    exit /b 1
)

REM Проверка результата
if exist "dist\EvaLayoutOptimizer\EvaLayoutOptimizer.exe" (
    echo.
    echo 🎉 Сборка завершена успешно!
    echo 📁 EXE файл: dist\EvaLayoutOptimizer\EvaLayoutOptimizer.exe
    echo 📦 Папка для распространения: dist\EvaLayoutOptimizer\
    echo.
    echo Для запуска приложения:
    echo   1. Скопируйте всю папку 'EvaLayoutOptimizer' на целевой компьютер
    echo   2. Запустите EvaLayoutOptimizer.exe
    echo.
) else (
    echo ❌ Ошибка: EXE файл не был создан
    pause
    exit /b 1
)

pause