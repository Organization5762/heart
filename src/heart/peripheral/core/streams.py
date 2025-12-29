from __future__ import annotations

from functools import cached_property
from typing import Any, Callable, Iterable

import reactivex
from reactivex import operators as ops
from reactivex.abc import SchedulerBase
from reactivex.subject.behaviorsubject import BehaviorSubject

from heart.peripheral.core import Peripheral, PeripheralMessageEnvelope
from heart.peripheral.switch import FakeSwitch, SwitchState
from heart.utilities.env import Configuration, ReactivexEventBusScheduler
from heart.utilities.reactivex_threads import (background_scheduler,
                                               input_scheduler,
                                               pipe_in_background)

PeripheralSource = Callable[[], Iterable[Peripheral[Any]]]


class PeripheralStreams:
    """Build shared reactive streams for detected peripherals."""

    def __init__(self, peripheral_source: PeripheralSource) -> None:
        self._peripheral_source = peripheral_source

    def event_bus(self) -> reactivex.Observable[Any]:
        event_sources = [peripheral.observe for peripheral in self._peripheral_source()]
        if not event_sources:
            event_bus = reactivex.empty()
        else:
            event_bus = reactivex.merge(*event_sources)
        return event_bus

    def main_switch_subscription(self) -> reactivex.Observable[SwitchState]:
        main_switches = [
            peripheral
            for peripheral in self._peripheral_source()
            if isinstance(peripheral, FakeSwitch)
        ]
        observables = [peripheral.observe for peripheral in main_switches]

        if not observables:
            return reactivex.empty()

        merged = pipe_in_background(
            reactivex.merge(*observables),
            ops.map(PeripheralMessageEnvelope[SwitchState].unwrap_peripheral)
        )
        return merged

    @cached_property
    def game_tick(self) -> reactivex.Subject[Any]:
        return BehaviorSubject[Any](None)

    @cached_property
    def window(self) -> reactivex.Subject[Any]:
        return BehaviorSubject[Any](None)

    @cached_property
    def clock(self) -> reactivex.Subject[Any]:
        return BehaviorSubject[Any](None)

    @staticmethod
    def _event_bus_scheduler() -> SchedulerBase | None:
        strategy = Configuration.reactivex_event_bus_scheduler()
        if strategy is ReactivexEventBusScheduler.BACKGROUND:
            return background_scheduler()
        if strategy is ReactivexEventBusScheduler.INPUT:
            return input_scheduler()
        return None
