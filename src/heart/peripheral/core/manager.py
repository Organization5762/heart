from functools import cached_property
from typing import Any, Iterable, TypeVar

import reactivex
from reactivex import operators as ops
from reactivex.abc import SchedulerBase
from reactivex.subject.behaviorsubject import BehaviorSubject

from heart.peripheral.configuration import PeripheralConfiguration
from heart.peripheral.core import Peripheral, PeripheralMessageEnvelope
from heart.peripheral.gamepad import Gamepad
from heart.peripheral.registry import PeripheralConfigurationRegistry
from heart.peripheral.switch import FakeSwitch, SwitchState
from heart.utilities.env import Configuration
from heart.utilities.logging import get_logger
from heart.utilities.reactivex_streams import share_stream
from heart.utilities.reactivex_threads import (background_scheduler,
                                               input_scheduler)

logger = get_logger(__name__)

T = TypeVar("T")
R = TypeVar("R")


class PeripheralManager:
    """Coordinate detection and execution of available peripherals."""

    def __init__(
        self,
        *,
        configuration: str | None = None,
        configuration_registry: PeripheralConfigurationRegistry | None = None,
    ) -> None:
        self._peripherals: list[Peripheral[Any]] = []
        self._started = False
        self._configuration_registry = (
            configuration_registry or PeripheralConfigurationRegistry()
        )
        self._configuration_name = (
            configuration or Configuration.peripheral_configuration()
        )
        self._configuration: PeripheralConfiguration | None = None

    @property
    def peripherals(self) -> tuple[Peripheral[Any], ...]:
        return tuple(self._peripherals)

    def get_gamepad(self) -> Gamepad:
        """Return the first detected gamepad."""

        for peripheral in self._peripherals:
            if isinstance(peripheral, Gamepad):
                return peripheral
        raise ValueError("No Gamepad peripheral registered")

    def detect(self) -> None:
        for peripheral in self._iter_detected_peripherals():
            self._register_peripheral(peripheral)

        self._ensure_configuration()

    def register(self, peripheral: Peripheral[Any]) -> None:
        """Manually register ``peripheral`` with the manager."""

        self._register_peripheral(peripheral)

    def _iter_detected_peripherals(self) -> Iterable[Peripheral[Any]]:
        configuration = self._ensure_configuration()
        for detector in configuration.detectors:
            yield from detector()

    def _ensure_configuration(self) -> PeripheralConfiguration:
        if self._configuration is None:
            self._configuration = self._load_configuration(self._configuration_name)
        return self._configuration

    def _load_configuration(self, name: str) -> PeripheralConfiguration:
        factory = self._configuration_registry.get(name)
        if factory is None:
            raise ValueError(f"Peripheral configuration '{name}' not found")
        logger.info("Loading peripheral configuration: %s", name)
        return factory()

    def start(self) -> None:
        if self._started:
            raise ValueError("Manager has already been started")

        self._started = True
        for peripheral in self._peripherals:
            logger.info(f"Attempting to start peripheral '{peripheral}'")
            peripheral.run()

    def _register_peripheral(self, peripheral: Peripheral[Any]) -> None:
        self._peripherals.append(peripheral)

    def get_event_bus(self) -> reactivex.Observable[Any]:
        event_sources = [peripheral.observe for peripheral in self.peripherals]
        if not event_sources:
            event_bus = reactivex.empty()
        else:
            event_bus = reactivex.merge(*event_sources)
        scheduler = self._event_bus_scheduler()
        if scheduler is not None:
            event_bus = event_bus.pipe(ops.observe_on(scheduler))
        return share_stream(event_bus, stream_name="PeripheralManager.event_bus")

    def get_main_switch_subscription(self) -> reactivex.Observable[SwitchState]:
        main_switches = [
            peripheral.observe
            for peripheral in self.peripherals
            if isinstance(peripheral, FakeSwitch)
        ]

        if not main_switches:
            return reactivex.empty()

        return reactivex.merge(*main_switches).pipe(
            ops.map(PeripheralMessageEnvelope[SwitchState].unwrap_peripheral)
        )

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
        if strategy == "background":
            return background_scheduler()
        if strategy == "input":
            return input_scheduler()
        return None
