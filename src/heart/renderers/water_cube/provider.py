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
        accel = peripheral_manager.input_io.active_acceleration()

        def update_state(prev: WaterCubeState, acceleration: Acceleration):
            return prev._step(
                heights=prev.heights,
                velocities=prev.velocities,
                acceleration=acceleration,
            )

        initial = WaterCubeState.initial_state(self.device)
        return accel.start_with(initial).scan(update_state)
