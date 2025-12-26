from typing import Any, Iterable

import reactivex

from heart.peripheral.configuration import PeripheralConfiguration
from heart.peripheral.configuration_loader import PeripheralConfigurationLoader
from heart.peripheral.core import Peripheral
from heart.peripheral.core.streams import PeripheralStreams
from heart.peripheral.gamepad import Gamepad
from heart.peripheral.registry import PeripheralConfigurationRegistry
from heart.peripheral.switch import SwitchState
from heart.utilities.logging import get_logger

logger = get_logger(__name__)


class PeripheralManager:
    """Coordinate detection and execution of available peripherals."""

    def __init__(
        self,
        *,
        configuration: str | None = None,
        configuration_registry: PeripheralConfigurationRegistry | None = None,
        configuration_loader: PeripheralConfigurationLoader | None = None,
    ) -> None:
        self._peripherals: list[Peripheral[Any]] = []
        self._started = False
        if configuration_loader and (configuration or configuration_registry):
            raise ValueError(
                "Provide configuration_loader or configuration/configuration_registry, not both."
            )
        self._configuration_loader = configuration_loader or PeripheralConfigurationLoader(
            configuration=configuration,
            registry=configuration_registry,
        )
        self._streams = PeripheralStreams(self._iter_peripherals)

    @property
    def peripherals(self) -> tuple[Peripheral[Any], ...]:
        return tuple(self._peripherals)

    @property
    def configuration_loader(self) -> PeripheralConfigurationLoader:
        return self._configuration_loader

    @property
    def configuration_registry(self) -> PeripheralConfigurationRegistry:
        return self._configuration_loader.registry

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
        for detector in self._ensure_configuration().detectors:
            yield from detector()

    def _ensure_configuration(self) -> PeripheralConfiguration:
        return self._configuration_loader.load()

    def _iter_peripherals(self) -> Iterable[Peripheral[Any]]:
        return tuple(self._peripherals)

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
        return self._streams.event_bus()

    def get_main_switch_subscription(self) -> reactivex.Observable[SwitchState]:
        return self._streams.main_switch_subscription()

    @property
    def game_tick(self) -> reactivex.Subject[Any]:
        return self._streams.game_tick

    @property
    def window(self) -> reactivex.Subject[Any]:
        return self._streams.window

    @property
    def clock(self) -> reactivex.Subject[Any]:
        return self._streams.clock
