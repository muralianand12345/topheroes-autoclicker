# Top Heroes Auto-Clicker

An auto-clicker for Top Heroes game that uses image detection to find and click UI elements.

## Features

- **Image Detection**: Uses OpenCV template matching to find UI elements
- **Multi-Monitor Support**: Works across multiple monitors
- **Action Sequences**: Supports multi-step click sequences
- **Global Hotkeys**: F6 to start, F7 to stop (works even when window is not focused)
- **Embedded Assets**: Images are baked into the .exe file

## Project Structure

```
├── assets/                     # Source images (for development)
│   ├── auto-challenge/
│   │   ├── action-1.png
│   │   ├── action-2.png
│   │   └── action-3.png
│   └── share-coordinates/
│       ├── action-1.png
│       └── action-2.png
├── scripts/
│   └── embed_assets.py         # Converts images to base64
├── src/
│   ├── core/
│   │   ├── __init__.py
│   │   ├── detector.py         # Image detection logic
│   │   └── models.py           # Data classes
│   ├── gui/
│   │   ├── __init__.py
│   │   └── app.py              # Tkinter GUI
│   ├── embedded_assets.py      # Auto-generated base64 images
│   └── main.py                 # Entry point
├── build.py                    # Build script for .exe
└── pyproject.toml
```

## Development Setup

1. Install dependencies:
   ```bash
   pip install -e .
   ```

2. Add your template images to `assets/` folder:
   ```
   assets/
   ├── sequence-name/
   │   ├── action-1.png    # First click
   │   ├── action-2.png    # Second click
   │   └── action-3.png    # Third click
   ```

3. Embed the assets:
   ```bash
   python scripts/embed_assets.py
   ```

4. Run the app:
   ```bash
   python src/main.py
   ```

## Building the .exe

1. Install PyInstaller:
   ```bash
   pip install pyinstaller
   ```

2. Run the build script:
   ```bash
   python build.py
   ```

3. Find the executable at `dist/TopHeroesAutoClicker.exe`

## Usage

### Hotkeys
- **F6**: Start monitoring
- **F7**: Stop monitoring
- **Move mouse to top-left corner**: Emergency stop (pyautogui failsafe)

### Settings
- **Check Interval**: How often to scan the screen (seconds)
- **Cooldown**: Wait time after completing a sequence (seconds)
- **Step Delay**: Wait time between clicks in a sequence (seconds)
- **Confidence**: Match threshold (0.0 - 1.0, higher = stricter matching)

### Creating Templates

1. Take a screenshot of the game
2. Crop the UI element you want to detect
3. Save as PNG in the appropriate sequence folder
4. Name files as `action-1.png`, `action-2.png`, etc. (sorted alphabetically)

**Tips for good templates:**
- Crop tightly around the element
- Include distinctive features
- Avoid areas that change (like timers or counters)
- Test with `visualize_match()` to verify detection

## License

MIT
