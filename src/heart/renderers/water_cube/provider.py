from manyfold import StreamNode

from heart.device import Device
from heart.peripheral.core.input.frame import FrameTick
from heart.peripheral.core.input.streams import average_by_frame_window
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import ObservableProvider
from heart.peripheral.sensor import Acceleration
from heart.renderers.water_cube.state import WaterCubeState

MIN_UPDATE_INTERVAL_MS = 100.0


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
        acceleration = peripheral_manager.input_io.active_acceleration().start_with(None)
        frame_ticks = peripheral_manager.input_io.frame_tick_stream()
        average_acceleration = self._average_acceleration(acceleration, frame_ticks)
        return (
            average_acceleration
            .scan(
                lambda prev, latest: self._advance_state(prev, latest),
                seed=initial,
            )
            .start_with(initial)
        )

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
        self, prev: WaterCubeState, acceleration: Acceleration | None
    ) -> WaterCubeState:
        return prev._step(
            heights=prev.heights,
            velocities=prev.velocities,
            acceleration=acceleration,
        )
