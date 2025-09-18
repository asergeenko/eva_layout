#!/usr/bin/env python3
"""
Build script for creating Windows EXE using PyInstaller.
"""

import subprocess
import sys
import os
from pathlib import Path

def run_command(cmd, description):
    """Run a command and handle errors."""
    print(f"\n=== {description} ===")
    print(f"Выполнение команды: {' '.join(cmd) if isinstance(cmd, list) else cmd}")

    try:
        result = subprocess.run(cmd, check=True, shell=isinstance(cmd, str))
        print(f"✅ {description} завершено успешно")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка при {description}: {e}")
        return False

def main():
    """Main build function."""
    print("=== Сборка Eva Layout Optimizer в EXE ===")

    # Check if we're in the right directory
    if not Path('streamlit_demo.py').exists():
        print("❌ Ошибка: файл streamlit_demo.py не найден в текущей директории")
        print("Убедитесь, что вы запускаете скрипт из корневой папки проекта")
        sys.exit(1)

    # Check if spec file exists
    spec_file = 'eva_layout.spec'
    if not Path(spec_file).exists():
        print(f"❌ Ошибка: файл {spec_file} не найден")
        sys.exit(1)

    # Install dependencies
    if not run_command([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'],
                      "Установка зависимостей"):
        sys.exit(1)

    # Clean previous builds
    print("\n=== Очистка предыдущих сборок ===")
    for dir_name in ['build', 'dist']:
        if Path(dir_name).exists():
            import shutil
            shutil.rmtree(dir_name)
            print(f"Удалена папка: {dir_name}")

    # Build with PyInstaller
    cmd = [sys.executable, '-m', 'PyInstaller', '--clean', spec_file]
    if not run_command(cmd, "Сборка с PyInstaller"):
        sys.exit(1)

    # Check if build was successful
    exe_path = Path('dist') / 'EvaLayoutOptimizer' / 'EvaLayoutOptimizer.exe'
    if exe_path.exists():
        print(f"\n🎉 Сборка завершена успешно!")
        print(f"📁 EXE файл находится по адресу: {exe_path.absolute()}")
        print(f"📦 Папка для распространения: {exe_path.parent.absolute()}")
        print("\nДля запуска приложения:")
        print(f"  1. Скопируйте всю папку '{exe_path.parent.name}' на целевой компьютер")
        print(f"  2. Запустите {exe_path.name}")
    else:
        print("❌ Ошибка: EXE файл не был создан")
        sys.exit(1)

if __name__ == "__main__":
    main()