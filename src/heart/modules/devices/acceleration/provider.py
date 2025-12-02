import random
from datetime import timedelta

import reactivex

from heart.peripheral.core import PeripheralWrapper
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

        if len(accels) > 0:
            return reactivex.merge(*accels).pipe(
                ops.map(PeripheralWrapper[Acceleration | None].unwrap_peripheral)
            )
        else:
            def random_accel(x):
                return Acceleration(
                    x=random.random(),
                    y=random.random(),
                    z=9.8,
                )
            # Fake value
            return reactivex.interval(timedelta(milliseconds=5)).pipe(
                ops.map(random_accel)
            )