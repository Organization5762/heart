import itertools
import threading
from dataclasses import dataclass
from enum import StrEnum
from typing import Iterator

from heart.peripheral import Peripheral
from heart.peripheral.gamepad import Gamepad
from heart.peripheral.heart_rates import HeartRateManager
from heart.peripheral.sensor import Accelerometer
from heart.peripheral.switch import BaseSwitch, BluetoothSwitch, FakeSwitch, Switch
from heart.peripheral.phyphox import Phyphox
from heart.utilities.env import Configuration


class NotificationService:
    def start_notify(on_value_change) -> None:
        pass


@dataclass
class Device:
    device_id: str
    device_type: "Device.Types"

    class Types(StrEnum):
        # TODO: Still need to work our this handling
        ACCELEROMETER = "ACCELEROMETER"
        ROTARY_ENCODER = "ROTARY_ENCODER"
        BLUETOOTH_BRIDGE = "BLUETOOTH_BRIDGE"


class PeripheralManager:
    def __init__(self) -> None:
        self.peripheral: list[Peripheral] = []
        self._deprecated_main_switch: BaseSwitch | None = None
        self._threads: list[threading.Thread] = []

        # TODO: I think this is something I want to support as it simplifies
        # pushing state around in some ways
        self.notification_service = NotificationService()
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
                target=peripherial_run_fn, daemon=True
            )
            peripherial_thread.start()

            self._threads.append(peripherial_thread)

    def _detect_switches(self) -> Iterator[Peripheral]:
        if Configuration.is_pi():
            switches = itertools.chain(
                Switch.detect(),
                BluetoothSwitch.detect(),
            )
            # If no switches are found this probably means they're not plugged in, just use a fake switch
            switches_list = list(switches)
            if len(switches_list) == 0:
                switches = FakeSwitch.detect()
            else:
                switches = switches_list
        else:
            switches = FakeSwitch.detect()

        for switch in switches:
            if self._deprecated_main_switch is None:
                self._deprecated_main_switch = switch
            yield switch

    def _detect_sensors(self) -> Iterator[Peripheral]:
        yield from itertools.chain(Accelerometer.detect(), Phyphox.detect())

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
