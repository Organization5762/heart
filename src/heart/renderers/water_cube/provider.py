
import reactivex
from reactivex import operators as ops

from heart.peripheral.core.providers import ObservableProvider
from heart.peripheral.providers.acceleration import AllAccelerometersProvider
from heart.peripheral.sensor import Acceleration
from heart.renderers.water_cube.state import WaterCubeState


class WaterCubeStateProvider(ObservableProvider[WaterCubeState]):
    def __init__(self, accel_stream: AllAccelerometersProvider):
        self._accel_stream = accel_stream

    def observable(self) -> reactivex.Observable[WaterCubeState]:
        accel = self._accel_stream.observable()

        def update_state(prev: WaterCubeState, acceleration: Acceleration):
            return prev._step(
                heights=prev.heights,
                velocities=prev.velocities,
                acceleration=acceleration
            )

        initial = WaterCubeState.initial_state()

        return accel.pipe(
            ops.start_with(initial),
            ops.scan(update_state),
            ops.share(),
        )
