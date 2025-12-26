"""
Top Heroes Auto-Clicker

Hotkeys:
    F6 - Start monitoring
    F7 - Stop monitoring

Move mouse to top-left corner of screen to emergency stop (pyautogui failsafe).
"""

import pyautogui

pyautogui.PAUSE = 0.1
pyautogui.FAILSAFE = True


def main():
    from gui import AutoClickerApp

    app = AutoClickerApp()
    app.run()


if __name__ == "__main__":
    main()
