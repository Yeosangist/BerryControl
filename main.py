#!/usr/bin/env python3

from __future__ import annotations

import os
import signal
import sys

if __package__ in {None, ""}:
    package_root = __file__.rsplit("/strawberry_controller", 1)[0]
    if package_root not in sys.path:
        sys.path.insert(0, package_root)
    from strawberry_controller.config import AppConfig, create_default_config
    from strawberry_controller.mpris import MPRISController
    from strawberry_controller.window import ControllerWindow
else:
    from .config import AppConfig, create_default_config
    from .mpris import MPRISController
    from .window import ControllerWindow


def ensure_single_instance() -> bool:
    lock_path = os.path.expanduser("~/.cache/strawberry-controller.lock")
    os.makedirs(os.path.dirname(lock_path), exist_ok=True)
    try:
        lock_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR)
        import fcntl

        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except BlockingIOError:
            os.close(lock_fd)
            return False
    except OSError:
        return False


def _install_signal_handlers() -> None:
    def handle_shutdown(*_args):
        raise SystemExit(0)

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)


def main() -> int:
    if not ensure_single_instance():
        return 0

    _install_signal_handlers()
    create_default_config()
    config = AppConfig()
    controller = MPRISController()
    controller.connect()

    try:
        from gi.repository import Gtk
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("PyGObject / GTK 3 is required to run this application.") from exc

    window = ControllerWindow(controller, config)
    window.show()
    Gtk.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
