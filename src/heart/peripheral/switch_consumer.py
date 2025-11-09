"""Event bus consumer that mirrors the legacy switch peripheral API."""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Any, Mapping

from heart.firmware_io.constants import (BUTTON_LONG_PRESS, BUTTON_PRESS,
                                         SWITCH_ROTATION)
from heart.peripheral.core import Input
from heart.peripheral.core.event_bus import EventBus, SubscriptionHandle
from heart.utilities.logging import get_logger

_LOGGER = get_logger(__name__)


@dataclass(slots=True)
class _SwitchState:
    """Mutable snapshot mirroring :class:`heart.peripheral.switch.BaseSwitch`."""

    rotational_value: int = 0
    button_value: int = 0
    long_button_value: int = 0
    rotation_at_button_press: int = 0
    rotation_at_long_press: int = 0


class SwitchStateConsumer:
    """Track switch input events emitted on an :class:`EventBus` instance."""

    def __init__(
        self,
        event_bus: EventBus,
        *,
        producer_id: int | None = None,
    ) -> None:
        self._event_bus = event_bus
        self._state = _SwitchState()
        self._lock = RLock()
        self._default_producer_id = producer_id if producer_id is not None else 0
        self._has_explicit_producer = producer_id is not None
        self._subscriptions: list[SubscriptionHandle] = []
        self._bind_listeners()
        self._seed_initial_state()

    def close(self) -> None:
        """Detach from the underlying event bus."""

        for handle in self._subscriptions:
            try:
                self._event_bus.unsubscribe(handle)
            except Exception:  # pragma: no cover - defensive cleanup
                _LOGGER.exception(
                    "Failed to unsubscribe switch consumer callback %s", handle.callback
                )
        self._subscriptions.clear()

    # ------------------------------------------------------------------
    # Snapshot accessors
    # ------------------------------------------------------------------
    def get_rotational_value(self) -> int:
        with self._lock:
            return self._state.rotational_value

    def get_rotation_since_last_button_press(self) -> int:
        with self._lock:
            return self._state.rotational_value - self._state.rotation_at_button_press

    def get_rotation_since_last_long_button_press(self) -> int:
        with self._lock:
            return (
                self._state.rotational_value
                - self._state.rotation_at_long_press
            )

    def get_button_value(self) -> int:
        with self._lock:
            return self._state.button_value

    def get_long_button_value(self) -> int:
        with self._lock:
            return self._state.long_button_value

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------
    def _bind_listeners(self) -> None:
        self._subscriptions.append(
            self._event_bus.subscribe(SWITCH_ROTATION, self._handle_rotation)
        )
        self._subscriptions.append(
            self._event_bus.subscribe(BUTTON_PRESS, self._handle_button_press)
        )
        self._subscriptions.append(
            self._event_bus.subscribe(
                BUTTON_LONG_PRESS, self._handle_long_button_press
            )
        )

    def _handle_rotation(self, event: Input) -> None:
        value = self._extract_rotation(event.data)
        if value is None:
            return
        with self._lock:
            if not self._accept_event(event):
                return
            self._state.rotational_value = value

    def _handle_button_press(self, event: Input) -> None:
        with self._lock:
            if not self._accept_event(event):
                return
            increment = self._extract_increment(event.data)
            if increment <= 0:
                return
            self._state.button_value += increment
            self._state.rotation_at_button_press = self._state.rotational_value

    def _handle_long_button_press(self, event: Input) -> None:
        with self._lock:
            if not self._accept_event(event):
                return
            increment = self._extract_increment(event.data)
            if increment <= 0:
                return
            self._state.long_button_value += increment
            self._state.rotation_at_long_press = self._state.rotational_value

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _seed_initial_state(self) -> None:
        """Populate the snapshot with existing rotation data if available."""

        producer_id = self._default_producer_id if self._has_explicit_producer else None
        entry = self._event_bus.state_store.get_latest(SWITCH_ROTATION, producer_id)
        if entry is None:
            return
        value = self._extract_rotation(entry.data)
        if value is None:
            return
        with self._lock:
            self._state.rotational_value = value
            self._state.rotation_at_button_press = value
            self._state.rotation_at_long_press = value

    def _accept_event(self, event: Input) -> bool:
        if self._has_explicit_producer and event.producer_id != self._default_producer_id:
            return False
        if not self._has_explicit_producer:
            self._default_producer_id = event.producer_id
        return True

    @staticmethod
    def _extract_rotation(payload: Any) -> int | None:
        if isinstance(payload, Mapping):
            for key in ("position", "rotation", "value"):
                if key in payload:
                    return SwitchStateConsumer._coerce_int(payload[key])
        return SwitchStateConsumer._coerce_int(payload)

    @staticmethod
    def _extract_increment(payload: Any) -> int:
        if isinstance(payload, Mapping):
            if "pressed" in payload and not bool(payload["pressed"]):
                return 0
            for key in ("value", "count", "increment"):
                if key in payload:
                    value = SwitchStateConsumer._coerce_int(payload[key])
                    return 0 if value is None else max(0, value)
            return 1
        if isinstance(payload, bool):
            return 1 if payload else 0
        value = SwitchStateConsumer._coerce_int(payload)
        return 0 if value is None else max(0, value)

    @staticmethod
    def _coerce_int(value: Any) -> int | None:
        if isinstance(value, bool):
            return 1 if value else 0
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            try:
                return int(float(value))
            except ValueError:
                return None
        return None


__all__ = ["SwitchStateConsumer"]
