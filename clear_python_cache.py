#!/usr/bin/env python3
"""Script to clear Python cache completely."""

import os
import shutil
import sys
import glob

print("Очистка кеша Python...")

# Remove __pycache__ directories
pycache_dirs = glob.glob("**/__pycache__", recursive=True)
for cache_dir in pycache_dirs:
    try:
        shutil.rmtree(cache_dir)
        print(f"Удален: {cache_dir}")
    except Exception as e:
        print(f"Не удалось удалить {cache_dir}: {e}")

# Remove .pyc files
pyc_files = glob.glob("**/*.pyc", recursive=True)
for pyc_file in pyc_files:
    try:
        os.remove(pyc_file)
        print(f"Удален: {pyc_file}")
    except Exception as e:
        print(f"Не удалось удалить {pyc_file}: {e}")

print("Кеш Python очищен!")
print("Теперь перезапустите Streamlit приложение.")