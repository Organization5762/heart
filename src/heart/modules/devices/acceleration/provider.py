
import reactivex

from heart.peripheral.core import PeripheralMessageEnvelope
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import ObservableProvider
from heart.peripheral.sensor import Acceleration, Accelerometer
from heart.peripheral.uwb import ops


class AllAccelerometersProvider(ObservableProvider[Acceleration]):
    """Provides an observable of Acceleration readings."""
    def __init__(self, peripheral_manager: PeripheralManager):
        self._pm = peripheral_manager

    def observable(self) -> reactivex.Observable[Acceleration]:
        accels = [peripheral.observe for peripheral in self._pm.peripherals if isinstance(peripheral, Accelerometer)]

        return reactivex.merge(*accels).pipe(
            ops.map(PeripheralMessageEnvelope[Acceleration | None].unwrap_peripheral)
        )