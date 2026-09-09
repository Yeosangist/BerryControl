#!/usr/bin/env python3

from __future__ import annotations

from typing import Callable, Optional

try:
    import gi

    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
    from gi.repository import Gdk, Gtk
except (ImportError, ValueError):  # pragma: no cover - GTK-only feature
    gi = None
    Gdk = None
    Gtk = None

if __package__ in {None, ""}:
    import os
    import sys

    package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if package_root not in sys.path:
        sys.path.insert(0, package_root)
    from BerryControls.config import AppConfig, ThemeSettings
else:
    from .config import AppConfig, ThemeSettings


class SettingsDialog:
    def __init__(
        self,
        config: Optional[AppConfig] = None,
        theme: Optional[ThemeSettings] = None,
        on_apply: Optional[Callable[[ThemeSettings], None]] = None,
    ) -> None:
        self.config = config or AppConfig()
        self._original_theme = theme or self.config.load_theme()
        self._working_theme = ThemeSettings(
            font=self._original_theme.font,
            button_color=self._original_theme.button_color,
            text_color=self._original_theme.text_color,
            background_rgba=self._original_theme.background_rgba,
            window_width=self._original_theme.window_width,
            window_height=self._original_theme.window_height,
            show_title=self._original_theme.show_title,
        )
        self._on_apply = on_apply
        self._dialog = None
        self._entries = {}
        self._show_title_toggle = None

    @staticmethod
    def _opaque_background(color: str) -> str:
        if "rgba(" in color:
            inner = color.replace("rgba(", "").replace(")", "")
            values = [part.strip() for part in inner.split(",")]
            if len(values) >= 3:
                return f"rgb({values[0]}, {values[1]}, {values[2]})"
        if "rgb(" in color:
            return color
        return color

    def _apply_theme_to_widget(self) -> None:
        if Gtk is None or self._dialog is None:
            return

        css = (
            f"""
            .settings-window {{
                background-color: {self._opaque_background(self._working_theme.background_rgba)};
                color: {self._working_theme.text_color};
            }}
            .settings-window .title-label {{
                color: {self._working_theme.text_color};
            }}
            .settings-window .action-button {{
                color: {self._working_theme.button_color};
                background-color: {self._opaque_background(self._working_theme.background_rgba)};
            }}
            """
        ).encode("utf-8")
        provider = Gtk.CssProvider()
        provider.load_from_data(css)
        context = self._dialog.get_style_context()
        context.add_provider_for_screen(Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def _read_form_values(self) -> None:
        self._working_theme.font = self._entries["font"].get_text()
        self._working_theme.button_color = self._entries["button_color"].get_text()
        self._working_theme.text_color = self._entries["text_color"].get_text()
        self._working_theme.background_rgba = self._entries["background_rgba"].get_text()
        self._working_theme.window_width = int(self._entries["window_width"].get_text() or 0)
        self._working_theme.window_height = int(self._entries["window_height"].get_text() or 0)
        self._working_theme.show_title = bool(self._show_title_toggle.get_active())

    def _save_current_theme(self) -> None:
        self._read_form_values()
        self.config.save_theme(self._working_theme)
        if self._on_apply is not None:
            self._on_apply(self._working_theme)

    def _close_dialog(self, response_id: int | None = None) -> None:
        if self._dialog is not None:
            self._dialog.response(response_id or Gtk.ResponseType.CANCEL)

    def _build_row(self, label_text: str, widget: Gtk.Widget) -> Gtk.Box:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        label = Gtk.Label(label=label_text)
        label.set_xalign(0.0)
        row.pack_start(label, True, True, 0)
        row.pack_start(widget, False, False, 0)
        return row

    def run(self) -> None:
        if Gtk is None:
            return

        self._dialog = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
        self._dialog.set_title("BerryControl Settings")
        self._dialog.set_modal(True)
        self._dialog.set_default_size(360, 240)
        self._dialog.set_resizable(False)
        self._dialog.set_deletable(True)
        self._dialog.get_style_context().add_class("settings-window")
        self._apply_theme_to_widget()

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        main_box.set_border_width(10)

        form = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self._entries["font"] = Gtk.Entry()
        self._entries["font"].set_text(self._working_theme.font)
        form.pack_start(self._build_row("Font", self._entries["font"]), False, False, 0)

        self._entries["button_color"] = Gtk.Entry()
        self._entries["button_color"].set_text(self._working_theme.button_color)
        form.pack_start(self._build_row("Button color", self._entries["button_color"]), False, False, 0)

        self._entries["text_color"] = Gtk.Entry()
        self._entries["text_color"].set_text(self._working_theme.text_color)
        form.pack_start(self._build_row("Text color", self._entries["text_color"]), False, False, 0)

        self._entries["background_rgba"] = Gtk.Entry()
        self._entries["background_rgba"].set_text(self._working_theme.background_rgba)
        form.pack_start(self._build_row("Background", self._entries["background_rgba"]), False, False, 0)

        self._entries["window_width"] = Gtk.Entry()
        self._entries["window_width"].set_text(str(self._working_theme.window_width))
        form.pack_start(self._build_row("Window width", self._entries["window_width"]), False, False, 0)

        self._entries["window_height"] = Gtk.Entry()
        self._entries["window_height"].set_text(str(self._working_theme.window_height))
        form.pack_start(self._build_row("Window height", self._entries["window_height"]), False, False, 0)

        self._show_title_toggle = Gtk.CheckButton(label="Show media title")
        self._show_title_toggle.set_active(self._working_theme.show_title)
        form.pack_start(self._show_title_toggle, False, False, 0)
        main_box.pack_start(form, True, True, 0)

        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        buttons.set_halign(Gtk.Align.END)

        ok_button = Gtk.Button(label="OK")
        ok_button.get_style_context().add_class("action-button")
        ok_button.connect("clicked", lambda _button: self._save_and_close())
        buttons.pack_end(ok_button, False, False, 0)

        cancel_button = Gtk.Button(label="Cancel")
        cancel_button.get_style_context().add_class("action-button")
        cancel_button.connect("clicked", lambda _button: self._close_and_destroy())
        buttons.pack_end(cancel_button, False, False, 0)

        apply_button = Gtk.Button(label="Apply")
        apply_button.get_style_context().add_class("action-button")
        apply_button.connect("clicked", lambda _button: self._save_current_theme())
        buttons.pack_end(apply_button, False, False, 0)
        
        main_box.pack_end(buttons, False, False, 0)
        self._dialog.add(main_box)
        self._dialog.show_all()
        self._dialog.present()

    def _close_and_destroy(self) -> None:
        if self._dialog is not None:
            self._dialog.destroy()
            self._dialog = None

    def _save_and_close(self) -> None:
        self._save_current_theme()
        self._close_and_destroy()
