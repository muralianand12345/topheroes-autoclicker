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
        if platform.system() == "Windows":
            base = Path.home() / "AppData" / "Local"
        elif platform.system() == "Darwin":
            base = Path.home() / "Library" / "Application Support"
        else:
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

    def get_settings(self) -> dict:
        data = self._load()
        return data.get("settings", {})

    def set_settings(self, settings: dict):
        data = self._load()
        data["settings"] = settings
        self._save(data)
    
    def get_window(self) -> Optional[str]:
        data = self._load()
        return data.get("window_title")
    
    def set_window(self, title: str):
        data = self._load()
        data["window_title"] = title
        self._save(data)
    
    def clear_window(self):
        data = self._load()
        data.pop("window_title", None)
        self._save(data)