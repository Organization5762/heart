from __future__ import annotations

import math
import time
from abc import ABC, abstractmethod
from collections import deque
from typing import Deque, Iterable

from heart.peripheral.gamepad import Gamepad
from heart.peripheral.heart_rates import (
    _mutex as heart_rate_mutex,
    battery_status,
    current_bpms,
    last_seen,
)
from heart.peripheral.phone_text import PhoneText
from heart.peripheral.sensor import Accelerometer
from heart.peripheral.switch import BaseSwitch, BluetoothSwitch
from peripheral_sidecar.config import PeripheralServiceConfig
from peripheral_sidecar.models import ActionEvent, PeripheralPollResult, RawPeripheralSnapshot
from heart.utilities.logging import get_logger

logger = get_logger(__name__)


class PeripheralActionMapper(ABC):
    """Base class used to convert peripheral state into high level actions."""

    def __init__(self, source: str, config: PeripheralServiceConfig) -> None:
        self.source = source
        self.config = config

    @abstractmethod
    def poll(self) -> PeripheralPollResult:
        """Poll the underlying peripheral for raw samples and derived actions."""


class SwitchActionMapper(PeripheralActionMapper):
    def __init__(self, switch: BaseSwitch, source: str, config: PeripheralServiceConfig) -> None:
        super().__init__(source, config)
        self._switch = switch
        self._last_rotation = switch.get_rotational_value()
        self._last_button = switch.get_button_value()
        self._last_long_press = switch.get_long_button_value()
        self._rotation_history: Deque[tuple[float, int]] = deque()

    def poll(self) -> PeripheralPollResult:
        now = time.time()
        rotation = self._switch.get_rotational_value()
        button_value = self._switch.get_button_value()
        long_press_value = self._switch.get_long_button_value()

        snapshots = [
            RawPeripheralSnapshot(
                source=self.source,
                timestamp=now,
                data={
                    "rotation": rotation,
                    "button_presses": button_value,
                    "long_press_count": long_press_value,
                },
            )
        ]

        actions: list[ActionEvent] = []
        rotation_delta = rotation - self._last_rotation
        if rotation_delta:
            actions.append(
                ActionEvent(
                    action="switch.rotation",
                    payload={"delta": rotation_delta, "value": rotation},
                    source=self.source,
                    timestamp=now,
                )
            )
            self._rotation_history.append((now, abs(rotation_delta)))
            self._last_rotation = rotation

        button_delta = button_value - self._last_button
        if button_delta > 0:
            actions.append(
                ActionEvent(
                    action="switch.button.press",
                    payload={"count": button_value, "delta": button_delta},
                    source=self.source,
                    timestamp=now,
                )
            )
        elif button_delta < 0:
            logger.debug("Switch button count decreased unexpectedly", extra={"delta": button_delta})
        self._last_button = button_value

        long_press_delta = long_press_value - self._last_long_press
        if long_press_delta > 0:
            actions.append(
                ActionEvent(
                    action="switch.button.long_press",
                    payload={"count": long_press_value, "delta": long_press_delta},
                    source=self.source,
                    timestamp=now,
                )
            )
        self._last_long_press = long_press_value

        window_seconds = self.config.switch_rotation_window
        threshold = self.config.switch_rotation_threshold
        if threshold > 0 and window_seconds > 0:
            while self._rotation_history and now - self._rotation_history[0][0] > window_seconds:
                self._rotation_history.popleft()
            aggregate_delta = sum(delta for _, delta in self._rotation_history)
            if aggregate_delta >= threshold:
                actions.append(
                    ActionEvent(
                        action="switch.rotation.aggregate",
                        payload={
                            "window_s": window_seconds,
                            "total_delta": aggregate_delta,
                        },
                        source=self.source,
                        timestamp=now,
                    )
                )
                self._rotation_history.clear()

        return PeripheralPollResult(raw_snapshots=snapshots, action_events=actions)


class BluetoothSwitchActionMapper(SwitchActionMapper):
    def __init__(
        self, switch: BluetoothSwitch, source: str, config: PeripheralServiceConfig
    ) -> None:
        super().__init__(switch, source, config)
        self._bt_switch = switch
        self._was_connected = switch.connected

    def poll(self) -> PeripheralPollResult:
        result = super().poll()
        now = time.time()
        connected = self._bt_switch.connected
        if connected != self._was_connected:
            result.action_events.append(
                ActionEvent(
                    action="switch.bluetooth.connection",
                    payload={"connected": connected},
                    source=self.source,
                    timestamp=now,
                )
            )
            self._was_connected = connected
        return result


class GamepadActionMapper(PeripheralActionMapper):
    def __init__(self, gamepad: Gamepad, source: str, config: PeripheralServiceConfig) -> None:
        super().__init__(source, config)
        self._gamepad = gamepad
        self._last_connected = gamepad.is_connected()
        self._button_states: dict[int, bool] = {}
        self._axis_states: dict[int, float] = {}
        self._dpad_state = (0, 0)

    def poll(self) -> PeripheralPollResult:
        now = time.time()
        self._gamepad.update()
        connected = self._gamepad.is_connected()

        actions: list[ActionEvent] = []
        buttons_state: dict[str, bool] = {}
        axes_state: dict[str, float] = {}

        if connected:
            num_buttons = self._gamepad.num_buttons or 0
            for button_id in range(num_buttons):
                held = self._gamepad.is_held(button_id)
                buttons_state[str(button_id)] = held
                previous = self._button_states.get(button_id, False)
                if held and not previous:
                    actions.append(
                        ActionEvent(
                            action="gamepad.button.down",
                            payload={"button": button_id},
                            source=self.source,
                            timestamp=now,
                        )
                    )
                if not held and previous:
                    actions.append(
                        ActionEvent(
                            action="gamepad.button.up",
                            payload={"button": button_id},
                            source=self.source,
                            timestamp=now,
                        )
                    )
                if self._gamepad.was_tapped(button_id):
                    actions.append(
                        ActionEvent(
                            action="gamepad.button.tap",
                            payload={"button": button_id},
                            source=self.source,
                            timestamp=now,
                        )
                    )

            num_axes = self._gamepad.num_axes or 0
            threshold = max(0.0, self.config.axis_threshold)
            for axis_id in range(num_axes):
                value = self._gamepad.axis_value(axis_id)
                axes_state[str(axis_id)] = value
                previous = self._axis_states.get(axis_id, 0.0)
                if threshold > 0 and self._crossed_threshold(previous, value, threshold):
                    actions.append(
                        ActionEvent(
                            action="gamepad.axis.threshold",
                            payload={"axis": axis_id, "value": value},
                            source=self.source,
                            timestamp=now,
                        )
                    )
        else:
            buttons_state = {str(button): False for button in self._button_states}
            axes_state = {str(axis): 0.0 for axis in self._axis_states}

        dpad = self._gamepad.get_dpad_value() if connected else (0, 0)
        if dpad != self._dpad_state:
            actions.append(
                ActionEvent(
                    action="gamepad.dpad.move",
                    payload={"value": dpad},
                    source=self.source,
                    timestamp=now,
                )
            )
            self._dpad_state = dpad

        if connected != self._last_connected:
            actions.append(
                ActionEvent(
                    action="gamepad.connection",
                    payload={"connected": connected},
                    source=self.source,
                    timestamp=now,
                )
            )
            self._last_connected = connected

        self._button_states = {int(k): v for k, v in buttons_state.items()}
        self._axis_states = {int(k): v for k, v in axes_state.items()}

        snapshot = RawPeripheralSnapshot(
            source=self.source,
            timestamp=now,
            data={
                "connected": connected,
                "buttons": buttons_state,
                "axes": axes_state,
                "dpad": dpad,
            },
        )
        return PeripheralPollResult(raw_snapshots=[snapshot], action_events=actions)

    @staticmethod
    def _crossed_threshold(previous: float, current: float, threshold: float) -> bool:
        crossed_high = abs(previous) < threshold <= abs(current)
        crossed_low = abs(previous) >= threshold > abs(current)
        return crossed_high or crossed_low


class AccelerometerActionMapper(PeripheralActionMapper):
    def __init__(
        self, accelerometer: Accelerometer, source: str, config: PeripheralServiceConfig
    ) -> None:
        super().__init__(source, config)
        self._accelerometer = accelerometer
        self._magnitude_history: Deque[tuple[float, float]] = deque()
        self._aggregate_triggered = False

    def poll(self) -> PeripheralPollResult:
        now = time.time()
        acceleration = self._accelerometer.get_acceleration()
        if acceleration is None:
            return PeripheralPollResult.empty()

        magnitude = math.sqrt(
            acceleration.x**2 + acceleration.y**2 + acceleration.z**2
        )
        self._magnitude_history.append((now, magnitude))

        window_seconds = max(0.0, self.config.accelerometer_window)
        while self._magnitude_history and now - self._magnitude_history[0][0] > window_seconds:
            self._magnitude_history.popleft()

        actions: list[ActionEvent] = []
        threshold = max(0.0, self.config.accelerometer_magnitude_threshold)
        if magnitude >= threshold > 0:
            actions.append(
                ActionEvent(
                    action="accelerometer.magnitude",
                    payload={"instant": magnitude},
                    source=self.source,
                    timestamp=now,
                )
            )

        avg_magnitude = sum(v for _, v in self._magnitude_history) / max(
            1, len(self._magnitude_history)
        )
        if threshold > 0:
            if avg_magnitude >= threshold and not self._aggregate_triggered:
                actions.append(
                    ActionEvent(
                        action="accelerometer.magnitude.aggregate",
                        payload={
                            "average": avg_magnitude,
                            "window_s": window_seconds,
                        },
                        source=self.source,
                        timestamp=now,
                    )
                )
                self._aggregate_triggered = True
            elif avg_magnitude < threshold * 0.8:
                self._aggregate_triggered = False

        snapshot = RawPeripheralSnapshot(
            source=self.source,
            timestamp=now,
            data={
                "x": acceleration.x,
                "y": acceleration.y,
                "z": acceleration.z,
                "magnitude": magnitude,
                "avg_magnitude": avg_magnitude,
            },
        )
        return PeripheralPollResult(raw_snapshots=[snapshot], action_events=actions)


class HeartRateActionMapper(PeripheralActionMapper):
    def __init__(
        self, source: str, config: PeripheralServiceConfig
    ) -> None:
        super().__init__(source, config)
        self._history: dict[str, Deque[tuple[float, int]]] = {}
        self._alert_state: dict[str, bool] = {}
        self._known_devices: set[str] = set()

    def poll(self) -> PeripheralPollResult:
        now = time.time()
        with heart_rate_mutex:
            bpm_snapshot = dict(current_bpms)
            battery_snapshot = dict(battery_status)
            last_seen_snapshot = dict(last_seen)

        actions: list[ActionEvent] = []

        new_devices = set(bpm_snapshot) - self._known_devices
        for device_id in new_devices:
            actions.append(
                ActionEvent(
                    action="heart_rate.device_seen",
                    payload={"device_id": device_id},
                    source=self.source,
                    timestamp=now,
                )
            )
        lost_devices = self._known_devices - set(bpm_snapshot)
        for device_id in lost_devices:
            actions.append(
                ActionEvent(
                    action="heart_rate.device_lost",
                    payload={"device_id": device_id},
                    source=self.source,
                    timestamp=now,
                )
            )
            self._history.pop(device_id, None)
            self._alert_state.pop(device_id, None)
        self._known_devices = set(bpm_snapshot)

        window_seconds = max(0.0, self.config.heart_rate_window)
        threshold = max(0, self.config.heart_rate_high_threshold)

        for device_id, bpm in bpm_snapshot.items():
            history = self._history.setdefault(device_id, deque())
            history.append((now, bpm))
            while history and now - history[0][0] > window_seconds:
                history.popleft()

            average = sum(value for _, value in history) / max(1, len(history))
            triggered = self._alert_state.get(device_id, False)
            if threshold > 0 and average >= threshold and not triggered:
                actions.append(
                    ActionEvent(
                        action="heart_rate.threshold",
                        payload={
                            "device_id": device_id,
                            "average_bpm": average,
                            "window_s": window_seconds,
                        },
                        source=self.source,
                        timestamp=now,
                    )
                )
                self._alert_state[device_id] = True
            elif triggered and average < threshold * 0.9:
                self._alert_state[device_id] = False

        snapshot = RawPeripheralSnapshot(
            source=self.source,
            timestamp=now,
            data={
                "bpm": bpm_snapshot,
                "battery": battery_snapshot,
                "last_seen": last_seen_snapshot,
            },
        )
        return PeripheralPollResult(raw_snapshots=[snapshot], action_events=actions)


class PhoneTextActionMapper(PeripheralActionMapper):
    def __init__(
        self, phone_text: PhoneText, source: str, config: PeripheralServiceConfig
    ) -> None:
        super().__init__(source, config)
        self._phone_text = phone_text
        self._message_index = 0

    def poll(self) -> PeripheralPollResult:
        now = time.time()
        text = self._phone_text.pop_text()
        last_text = self._phone_text.get_last_text()

        if text is None and last_text is None:
            return PeripheralPollResult.empty()

        actions: list[ActionEvent] = []
        if text is not None:
            self._message_index += 1
            actions.append(
                ActionEvent(
                    action="phone_text.received",
                    payload={
                        "text": text,
                        "message_index": self._message_index,
                    },
                    source=self.source,
                    timestamp=now,
                )
            )
            last_text = text

        snapshot = RawPeripheralSnapshot(
            source=self.source,
            timestamp=now,
            data={
                "text": last_text,
                "message_index": self._message_index,
                "has_new": text is not None,
            },
        )
        return PeripheralPollResult(raw_snapshots=[snapshot], action_events=actions)


def build_action_mappers(
    peripheral: object, source: str, config: PeripheralServiceConfig
) -> Iterable[PeripheralActionMapper]:
    if isinstance(peripheral, BluetoothSwitch):
        yield BluetoothSwitchActionMapper(peripheral, source, config)
    elif isinstance(peripheral, BaseSwitch):
        yield SwitchActionMapper(peripheral, source, config)
    elif isinstance(peripheral, Gamepad):
        yield GamepadActionMapper(peripheral, source, config)
    elif isinstance(peripheral, Accelerometer):
        yield AccelerometerActionMapper(peripheral, source, config)
    elif isinstance(peripheral, PhoneText):
        yield PhoneTextActionMapper(peripheral, source, config)
    else:
        from heart.peripheral.heart_rates import HeartRateManager

        if isinstance(peripheral, HeartRateManager):
            yield HeartRateActionMapper(source, config)
        else:
            logger.debug("No action mapper registered for peripheral", extra={"type": type(peripheral).__name__})
