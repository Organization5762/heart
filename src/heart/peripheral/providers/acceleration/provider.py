import heart.utilities.reactive as reactive
from heart.peripheral.core.input import AccelerometerController
from heart.peripheral.core.providers import ObservableProvider
from heart.peripheral.sensor import Acceleration


class AllAccelerometersProvider(ObservableProvider[Acceleration]):
    """Compatibility adapter over the shared accelerometer controller."""

    def __init__(self, accelerometer_controller: AccelerometerController):
        self._controller = accelerometer_controller

    def observable(
        self, *args: object, **kwargs: object
    ) -> reactive.Observable[Acceleration]:
        return self._controller.node()
