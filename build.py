"""
Build script to create standalone .exe using PyInstaller.

Usage:
    python build.py

This will:
    1. Run embed_assets.py to update embedded assets
    2. Run PyInstaller to create the .exe

Output:
    dist/TopHeroesAutoClicker.exe
"""

import subprocess
import sys
from pathlib import Path


def run_command(cmd: list[str], description: str) -> bool:
    """Run a command and return success status."""
    print(f"\n{'='*50}")
    print(f"{description}")
    print(f"{'='*50}")
    print(f"Running: {' '.join(cmd)}\n")

    result = subprocess.run(cmd)
    return result.returncode == 0


def main():
    # Check if PyInstaller is installed
    try:
        import PyInstaller
        print(f"PyInstaller version: {PyInstaller.__version__}")
    except ImportError:
        print("PyInstaller not found. Installing...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"])

    # Step 1: Embed assets
    assets_path = Path("assets")
    if assets_path.exists() and any(assets_path.iterdir()):
        if not run_command(
            [sys.executable, "scripts/embed_assets.py"],
            "Step 1: Embedding assets into Python file"
        ):
            print("Failed to embed assets!")
            return 1
    else:
        print("\nWarning: No assets folder found or it's empty.")
        print("The .exe will be built without any embedded images.")
        print("Make sure to run embed_assets.py after adding images.\n")

    # Step 2: Run PyInstaller
    pyinstaller_args = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--windowed",  # No console window
        "--name", "TopHeroesAutoClicker",
        "--clean",
        # Add icon if exists
        # "--icon", "icon.ico",
        "src/main.py",
    ]

    # Check for icon
    if Path("icon.ico").exists():
        pyinstaller_args.insert(-1, "--icon")
        pyinstaller_args.insert(-1, "icon.ico")

    if not run_command(pyinstaller_args, "Step 2: Building executable with PyInstaller"):
        print("Failed to build executable!")
        return 1

    # Done
    print("\n" + "="*50)
    print("BUILD COMPLETE!")
    print("="*50)
    exe_path = Path("dist/TopHeroesAutoClicker.exe")
    if exe_path.exists():
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print(f"\nOutput: {exe_path}")
        print(f"Size: {size_mb:.1f} MB")
    else:
        print("\nOutput: dist/TopHeroesAutoClicker (check dist/ folder)")

    print("\nTo run: dist/TopHeroesAutoClicker.exe")

    return 0


if __name__ == "__main__":
    sys.exit(main())
