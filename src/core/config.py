import json
import platform
from pathlib import Path
from typing import Optional


class Config:
    APP_NAME = "TopHeroesAutoClicker"
    CONFIG_FILENAME = "config.json"

    def __init__(self):
        self.config_path = self._get_config_path()
        self._ensure_config_dir()

    def _get_config_path(self) -> Path:
        """Get the config file path based on OS."""
        if platform.system() == "Windows":
            # C:\Users\<name>\AppData\Local\TopHeroesAutoClicker\config.json
            base = Path.home() / "AppData" / "Local"
        elif platform.system() == "Darwin":
            # macOS: ~/Library/Application Support/TopHeroesAutoClicker/config.json
            base = Path.home() / "Library" / "Application Support"
        else:
            # Linux: ~/.local/share/TopHeroesAutoClicker/config.json
            base = Path.home() / ".local" / "share"

        return base / self.APP_NAME / self.CONFIG_FILENAME

    def _ensure_config_dir(self):
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> dict:
        if not self.config_path.exists():
            return {}

        try:
            with open(self.config_path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    def _save(self, data: dict):
        try:
            with open(self.config_path, "w") as f:
                json.dump(data, f, indent=2)
        except IOError as e:
            print(f"Failed to save config: {e}")

    def get_scale(self) -> Optional[float]:
        data = self._load()
        return data.get("scale")

    def set_scale(self, scale: float):
        data = self._load()
        data["scale"] = scale
        self._save(data)

    def clear_scale(self):
        data = self._load()
        data.pop("scale", None)
        self._save(data)

    def get_settings(self) -> dict:
        data = self._load()
        return data.get("settings", {})

    def set_settings(self, settings: dict):
        data = self._load()
        data["settings"] = settings
        self._save(data)