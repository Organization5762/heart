from manyfold import StreamNode

from heart.device import Device
from heart.peripheral.core.input import (GamepadAxis, GamepadButton,
                                         GamepadSnapshot, GamepadSnapshotEvent)
from heart.peripheral.core.input.frame import FrameTick
from heart.peripheral.core.input.streams import average_by_frame_window
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import ObservableProvider
from heart.peripheral.sensor import Acceleration
from heart.renderers.water_cube.state import WaterCubeState

MIN_UPDATE_INTERVAL_MS = 100.0
MIN_ACCELERATION_AVERAGE = 0.08
MAX_ACCELERATION_AVERAGE = 1.0
ACCELERATION_AVERAGE_STEP = 0.15
HUE_STEP_DEGREES = 8.0


class WaterCubeStateProvider(ObservableProvider[WaterCubeState]):
    def __init__(
        self,
        device: Device,
        min_update_interval_ms: float = MIN_UPDATE_INTERVAL_MS,
    ):
        self.device = device
        self._min_update_interval_ms = min_update_interval_ms

    def observable(
        self, peripheral_manager: PeripheralManager | None = None
    ) -> StreamNode[WaterCubeState]:
        if peripheral_manager is None:
            msg = "WaterCubeStateProvider requires a PeripheralManager"
            raise ValueError(msg)
        initial = WaterCubeState.initial_state(self.device)
        acceleration = peripheral_manager.input_io.active_acceleration().start_with(
            None
        )
        frame_ticks = peripheral_manager.input_io.frame_tick_stream()
        average_acceleration = self._average_acceleration(acceleration, frame_ticks)
        samples = average_acceleration.map(
            lambda latest: (
                latest,
                peripheral_manager.input_io.gamepad.sample(
                    source="renderer.water_cube",
                ),
            )
        )
        return samples.scan(
            lambda prev, latest: self._advance_state(prev, latest),
            seed=initial,
        ).start_with(initial)

    def _average_acceleration(
        self,
        acceleration: StreamNode[Acceleration | None],
        frame_ticks: StreamNode[FrameTick],
    ) -> StreamNode[Acceleration]:
        average_x = average_by_frame_window(
            acceleration,
            frame_ticks,
            interval_ms=self._min_update_interval_ms,
            selector=lambda value: value.x,
        )
        average_y = average_by_frame_window(
            acceleration,
            frame_ticks,
            interval_ms=self._min_update_interval_ms,
            selector=lambda value: value.y,
        )
        average_z = average_by_frame_window(
            acceleration,
            frame_ticks,
            interval_ms=self._min_update_interval_ms,
            selector=lambda value: value.z,
        )
        return average_x.with_latest_from(average_y, average_z).map(
            lambda latest: Acceleration(x=latest[0], y=latest[1], z=latest[2])
        )

    def _advance_state(
        self,
        prev: WaterCubeState,
        latest: tuple[Acceleration | None, tuple[GamepadSnapshotEvent, ...]],
    ) -> WaterCubeState:
        acceleration, gamepads = latest
        acceleration_average = prev.acceleration_average
        water_hue_degrees = prev.water_hue_degrees
        for event in gamepads:
            acceleration_average = _next_acceleration_average(
                acceleration_average,
                event.snapshot,
            )
            water_hue_degrees = _next_water_hue(water_hue_degrees, event.snapshot)
        return prev._step(
            heights=prev.heights,
            velocities=prev.velocities,
            acceleration=acceleration,
            acceleration_average=acceleration_average,
            water_hue_degrees=water_hue_degrees,
        )


def _next_acceleration_average(current: float, gamepad: GamepadSnapshot) -> float:
    if not gamepad.connected:
        return current
    thinner = _trigger_pressure(gamepad.axis_value(GamepadAxis.TRIGGER_RIGHT))
    thicker = _trigger_pressure(gamepad.axis_value(GamepadAxis.TRIGGER_LEFT))
    delta = (thinner - thicker) * ACCELERATION_AVERAGE_STEP
    return _clamp(
        current + delta,
        minimum=MIN_ACCELERATION_AVERAGE,
        maximum=MAX_ACCELERATION_AVERAGE,
    )


def _next_water_hue(current: float, gamepad: GamepadSnapshot) -> float:
    if not gamepad.connected:
        return current
    delta = 0.0
    if gamepad.button_held(GamepadButton.ZR):
        delta += HUE_STEP_DEGREES
    if gamepad.button_held(GamepadButton.ZL):
        delta -= HUE_STEP_DEGREES
    return (current + delta) % 360.0


def _trigger_pressure(raw_value: float) -> float:
    return _clamp(raw_value, minimum=0.0, maximum=1.0)


def _clamp(value: float, *, minimum: float, maximum: float) -> float:
    return min(max(value, minimum), maximum)
