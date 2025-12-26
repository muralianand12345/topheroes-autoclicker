"""
Top Heroes Auto-Clicker

Hotkeys:
    F6 - Start monitoring
    F7 - Stop monitoring

Move mouse to top-left corner of screen to emergency stop (pyautogui failsafe).
"""

import pyautogui

# Safety settings
pyautogui.PAUSE = 0.1
pyautogui.FAILSAFE = True


def main():
    from src.gui import AutoClickerApp

    app = AutoClickerApp()
    app.run()


if __name__ == "__main__":
    main()
