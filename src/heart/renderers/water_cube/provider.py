
import reactivex
from reactivex import operators as ops

from heart.device import Device
from heart.peripheral.core.input import (AccelerometerController,
                                         AccelerometerDebugProfile)
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import ObservableProvider
from heart.peripheral.sensor import Acceleration
from heart.renderers.water_cube.state import WaterCubeState
from heart.utilities.reactivex_threads import pipe_in_background


class WaterCubeStateProvider(ObservableProvider[WaterCubeState]):
    def __init__(
        self,
        accelerometer_controller: AccelerometerController,
        accelerometer_debug_profile: AccelerometerDebugProfile,
        device: Device,
    ):
        self._accelerometer_controller = accelerometer_controller
        self._accelerometer_debug_profile = accelerometer_debug_profile
        self.device = device

    def observable(
        self, peripheral_manager: PeripheralManager | None = None
    ) -> reactivex.Observable[WaterCubeState]:
        if self._accelerometer_debug_profile.should_use_debug_input():
            accel = self._accelerometer_debug_profile.observable()
        else:
            accel = self._accelerometer_controller.observable()

        def update_state(prev: WaterCubeState, acceleration: Acceleration):
            return prev._step(
                heights=prev.heights,
                velocities=prev.velocities,
                acceleration=acceleration
            )

        initial = WaterCubeState.initial_state(self.device)

        return pipe_in_background(
            accel,
            ops.start_with(initial),
            ops.scan(update_state),
            ops.share(),
        )
