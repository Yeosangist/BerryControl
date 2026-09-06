#!/usr/bin/env python3

from __future__ import annotations

from typing import Optional

try:
    import gi

    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
    from gi.repository import Gdk, Gtk, Pango
except (ImportError, ValueError):  # pragma: no cover - exercised only when GTK is absent
    gi = None
    Gdk = None
    Gtk = None

if __package__ in {None, ""}:
    import os
    import sys

    package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if package_root not in sys.path:
        sys.path.insert(0, package_root)
    from strawberry_controller.config import AppConfig
else:
    from .config import AppConfig


class ControllerWindow:
    def __init__(self, controller, config: Optional[AppConfig] = None) -> None:
        self.controller = controller
        self.config = config or AppConfig()
        self._window = None
        self._title_label = None
        self._play_pause_button = None
        self._prev_button = None
        self._next_button = None
        self._theme = self.config.load_theme()
        self.controller.subscribe(self._apply_state)
        self._setup_ui()

    @staticmethod
    def _font_css(font: str) -> str:
        description = Pango.FontDescription(font)
        family = description.get_family() or "Sans"
        size = description.get_size() / Pango.SCALE or 12
        escaped_family = family.replace('\\', '\\\\').replace('"', '\\"')
        return f'{size:g}pt "{escaped_family}"'

    def _setup_ui(self) -> None:
        if Gtk is None:
            return

        self._window = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
        self._window.set_title("Strawberry Controller")
        self._window.set_decorated(False)
        self._window.set_resizable(False)
        self._window.set_keep_above(True)
        self._window.set_skip_taskbar_hint(True)
        self._window.set_default_size(self._theme.window_width, self._theme.window_height)

        screen = self._window.get_screen()
        if screen is not None:
            visual = screen.get_rgba_visual()
            if visual is not None:
                self._window.set_visual(visual)

        self._window.set_app_paintable(True)
        self._window.set_border_width(0)

        css = (
            f"""
            window {{
                background: transparent;
            }}
            .panel {{
                background-color: {self._theme.background_rgba};
                padding: 10px 0px;
                margin: 0;
            }}
            .title-label {{
                color: {self._theme.text_color};
                font: {self._font_css(self._theme.font)};
                font-weight: 600;
            }}
            .control-button {{
                min-width: 18px;
                min-height: 18px;
                color: {self._theme.button_color};
            }}
            """
        ).encode("utf-8")
        provider = Gtk.CssProvider()
        provider.load_from_data(css)
        context = self._window.get_style_context()
        context.add_provider_for_screen(Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_border_width(0)
        box.set_homogeneous(False)
        box.get_style_context().add_class("panel")
        frame = Gtk.EventBox()
        frame.get_style_context().add_class("panel")
        frame.set_border_width(0)
        frame.add(box)
        self._title_label = Gtk.Label()
        self._title_label.set_ellipsize(Pango.EllipsizeMode.END)
        self._title_label.set_xalign(0.5)
        self._title_label.get_style_context().add_class("title-label")

        controls = Gtk.Box(spacing=15)
        controls.set_halign(Gtk.Align.CENTER)
        self._prev_button = Gtk.Button()
        self._prev_button.set_image(Gtk.Image.new_from_icon_name("media-skip-backward-symbolic", Gtk.IconSize.BUTTON))
        self._prev_button.get_style_context().add_class("control-button")
        self._prev_button.connect("clicked", self._on_previous)

        self._play_pause_button = Gtk.Button()
        self._play_pause_button.set_image(Gtk.Image.new_from_icon_name("media-playback-pause-symbolic", Gtk.IconSize.BUTTON))
        self._play_pause_button.get_style_context().add_class("control-button")
        self._play_pause_button.connect("clicked", self._on_play_pause)

        self._next_button = Gtk.Button()
        self._next_button.set_image(Gtk.Image.new_from_icon_name("media-skip-forward-symbolic", Gtk.IconSize.BUTTON))
        self._next_button.get_style_context().add_class("control-button")
        self._next_button.connect("clicked", self._on_next)

        controls.pack_start(self._prev_button, False, False, 0)
        controls.pack_start(self._play_pause_button, False, False, 0)
        controls.pack_start(self._next_button, False, False, 0)

        box.pack_start(self._title_label, False, False, 0)
        box.pack_start(controls, False, False, 0)
        self._window.add(frame)

        self._window.connect("button-press-event", self._on_button_press)
        self._window.connect("configure-event", self._on_configure)
        self._window.connect("delete-event", Gtk.main_quit)

        self._apply_state(self.controller.state)

    def _on_button_press(self, widget, event):
        if event.button == 1 and event.state & Gdk.ModifierType.MOD1_MASK:
            self._window.begin_move_drag(event.button, int(event.x_root), int(event.y_root), event.time)
            return True
        return False

    def _on_configure(self, widget, event):
        x, y = widget.get_position()
        self.config.save_position(x, y)
        return False

    def _on_previous(self, _button):
        self.controller.previous()

    def _on_play_pause(self, _button):
        self.controller.play_pause()

    def _on_next(self, _button):
        self.controller.next()

    def _apply_state(self, state) -> None:
        if self._title_label is None:
            return

        availability = getattr(state, "availability", "CONNECTING")
        playback = getattr(state, "playback", "STOPPED")
        title = getattr(state, "title", None) or "No track playing"

        if availability == "CONNECTING":
            title = "Connecting…"
        elif availability == "UNAVAILABLE":
            title = "Strawberry unavailable"
        elif not title:
            title = "No track playing"

        if availability in {"CONNECTING", "UNAVAILABLE"}:
            self._prev_button.set_sensitive(False)
            self._play_pause_button.set_sensitive(False)
            self._next_button.set_sensitive(False)
        else:
            self._prev_button.set_sensitive(True)
            self._play_pause_button.set_sensitive(True)
            self._next_button.set_sensitive(True)

        if playback == "PLAYING":
            self._set_button_icon(self._play_pause_button, "media-playback-pause-symbolic")
        else:
            self._set_button_icon(self._play_pause_button, "media-playback-start-symbolic")

        self._title_label.set_text(title)

    def _set_button_icon(self, button, icon_name: str) -> None:
        button.set_image(Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.BUTTON))

    def show(self) -> None:
        if self._window is not None:
            self._window.show_all()
            position = self.config.load_position()
            if position:
                self._window.move(*position)

    def run(self) -> None:
        if self._window is None:
            return
        Gtk.main()

    def close(self) -> None:
        if self._window is not None:
            self._window.destroy()


try:
    import gi.repository.Pango as Pango
except Exception:  # pragma: no cover
    Pango = None
