from __future__ import annotations

from dataclasses import replace

from manyfold import StreamNode

from heart.peripheral.core.input import (GamepadAxis, GamepadButton,
                                         GamepadSnapshot)
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import ObservableProvider
from heart.renderers.tixyland.state import TixylandState

MIN_SPEED_SCALE = 0.1
MAX_SPEED_SCALE = 4.0
SPEED_SCALE_STEP = 0.15
HUE_STEP_DEGREES = 8.0


class TixylandStateProvider(ObservableProvider[TixylandState]):
    def __init__(self, peripheral_manager: PeripheralManager) -> None:
        self._peripheral_manager = peripheral_manager

    def observable(
        self, peripheral_manager: PeripheralManager | None = None
    ) -> StreamNode[TixylandState]:
        frame_ticks = self._peripheral_manager.input_io.frame_tick_stream()
        initial_state = TixylandState()

        def advance_state(state: TixylandState, frame_tick: object) -> TixylandState:
            for event in self._peripheral_manager.input_io.gamepad.sample(
                source="renderer.tixyland",
            ):
                state = _apply_gamepad_controls(state, event.snapshot)
            delta_seconds = max(frame_tick.delta_ms, 0.0) / 1000
            return replace(
                state,
                time_seconds=state.time_seconds + delta_seconds * state.speed_scale,
            )

        return frame_ticks.scan(advance_state, seed=initial_state).start_with(
            initial_state
        )


def _apply_gamepad_controls(
    state: TixylandState,
    gamepad: GamepadSnapshot,
) -> TixylandState:
    if not gamepad.connected:
        return state
    speed_delta = (
        _trigger_pressure(gamepad.axis_value(GamepadAxis.TRIGGER_RIGHT))
        - _trigger_pressure(gamepad.axis_value(GamepadAxis.TRIGGER_LEFT))
    ) * SPEED_SCALE_STEP
    hue_delta = 0.0
    if gamepad.button_held(GamepadButton.ZR):
        hue_delta += HUE_STEP_DEGREES
    if gamepad.button_held(GamepadButton.ZL):
        hue_delta -= HUE_STEP_DEGREES
    return replace(
        state,
        speed_scale=_clamp(
            state.speed_scale + speed_delta,
            minimum=MIN_SPEED_SCALE,
            maximum=MAX_SPEED_SCALE,
        ),
        hue_degrees=(state.hue_degrees + hue_delta) % 360.0,
    )


def _trigger_pressure(raw_value: float) -> float:
    return _clamp(raw_value, minimum=0.0, maximum=1.0)


def _clamp(value: float, *, minimum: float, maximum: float) -> float:
    return min(max(value, minimum), maximum)
