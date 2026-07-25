from __future__ import annotations

from collections.abc import Callable

from manyfold import Subscribable
from manyfold.architecture import PubSubCallbackSubscription

from heart.peripheral.core.input.gamepad import (
    DEFAULT_GAMEPAD_AXIS_DEAD_ZONE, GamepadAxis, GamepadController,
    GamepadSnapshotEvent, GamepadStickValue)
from heart.peripheral.core.input.keyboard import (KeyboardController,
                                                  KeyboardSnapshot)


class ControlSurface:
    """Read or observe the centrally polled input state."""

    def __init__(
        self,
        keyboard: KeyboardController,
        gamepad: GamepadController,
    ) -> None:
        self._keyboard = keyboard
        self._gamepad = gamepad

    def keyboard(self) -> KeyboardSnapshot:
        return self._keyboard.latest()

    def gamepads(self) -> tuple[GamepadSnapshotEvent, ...]:
        return self._gamepad.latest()

    def on_stick_move(
        self,
        callback: Callable[[GamepadStickValue], object],
        *,
        stick: str = "left",
        dead_zone: float = DEFAULT_GAMEPAD_AXIS_DEAD_ZONE,
    ) -> PubSubCallbackSubscription:
        x_axis, y_axis = _stick_axes(stick)
        return self._gamepad_state().subscribe(
            lambda events: _emit_stick_moves(
                events,
                callback=callback,
                x_axis=x_axis,
                y_axis=y_axis,
                dead_zone=dead_zone,
            )
        )

    def _gamepad_state(self) -> Subscribable[tuple[GamepadSnapshotEvent, ...]]:
        return self._gamepad.state_stream()


def _stick_axes(stick: str) -> tuple[GamepadAxis, GamepadAxis]:
    if stick == "left":
        return GamepadAxis.LEFT_X, GamepadAxis.LEFT_Y
    if stick == "right":
        return GamepadAxis.RIGHT_X, GamepadAxis.RIGHT_Y
    raise ValueError(f"Unknown gamepad stick {stick!r}; expected 'left' or 'right'")


def _emit_stick_moves(
    events: tuple[GamepadSnapshotEvent, ...],
    *,
    callback: Callable[[GamepadStickValue], object],
    x_axis: GamepadAxis,
    y_axis: GamepadAxis,
    dead_zone: float,
) -> None:
    for event in events:
        value = GamepadStickValue(
            x=event.snapshot.axis_value(x_axis, dead_zone=dead_zone),
            y=event.snapshot.axis_value(y_axis, dead_zone=dead_zone),
        )
        if value.x != 0.0 or value.y != 0.0:
            callback(value)
