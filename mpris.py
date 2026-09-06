#!/usr/bin/env python3

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Optional

logger = logging.getLogger(__name__)

PLAYER_NAME = "org.mpris.MediaPlayer2.strawberry"
PLAYER_PATH = "/org/mpris/MediaPlayer2"


@dataclass(frozen=True)
class MetadataState:
    title: Optional[str] = None


@dataclass(frozen=True)
class PlayerState:
    availability: str = "CONNECTING"
    playback: str = "STOPPED"
    title: Optional[str] = None


def parse_playback_status(status: Optional[str]) -> str:
    if status is None:
        return "STOPPED"
    normalized = str(status).strip().lower()
    if normalized in {"playing", "play"}:
        return "PLAYING"
    if normalized in {"paused", "pause"}:
        return "PAUSED"
    if normalized in {"stopped", "stop"}:
        return "STOPPED"
    return "STOPPED"


def _string_from_metadata(value: Any) -> Optional[str]:
    if value is None:
        return None
    # Unpack GLib.Variant if present
    if hasattr(value, "unpack"):
        value = value.unpack()
    if isinstance(value, (list, tuple)):
        parts = [str(item).strip() for item in value if str(item).strip()]
        return ", ".join(parts) if parts else None
    text = str(value).strip()
    return text or None


def normalize_metadata(raw_metadata: Optional[Mapping[str, Any]]) -> MetadataState:
    if not raw_metadata:
        logger.debug("No raw metadata provided")
        return MetadataState()

    title = _string_from_metadata(raw_metadata.get("xesam:title"))
    logger.debug("Extracted title: %s from metadata keys: %s", title, list(raw_metadata.keys()))

    if title is not None and not title:
        title = None

    return MetadataState(title=title)


def build_player_state(playback_status: Optional[str], raw_metadata: Optional[Mapping[str, Any]], availability: str = "AVAILABLE") -> PlayerState:
    playback = parse_playback_status(playback_status)
    metadata = normalize_metadata(raw_metadata)
    title = metadata.title
    return PlayerState(availability=availability, playback=playback, title=title)


def is_service_unavailable_error(exc: BaseException) -> bool:
    message = str(exc).lower()
    return (
        "serviceunknown" in message
        or "name is not activatable" in message
        or "org.freedesktop.dbus.error.serviceunknown" in message
    )


class MPRISController:
    """Very small MPRIS wrapper with reactive state updates and a safe fallback."""

    def __init__(self, service_name: str = PLAYER_NAME, object_path: str = PLAYER_PATH) -> None:
        self.service_name = service_name
        self.object_path = object_path
        self._properties_proxy = None
        self._player_proxy = None
        self._state = PlayerState()
        self._connected = False
        self._state_listeners: list[Callable[[PlayerState], None]] = []
        self._poll_source_id = None

    @property
    def state(self) -> PlayerState:
        return self._state

    def subscribe(self, listener: Callable[[PlayerState], None]) -> None:
        self._state_listeners.append(listener)

    def _set_state(self, state: PlayerState) -> None:
        self._state = state
        for listener in tuple(self._state_listeners):
            try:
                listener(state)
            except Exception:
                logger.exception("MPRIS state listener failed")

    def connect(self) -> None:
        try:
            from gi.repository import Gio
        except ImportError:
            logger.warning("PyGObject/GIO unavailable; MPRIS controller will remain offline.")
            self._set_availability("UNAVAILABLE")
            return

        try:
            self._properties_proxy = Gio.DBusProxy.new_for_bus_sync(
                Gio.BusType.SESSION,
                Gio.DBusProxyFlags.NONE,
                None,
                self.service_name,
                self.object_path,
                "org.freedesktop.DBus.Properties",
                None,
            )
            self._player_proxy = Gio.DBusProxy.new_for_bus_sync(
                Gio.BusType.SESSION,
                Gio.DBusProxyFlags.NONE,
                None,
                self.service_name,
                self.object_path,
                "org.mpris.MediaPlayer2.Player",
                None,
            )
            self._connected = True
            self._set_availability("AVAILABLE")
            self.refresh_state()
            self._start_polling()
        except Exception:
            logger.exception("Failed to connect to Strawberry MPRIS service")
            self._set_availability("UNAVAILABLE")
            self._properties_proxy = None
            self._player_proxy = None
            self._connected = False

    def _set_availability(self, availability: str) -> None:
        self._set_state(
            PlayerState(
                availability=availability,
                playback=self._state.playback,
                title=self._state.title,
            )
        )

    def _start_polling(self) -> None:
        try:
            from gi.repository import GLib
        except ImportError:
            logger.warning("GLib unavailable; polling not started")
            return

        if self._poll_source_id is not None:
            return

        self._poll_source_id = GLib.timeout_add(3000, self._poll)
        logger.debug("Started 3-second polling interval")

    def _poll(self) -> bool:
        self.refresh_state()
        return True  # Continue polling

    def stop_polling(self) -> None:
        if self._poll_source_id is not None:
            try:
                from gi.repository import GLib
                GLib.source_remove(self._poll_source_id)
                self._poll_source_id = None
                logger.debug("Stopped polling")
            except Exception:
                logger.exception("Failed to stop polling")

    def refresh_state(self) -> PlayerStatus:
        if self._properties_proxy is None:
            self._set_availability("UNAVAILABLE")
            return self._state

        try:
            from gi.repository import GLib
        except ImportError:
            self._set_availability("UNAVAILABLE")
            return self._state

        try:
            raw = self._properties_proxy.call_sync(
                "GetAll",
                GLib.Variant("(s)", ["org.mpris.MediaPlayer2.Player"]),
                0,
                -1,
                None,
            )
        except Exception as exc:
            if is_service_unavailable_error(exc):
                logger.info("Strawberry MPRIS service unavailable; waiting to reconnect.")
            else:
                logger.warning("Failed to read MPRIS properties: %s", exc)
            self._set_availability("UNAVAILABLE")
            return self._state

        try:
            values = raw.unpack()[0]
            playback = values.get("PlaybackStatus")
            metadata = values.get("Metadata")
            logger.debug("MPRIS metadata received: %s", metadata)
        except Exception:
            logger.warning("Unexpected MPRIS property payload")
            self._set_availability("UNAVAILABLE")
            return self._state

        self._set_state(
            build_player_state(
                playback.unpack() if hasattr(playback, "unpack") else playback,
                metadata,
                availability="AVAILABLE",
            )
        )
        return self._state

    def previous(self) -> bool:
        return self._invoke_method("Previous")

    def play_pause(self) -> bool:
        return self._invoke_method("PlayPause")

    def next(self) -> bool:
        return self._invoke_method("Next")

    def _invoke_method(self, method_name: str) -> bool:
        if self._player_proxy is None:
            self._set_availability("UNAVAILABLE")
            return False
        try:
            from gi.repository import GLib

            self._player_proxy.call(
                method_name,
                GLib.Variant("()", ()),
                0,
                -1,
                None,
                lambda *args: None,
            )
            return True
        except Exception as exc:
            if is_service_unavailable_error(exc):
                logger.info("Strawberry MPRIS service unavailable while invoking %s.", method_name)
            else:
                logger.warning("MPRIS method failed: %s: %s", method_name, exc)
            self._set_availability("UNAVAILABLE")
            return False


PlayerStatus = PlayerState
