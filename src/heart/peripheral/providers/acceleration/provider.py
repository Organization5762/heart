from collections.abc import Callable
from typing import TypeGuard, cast

import reactivex
from reactivex import operators as ops

from heart.peripheral.core import PeripheralMessageEnvelope
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import ObservableProvider
from heart.peripheral.sensor import Acceleration, Accelerometer


class AllAccelerometersProvider(ObservableProvider[Acceleration]):
    """Provides an observable of Acceleration readings."""

    def __init__(self, peripheral_manager: PeripheralManager):
        self._pm = peripheral_manager

    def observable(self) -> reactivex.Observable[Acceleration]:
        accels = [
            peripheral.observe
            for peripheral in self._pm.peripherals
            if isinstance(peripheral, Accelerometer)
        ]

        def unwrap_acceleration(
            envelope: PeripheralMessageEnvelope[Acceleration | None],
        ) -> Acceleration | None:
            return envelope.data

        def is_acceleration(accel: Acceleration | None) -> TypeGuard[Acceleration]:
            return accel is not None

        def filter_acceleration(
            source: reactivex.Observable[Acceleration | None],
        ) -> reactivex.Observable[Acceleration]:
            return source.pipe(
                ops.filter(is_acceleration),
                ops.map(lambda accel: cast(Acceleration, accel)),
            )

        merged = cast(
            reactivex.Observable[PeripheralMessageEnvelope[Acceleration | None]],
            reactivex.merge(*accels),
        )
        map_op: Callable[
            [reactivex.Observable[PeripheralMessageEnvelope[Acceleration | None]]],
            reactivex.Observable[Acceleration | None],
        ] = ops.map(unwrap_acceleration)
        return merged.pipe(
            map_op,
            filter_acceleration,
        )
