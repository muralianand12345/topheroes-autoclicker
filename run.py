import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

import pyautogui
pyautogui.PAUSE = 0.1
pyautogui.FAILSAFE = True

from gui import AutoClickerApp

if __name__ == "__main__":
    app = AutoClickerApp()
    app.run()