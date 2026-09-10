#!/usr/bin/env python3

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Optional

logger = logging.getLogger(__name__)

MPRIS_SERVICE_PREFIX = "org.mpris.MediaPlayer2."
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


def is_mpris_service_name(service_name: str) -> bool:
    return service_name.startswith(MPRIS_SERVICE_PREFIX) and len(service_name) > len(MPRIS_SERVICE_PREFIX)


def select_mpris_service(
    service_names: list[str],
    preferred: Optional[str] = None,
    statuses: Optional[Mapping[str, Optional[str]]] = None,
) -> Optional[str]:
    """Select an active MPRIS service, honoring an explicitly requested player."""
    services = sorted(name for name in service_names if is_mpris_service_name(name))
    if preferred is not None:
        return preferred if preferred in services else None
    if statuses:
        status_rank = {"PLAYING": 0, "PAUSED": 1, "STOPPED": 2}
        services.sort(key=lambda name: (status_rank.get(parse_playback_status(statuses.get(name)), 3), name))
    return services[0] if services else None


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
    title = None if playback == "STOPPED" else metadata.title
    return PlayerState(availability=availability, playback=playback, title=title)


def is_service_unavailable_error(exc: BaseException) -> bool:
    message = str(exc).lower()
    return (
        "serviceunknown" in message
        or "name is not activatable" in message
        or "org.freedesktop.dbus.error.serviceunknown" in message
    )


class MPRISController:
    """Small MPRIS wrapper that can control any available MPRIS player."""

    def __init__(self, service_name: Optional[str] = None, object_path: str = PLAYER_PATH) -> None:
        self._preferred_service_name = service_name
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

    @property
    def player_name(self) -> Optional[str]:
        if not self.service_name or not is_mpris_service_name(self.service_name):
            return None
        return self.service_name.removeprefix(MPRIS_SERVICE_PREFIX)

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
        if self.service_name is None:
            self.service_name = self._discover_service_name()
        if self.service_name is None:
            logger.info("No MPRIS player is currently available.")
            self._set_availability("UNAVAILABLE")
            return

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
            if hasattr(self._properties_proxy, "connect"):
                self._properties_proxy.connect("g-properties-changed", self._on_properties_changed)
            self._connected = True
            self._set_availability("AVAILABLE")
            self.refresh_state()
            self._start_polling()
        except Exception:
            logger.exception("Failed to connect to MPRIS service %s", self.service_name)
            self._set_availability("UNAVAILABLE")
            self._properties_proxy = None
            self._player_proxy = None
            self._connected = False

    def _discover_service_name(self) -> Optional[str]:
        try:
            from gi.repository import Gio, GLib

            bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            result = bus.call_sync(
                "org.freedesktop.DBus",
                "/org/freedesktop/DBus",
                "org.freedesktop.DBus",
                "ListNames",
                None,
                GLib.VariantType("(as)"),
                Gio.DBusCallFlags.NONE,
                -1,
                None,
            )
            names = result.unpack()[0]
            services = [name for name in names if is_mpris_service_name(name)]
            statuses = {}
            for service_name in services:
                try:
                    proxy = Gio.DBusProxy.new_for_bus_sync(
                        Gio.BusType.SESSION,
                        Gio.DBusProxyFlags.NONE,
                        None,
                        service_name,
                        self.object_path,
                        "org.freedesktop.DBus.Properties",
                        None,
                    )
                    properties = proxy.call_sync(
                        "GetAll",
                        GLib.Variant("(s)", ["org.mpris.MediaPlayer2.Player"]),
                        0,
                        -1,
                        None,
                    ).unpack()[0]
                    playback_status = properties.get("PlaybackStatus")
                    statuses[service_name] = (
                        playback_status.unpack() if hasattr(playback_status, "unpack") else playback_status
                    )
                except Exception as exc:
                    logger.debug("Unable to inspect MPRIS service %s: %s", service_name, exc)
            return select_mpris_service(services, self._preferred_service_name, statuses)
        except Exception as exc:
            logger.debug("Unable to discover MPRIS services: %s", exc)
            return None

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
        if self._preferred_service_name is None:
            discovered = self._discover_service_name()
            if discovered != self.service_name:
                self.service_name = discovered
                self._properties_proxy = None
                self._player_proxy = None
                self._connected = False
                self.connect()
                return True
        elif not self._connected:
            self.connect()
        self.refresh_state()
        return True  # Continue polling

    def stop_polling(self) -> None:
        if self._poll_source_id is not None:
            try:
                from gi.repository import GLib
                GLib.source_remove(self._poll_source_id)
                logger.debug("Stopped polling")
            except Exception:
                logger.exception("Failed to stop polling")
            finally:
                self._poll_source_id = None

    def close(self) -> None:
        """Stop updates and release the D-Bus proxies.

        This method is deliberately safe to call more than once so every
        application shutdown path can use the same cleanup operation.
        """
        self.stop_polling()
        self._connected = False
        self._properties_proxy = None
        self._player_proxy = None
        self._state_listeners.clear()

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
                logger.info("MPRIS service unavailable; waiting to reconnect.")
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

    def _on_properties_changed(self, _proxy, changed_properties, _invalidated_properties) -> None:
        """Refresh the full state when a property change arrives so metadata stays current."""
        if self._properties_proxy is not None:
            try:
                self.refresh_state()
                return
            except Exception:
                logger.exception("Failed to refresh MPRIS state after property change")

        values = {
            "PlaybackStatus": self._state.playback,
            "Metadata": {"xesam:title": self._state.title} if self._state.title else {},
        }
        for key, value in changed_properties.items():
            values[key] = value.unpack() if hasattr(value, "unpack") else value
        self._set_state(build_player_state(values["PlaybackStatus"], values["Metadata"], availability="AVAILABLE"))

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
                logger.info("MPRIS service unavailable while invoking %s.", method_name)
            else:
                logger.warning("MPRIS method failed: %s: %s", method_name, exc)
            self._set_availability("UNAVAILABLE")
            return False


PlayerStatus = PlayerState
