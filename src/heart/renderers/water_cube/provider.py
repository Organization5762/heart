from manyfold import StreamNode

from heart.device import Device
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import ObservableProvider
from heart.peripheral.sensor import Acceleration
from heart.renderers.water_cube.state import WaterCubeState


class WaterCubeStateProvider(ObservableProvider[WaterCubeState]):
    def __init__(
        self,
        device: Device,
    ):
        self.device = device

    def observable(
        self, peripheral_manager: PeripheralManager | None = None
    ) -> StreamNode[WaterCubeState]:
        if peripheral_manager is None:
            msg = "WaterCubeStateProvider requires a PeripheralManager"
            raise ValueError(msg)
        initial = WaterCubeState.initial_state(self.device)
        acceleration = peripheral_manager.input_io.active_acceleration().start_with(None)
        frame_ticks = peripheral_manager.input_io.frame_tick_stream()
        return (
            frame_ticks.with_latest_from(acceleration)
            .scan(
                lambda prev, latest: self._advance_state(prev, latest[1]),
                seed=initial,
            )
            .start_with(initial)
        )

    def _advance_state(
        self, prev: WaterCubeState, acceleration: Acceleration | None
    ) -> WaterCubeState:
        return prev._step(
            heights=prev.heights,
            velocities=prev.velocities,
            acceleration=acceleration,
        )
