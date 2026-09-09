#!/usr/bin/env python3

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)


def resource_path(relative_path: str) -> Path:
    """Resolve an asset from source or PyInstaller's one-file directory."""
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        return Path(bundle_root) / relative_path
    return Path(__file__).resolve().parent / relative_path


class TrayIcon:
    """Own the tray indicator and its menu independently from the GTK window."""

    def __init__(
        self,
        on_quit: Callable[[], None],
        on_reset_size: Optional[Callable[[], None]] = None,
        on_settings: Optional[Callable[[], None]] = None,
    ) -> None:
        self._on_quit = on_quit
        self._on_reset_size = on_reset_size
        self._on_settings = on_settings
        self._indicator = None
        self._menu = None
        self._started = False

    def start(self) -> None:
        if self._started:
            return

        try:
            import gi

            gi.require_version("AyatanaAppIndicator3", "0.1")
            from gi.repository import AyatanaAppIndicator3, Gtk
        except (ImportError, ValueError) as exc:  # pragma: no cover - desktop dependency
            raise RuntimeError("libayatana-appindicator is required for the system tray.") from exc

        icon_path = resource_path("assets/trayicon.png")
        if not icon_path.is_file():
            raise FileNotFoundError(f"Tray icon asset not found: {icon_path}")

        indicator = AyatanaAppIndicator3.Indicator.new(
            "BerryControl",
            icon_path.stem,
            AyatanaAppIndicator3.IndicatorCategory.APPLICATION_STATUS,
        )
        indicator.set_icon_theme_path(str(icon_path.parent))
        indicator.set_status(AyatanaAppIndicator3.IndicatorStatus.ACTIVE)

        menu = Gtk.Menu()
        settings_item = Gtk.MenuItem(label="Settings…")
        settings_item.connect("activate", self._settings_from_menu)
        menu.append(settings_item)
        reset_size_item = Gtk.MenuItem(label="Reset window size")
        reset_size_item.connect("activate", self._reset_size_from_menu)
        menu.append(reset_size_item)
        quit_item = Gtk.MenuItem(label="Quit")
        quit_item.connect("activate", self._quit_from_menu)
        menu.append(quit_item)
        menu.show_all()
        indicator.set_menu(menu)

        self._indicator = indicator
        self._menu = menu
        self._started = True

    def _quit_from_menu(self, _item) -> None:
        self._on_quit()

    def _reset_size_from_menu(self, _item) -> None:
        if self._on_reset_size is not None:
            self._on_reset_size()

    def _settings_from_menu(self, _item) -> None:
        if self._on_settings is not None:
            self._on_settings()

    def close(self) -> None:
        if not self._started:
            return

        if self._indicator is not None:
            try:
                from gi.repository import AyatanaAppIndicator3

                self._indicator.set_status(AyatanaAppIndicator3.IndicatorStatus.PASSIVE)
            except (ImportError, ValueError, AttributeError):
                logger.debug("Tray indicator was already unavailable", exc_info=True)
        self._indicator = None
        self._menu = None
        self._started = False