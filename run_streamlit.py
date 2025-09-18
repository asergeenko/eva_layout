#!/usr/bin/env python3
"""
Launcher script for the Eva Layout Optimizer Streamlit application.
This script is designed to be used with PyInstaller.
"""

import sys
import subprocess
from pathlib import Path


def find_streamlit_exe():
    """Find streamlit executable in the bundle or system."""
    if getattr(sys, "frozen", False):
        # Running in PyInstaller bundle
        bundle_dir = Path(sys._MEIPASS)

        # Try to find streamlit in the bundle
        possible_paths = [
            bundle_dir / "streamlit",
            bundle_dir / "Scripts" / "streamlit.exe",
            bundle_dir / "Scripts" / "streamlit",
        ]

        for path in possible_paths:
            if path.exists():
                return str(path)

    # Fallback to system streamlit
    return "streamlit"


def main():
    """Main launcher function."""
    print("=== Eva Layout Optimizer ===")
    print("Запуск приложения...")

    # Determine the script directory
    if getattr(sys, "frozen", False):
        # Running in PyInstaller bundle
        script_dir = Path(sys._MEIPASS)
        app_script = script_dir / "streamlit_demo.py"
    else:
        # Running in development
        script_dir = Path(__file__).parent
        app_script = script_dir / "streamlit_demo.py"

    if not app_script.exists():
        print(f"Error: Could not find streamlit_demo.py at {app_script}")
        sys.exit(1)

    # Find streamlit executable
    streamlit_cmd = find_streamlit_exe()

    # Prepare streamlit command
    if getattr(sys, "frozen", False):
        # Running in PyInstaller bundle - use streamlit directly
        cmd = [
            streamlit_cmd,
            "run",
            str(app_script),
            "--server.port=8501",
            "--server.address=localhost",
            "--browser.gatherUsageStats=false",
        ]
    else:
        # Running in development - use python -m streamlit
        cmd = [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(app_script),
            "--server.port=8501",
            "--server.address=localhost",
            "--browser.gatherUsageStats=false",
        ]

    print(f"Starting Streamlit with command: {' '.join(cmd)}")

    try:
        # Run streamlit
        result = subprocess.run(cmd, cwd=script_dir)
        sys.exit(result.returncode)
    except KeyboardInterrupt:
        print("\nПриложение остановлено пользователем.")
        sys.exit(0)
    except Exception as e:
        print(f"Ошибка запуска приложения: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
