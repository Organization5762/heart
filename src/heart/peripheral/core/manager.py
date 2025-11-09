import itertools
import threading
from types import MappingProxyType
from typing import Callable, Iterable, Iterator

from heart.peripheral.compass import Compass
from heart.peripheral.configuration import PeripheralConfiguration
from heart.peripheral.core import Peripheral
from heart.peripheral.core.event_bus import (EventBus,
                                             VirtualPeripheralDefinition,
                                             VirtualPeripheralHandle)
from heart.peripheral.drawing_pad import DrawingPad
from heart.peripheral.gamepad import Gamepad
from heart.peripheral.heart_rates import HeartRateManager
from heart.peripheral.led_matrix import LEDMatrixDisplay
from heart.peripheral.microphone import Microphone
from heart.peripheral.phone_text import PhoneText
from heart.peripheral.phyphox import Phyphox
from heart.peripheral.radio import RadioPeripheral
from heart.peripheral.registry import PeripheralConfigurationRegistry
from heart.peripheral.sensor import Accelerometer
from heart.peripheral.switch import (BaseSwitch, BluetoothSwitch, FakeSwitch,
                                     Switch, SwitchState)
from heart.utilities.env import Configuration
from heart.utilities.logging import get_logger

logger = get_logger(__name__)


class PeripheralManager:
    """Coordinate detection and execution of available peripherals."""

    def __init__(
        self,
        *,
        event_bus: EventBus | None = None,
        configuration: str | None = None,
        configuration_registry: PeripheralConfigurationRegistry | None = None,
    ) -> None:
        self._peripherals: list[Peripheral] = []
        self._deprecated_main_switch: BaseSwitch | None = None
        self._threads: list[threading.Thread] = []
        self._started = False
        self._event_bus = event_bus
        self._propagate_event_bus = event_bus is not None
        self._configuration_registry = (
            configuration_registry or PeripheralConfigurationRegistry()
        )
        self._configuration_name = (
            configuration or Configuration.peripheral_configuration()
        )
        self._configuration: PeripheralConfiguration | None = None
        self._virtual_peripheral_definitions: dict[str, VirtualPeripheralDefinition] = {}
        self._virtual_peripheral_handles: dict[str, VirtualPeripheralHandle] = {}

    @property
    def event_bus(self) -> EventBus | None:
        return self._event_bus

    def attach_event_bus(self, event_bus: EventBus, *, propagate: bool = True) -> None:
        """Register ``event_bus`` for peripherals managed by this instance."""

        previous_bus = self._event_bus
        if (
            previous_bus is not None
            and previous_bus is not event_bus
            and self._virtual_peripheral_handles
        ):
            for handle in tuple(self._virtual_peripheral_handles.values()):
                previous_bus.virtual_peripherals.remove(handle)
            self._virtual_peripheral_handles.clear()

        self._event_bus = event_bus
        self._propagate_event_bus = propagate
        if not propagate:
            return
        for peripheral in self._peripherals:
            self._attach_event_bus(peripheral, event_bus)
        self._synchronize_virtual_peripherals()

    @property
    def peripherals(self) -> tuple[Peripheral, ...]:
        return tuple(self._peripherals)

    @property
    def virtual_peripheral_definitions(self) -> MappingProxyType[str, VirtualPeripheralDefinition]:
        return MappingProxyType(dict(self._virtual_peripheral_definitions))

    def get_gamepad(self) -> Gamepad:
        """Return the first detected gamepad."""

        for peripheral in self._peripherals:
            if isinstance(peripheral, Gamepad):
                return peripheral
        raise ValueError("No Gamepad peripheral registered")

    def detect(self) -> None:
        for peripheral in self._iter_detected_peripherals():
            self._register_peripheral(peripheral)
        configuration = self._ensure_configuration()
        self._register_virtual_peripherals(configuration.virtual_peripherals)

    def register(self, peripheral: Peripheral) -> None:
        """Manually register ``peripheral`` with the manager."""

        self._register_peripheral(peripheral)

    def _iter_detected_peripherals(self) -> Iterable[Peripheral]:
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
        return factory(self)

    def _register_virtual_peripherals(
        self, definitions: Iterable[VirtualPeripheralDefinition]
    ) -> None:
        updated = False
        for definition in definitions:
            self._virtual_peripheral_definitions[definition.name] = definition
            updated = True
        if not updated:
            return
        self._synchronize_virtual_peripherals()

    def _synchronize_virtual_peripherals(self) -> None:
        if self._event_bus is None or not self._propagate_event_bus:
            return
        for definition in self._virtual_peripheral_definitions.values():
            self._bind_virtual_peripheral(definition)

    def _bind_virtual_peripheral(self, definition: VirtualPeripheralDefinition) -> None:
        if self._event_bus is None or not self._propagate_event_bus:
            return
        handle = self._virtual_peripheral_handles.get(definition.name)
        if handle is None:
            handle = self._event_bus.virtual_peripherals.register(definition)
            self._virtual_peripheral_handles[definition.name] = handle
            logger.info("Registered virtual peripheral %s", definition.name)
        else:
            self._event_bus.virtual_peripherals.update(handle, definition)
            logger.info("Updated virtual peripheral %s", definition.name)

    def start(self) -> None:
        if self._started:
            raise ValueError("Manager has already been started")

        self._started = True
        for peripheral in self._peripherals:
            logger.info("Starting peripheral thread for %s", type(peripheral).__name__)
            thread = threading.Thread(
                target=peripheral.run,
                daemon=True,
                name=f"Peripheral - {type(peripheral).__name__}",
            )
            thread.start()
            self._threads.append(thread)

    def _detect_switches(self) -> Iterator[Peripheral]:
        if Configuration.is_pi() and not Configuration.is_x11_forward():
            logger.info("Detecting switches")
            switches: list[Peripheral] = [
                *Switch.detect(),
                *BluetoothSwitch.detect(),
            ]
            logger.info("Found %d switches", len(switches))
            if len(switches) == 0:
                logger.warning("No switches found")
                switches = list(FakeSwitch.detect())
        else:
            logger.info("Not running on pi, using fake switch")
            switches = list(FakeSwitch.detect())

        for switch in switches:
            logger.info("Adding switch - %s", switch)

            if self._deprecated_main_switch is None and isinstance(switch, BaseSwitch):
                self._deprecated_main_switch = switch
            yield switch

    def _detect_phone_text(self) -> Iterator[Peripheral]:
        yield from itertools.chain(PhoneText.detect())

    def _detect_sensors(self) -> Iterator[Peripheral]:
        yield from itertools.chain(Accelerometer.detect(), Compass.detect())

    def _detect_gamepads(self) -> Iterator[Peripheral]:
        yield from itertools.chain(Gamepad.detect())

    def _detect_heart_rate_sensor(self) -> Iterator[Peripheral]:
        yield from itertools.chain(HeartRateManager.detect())

    def _detect_microphones(self) -> Iterator[Peripheral]:
        yield from itertools.chain(Microphone.detect())

    def _detect_drawing_pads(self) -> Iterator[Peripheral]:
        yield from itertools.chain(DrawingPad.detect())

    def _detect_radios(self) -> Iterator[Peripheral]:
        yield from itertools.chain(RadioPeripheral.detect())

    def _register_peripheral(self, peripheral: Peripheral) -> None:
        self._peripherals.append(peripheral)
        if self._event_bus is not None and self._propagate_event_bus:
            self._attach_event_bus(peripheral, self._event_bus)

    def get_led_matrix_display(self) -> LEDMatrixDisplay:
        for peripheral in self._peripherals:
            if isinstance(peripheral, LEDMatrixDisplay):
                return peripheral
        raise ValueError("No LEDMatrixDisplay peripheral registered")

    def _attach_event_bus(self, peripheral: Peripheral, event_bus: EventBus) -> None:
        attach = getattr(peripheral, "attach_event_bus", None)
        if callable(attach):
            try:
                attach(event_bus)
            except Exception:
                logger.exception(
                    "Failed to attach event bus to peripheral %s", type(peripheral).__name__
                )

    def _deprecated_get_main_switch(self) -> BaseSwitch:
        """Added this to make the legacy conversion easier, SwitchSubscriber is now
        subsumed by this."""
        if self._deprecated_main_switch is None:
            raise Exception("Unable to get switch as it has not been registered")

        return self._deprecated_main_switch

    def get_main_switch_state(self) -> SwitchState:
        """Return the latest state snapshot for the primary switch."""

        if self._deprecated_main_switch is None:
            raise RuntimeError("Main switch is not registered")
        return self._deprecated_main_switch.get_state()

    def subscribe_main_switch(
        self, callback: Callable[[SwitchState], None]
    ) -> Callable[[], None]:
        """Register ``callback`` for main switch state updates."""

        if self._deprecated_main_switch is None:
            raise RuntimeError("Main switch is not registered")
        return self._deprecated_main_switch.subscribe_state(callback)

    def bluetooth_switch(self) -> BluetoothSwitch | None:
        for p in self._peripherals:
            if isinstance(p, BluetoothSwitch):
                return p
        return None

    def get_heart_rate_peripheral(self) -> HeartRateManager:
        """There should be only one instance managing all the heart rate sensors."""
        for p in self._peripherals:
            if isinstance(p, HeartRateManager):
                return p
        raise ValueError("No HeartRateManager peripheral registered")

    def get_phyphox_peripheral(self) -> Phyphox:
        """There should be only one instance of Phyphox."""
        for p in self._peripherals:
            if isinstance(p, Phyphox):
                return p
        raise ValueError("No Phyphox peripheral registered")

    def get_accelerometer(self) -> Accelerometer:
        for p in self._peripherals:
            if isinstance(p, Accelerometer):
                return p
        raise ValueError("No Accelerometer peripheral registered")

    def get_phone_text(self) -> PhoneText:
        for p in self._peripherals:
            if isinstance(p, PhoneText):
                return p
        raise ValueError("No PhoneText peripheral registered")

    def close(self, join_timeout: float = 3.0) -> None:
        """Attempt to stop all background threads started by the manager."""

        for thread in self._threads:
            if thread.is_alive():
                logger.debug(
                    "Joining peripheral thread %s with timeout %.1f",
                    thread.name,
                    join_timeout,
                )
                try:
                    thread.join(timeout=join_timeout)
                except Exception:
                    logger.exception("Failed to join thread %s", thread.name)

    def __del__(self) -> None:
        """Attempt to clean up threads and peripherals at object deletion time.

        This is not guaranteed to run in all scenarios; consider an explicit 'close()'
        or context-manager approach for reliability.

        """
        self.close()
