from __future__ import annotations

import itertools
import threading
from typing import Iterable, Iterator

from heart.peripheral.core import Peripheral
from heart.peripheral.gamepad import Gamepad
from heart.peripheral.heart_rates import HeartRateManager
from heart.peripheral.phone_text import PhoneText
from heart.peripheral.phyphox import Phyphox
from heart.peripheral.sensor import Accelerometer
from heart.peripheral.switch import BaseSwitch, BluetoothSwitch, FakeSwitch, Switch
from heart.utilities.env import Configuration
from heart.utilities.logging import get_logger

logger = get_logger(__name__)


class PeripheralManager:
    """Coordinate detection and execution of available peripherals."""

    def __init__(self) -> None:
        self._peripherals: list[Peripheral] = []
        self._deprecated_main_switch: BaseSwitch | None = None
        self._threads: list[threading.Thread] = []
        self._started = False

    @property
    def peripherals(self) -> tuple[Peripheral, ...]:
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

    def _iter_detected_peripherals(self) -> Iterable[Peripheral]:
        yield from itertools.chain(
            self._detect_switches(),
            self._detect_sensors(),
            self._detect_gamepads(),
            self._detect_heart_rate_sensor(),
            self._detect_phone_text(),
        )

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
        yield from itertools.chain(Accelerometer.detect())

    def _detect_gamepads(self) -> Iterator[Peripheral]:
        yield from itertools.chain(Gamepad.detect())

    def _detect_heart_rate_sensor(self) -> Iterator[Peripheral]:
        yield from itertools.chain(HeartRateManager.detect())

    def _register_peripheral(self, peripheral: Peripheral) -> None:
        self._peripherals.append(peripheral)

    def _deprecated_get_main_switch(self) -> BaseSwitch:
        """Added this to make the legacy conversion easier, SwitchSubscriber is now
        subsumed by this."""
        if self._deprecated_main_switch is None:
            raise Exception("Unable to get switch as it has not been registered")

        return self._deprecated_main_switch

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
