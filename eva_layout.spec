# -*- mode: python ; coding: utf-8 -*-

import os

block_cipher = None

# Определяем дополнительные данные для включения
added_files = [
    ('logo.png', '.'),  # Логотип приложения
    ('streamlit_demo.py', '.'),  # Streamlit приложение
]

# Скрытые импорты для библиотек, которые PyInstaller может не найти
hiddenimports = [
    'streamlit',
    'streamlit.web.cli',
    'streamlit.web.server',
    'streamlit.web.server.server',
    'streamlit.runtime',
    'streamlit.runtime.scriptrunner',
    'streamlit.runtime.state',
    'pandas',
    'numpy',
    'shapely',
    'shapely.geometry',
    'shapely.ops',
    'shapely.affinity',
    'ezdxf',
    'matplotlib',
    'matplotlib.pyplot',
    'openpyxl',
    'altair',
    'plotly',
    'pydeck',
    'tornado',
    'validators',
    'watchdog',
    'click',
    'toml',
    'tzlocal',
    'pytz',
    'packaging',
    'pkg_resources',
]

a = Analysis(
    ['run_streamlit.py'],
    pathex=[os.getcwd()],
    binaries=[],
    datas=added_files,
    hiddenimports=hiddenimports,
    hookspath=['./.hooks'],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='EvaLayoutOptimizer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # Консольное приложение для вывода логов
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='logo.png' if os.path.exists('logo.png') else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='EvaLayoutOptimizer',
)