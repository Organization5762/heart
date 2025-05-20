import itertools
import threading
from dataclasses import dataclass
from enum import StrEnum
from typing import Iterator

from heart.peripheral.core import Peripheral
from heart.peripheral.gamepad import Gamepad
from heart.peripheral.heart_rates import HeartRateManager
from heart.peripheral.phyphox import Phyphox
from heart.peripheral.sensor import Accelerometer
from heart.peripheral.switch import BaseSwitch, BluetoothSwitch, FakeSwitch, Switch
from heart.utilities.env import Configuration
from heart.utilities.logging import get_logger

logger = get_logger(__name__)


class PeripheralManager:
    def __init__(self) -> None:
        self.peripheral: list[Peripheral] = []
        self._deprecated_main_switch: BaseSwitch | None = None
        self._threads: list[threading.Thread] = []

        self.started = False

    def get_gamepad(self) -> Gamepad:
        # todo: we're just assuming there's at most one gamepad plugged in and hence
        #  always exactly one Gamepad entry point. could generalize to more
        gamepads = [
            peripheral
            for peripheral in self.peripheral
            if isinstance(peripheral, Gamepad)
        ]
        return gamepads[0]

    def detect(self) -> None:
        peripherials = itertools.chain(
            self._detect_switches(),
            self._detect_sensors(),
            self._detect_gamepads(),
            self._detect_heart_rate_sensor(),
        )

        for peripherial in peripherials:
            self._register_peripherial(peripherial=peripherial)

    def start(self) -> None:
        if self.started:
            raise ValueError("Manager has already been started")

        self.started = True
        for peripherial in self.peripheral:
            # TODO (lampe): Should likely keep a handle on all these threads
            def peripherial_run_fn() -> None:
                peripherial.run()

            # TODO: Doing the threading automatically might cause issues with the local switch?
            peripherial_thread = threading.Thread(
                target=peripherial_run_fn,
                daemon=True,
                name=f"Peripherial - {type(peripherial).__name__}",
            )
            peripherial_thread.start()

            self._threads.append(peripherial_thread)

    def _detect_switches(self) -> Iterator[Peripheral]:
        if Configuration.is_pi() and not Configuration.is_x11_forward():
            logger.info("Detecting switches")
            switches = itertools.chain(
                Switch.detect(),
                BluetoothSwitch.detect(),
            )
            switches = list(switches)
            logger.info("Found %d switches", len(switches))
        else:
            logger.info("Not running on pi, using fake switch")
            switches = list(FakeSwitch.detect())

        for switch in switches:
            logger.info(f"Adding switch - {switch}")
            if self._deprecated_main_switch is None:
                self._deprecated_main_switch = switch
            yield switch

    def _detect_sensors(self) -> Iterator[Peripheral]:
        yield from itertools.chain(Accelerometer.detect())

    def _detect_gamepads(self) -> Iterator[Peripheral]:
        yield from itertools.chain(Gamepad.detect())

    def _detect_heart_rate_sensor(self) -> Iterator[Peripheral]:
        yield from itertools.chain(HeartRateManager.detect())

    def _register_peripherial(self, peripherial: Peripheral) -> None:
        self.peripheral.append(peripherial)

    def _deprecated_get_main_switch(self) -> BaseSwitch:
        """Added this to make the legacy conversion easier, SwitchSubscriber is now
        subsumed by this."""
        if self._deprecated_main_switch is None:
            raise Exception("Unable to get switch as it has not been registered")

        return self._deprecated_main_switch

    def get_heart_rate_peripheral(self) -> HeartRateManager:
        """There should be only one instance managing all the heart rate sensors."""
        for p in self.peripheral:
            if isinstance(p, HeartRateManager):
                return p
        raise ValueError("No HeartRateManager peripheral registered")

    def get_phyphox_peripheral(self) -> Phyphox:
        """There should be only one instance of Phyphox."""
        for p in self.peripheral:
            if isinstance(p, Phyphox):
                return p
        raise ValueError("No Phyphox peripheral registered")

    def get_accelerometer(self) -> Accelerometer:
        for p in self.peripheral:
            if isinstance(p, Accelerometer):
                return p
        raise ValueError("No Accelerometer peripheral registered")

    def __del__(self) -> None:
        """Attempt to clean up threads and peripherals at object deletion time.

        This is not guaranteed to run in all scenarios; consider an explicit 'close()'
        or context-manager approach for reliability.

        """
        for t in self._threads:
            if t.is_alive():
                try:
                    t.join(timeout=3.0)
                except Exception as e:
                    print(f"Error joining thread {t}: {e}")
