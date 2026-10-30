#!/usr/bin/env python3

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

CONFIG_DIR = Path.home() / ".config" / "berrycontrol"
CONFIG_FILE = CONFIG_DIR / "window.json"


@dataclass
class ThemeSettings:
    font: str = "Sans 12"
    button_color: str = "#00ff00"
    text_color: str = "#00ff00"
    background_rgba: str = "rgba(0, 17, 0, 0.4)"
    window_width: int = 250
    window_height: int = 50
    show_title: bool = True


class AppConfig:
    def __init__(self, config_path: Path | str = CONFIG_FILE) -> None:
        self.config_path = Path(config_path)
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _parse_bool(value, default: bool) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return default

    def _read_data(self) -> dict:
        if not self.config_path.exists():
            return {}
        try:
            with self.config_path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def _write_data(self, data: dict) -> None:
        try:
            with self.config_path.open("w", encoding="utf-8") as handle:
                json.dump(data, handle)
        except OSError:
            pass

    def load_position(self) -> Optional[Tuple[int, int]]:
        data = self._read_data()
        x = data.get("x")
        y = data.get("y")
        if isinstance(x, (int, float)) and isinstance(y, (int, float)):
            return int(x), int(y)
        return None

    def save_position(self, x: int, y: int) -> None:
        payload = self._read_data()
        payload["x"] = int(x)
        payload["y"] = int(y)
        self._write_data(payload)

    def load_theme(self) -> ThemeSettings:
        data = self._read_data()
        return ThemeSettings(
            font=str(data.get("font", ThemeSettings.font)),
            button_color=str(data.get("button_color", ThemeSettings.button_color)),
            text_color=str(data.get("text_color", ThemeSettings.text_color)),
            background_rgba=str(data.get("background_rgba", ThemeSettings.background_rgba)),
            window_width=int(data.get("window_width", ThemeSettings.window_width)),
            window_height=int(data.get("window_height", ThemeSettings.window_height)),
            show_title=self._parse_bool(data.get("show_title", ThemeSettings.show_title), ThemeSettings.show_title),
        )

    def save_theme(self, theme: ThemeSettings) -> None:
        payload = self._read_data()
        payload["font"] = theme.font
        payload["button_color"] = theme.button_color
        payload["text_color"] = theme.text_color
        payload["background_rgba"] = theme.background_rgba
        payload["window_width"] = theme.window_width
        payload["window_height"] = theme.window_height
        payload["show_title"] = theme.show_title
        self._write_data(payload)


def default_position() -> Tuple[int, int]:
    return (0, 0)


def create_default_config() -> None:
    """Create a default config file with all settings exposed for user editing.
    Only creates the file if it doesn't already exist, preserving user customizations."""
    config = AppConfig()
    if not config.config_path.exists():
        default_theme = ThemeSettings()
        config.save_theme(default_theme)
