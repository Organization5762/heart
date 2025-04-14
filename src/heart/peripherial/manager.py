
from dataclasses import dataclass
from enum import StrEnum
import itertools
import threading
from typing import Iterator

from heart.peripherial import Peripherial
from heart.peripherial.sensor import Accelerometer
from heart.peripherial.switch import BaseSwitch, BluetoothSwitch, FakeSwitch, Switch
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

class PeripherialManager:
    def __init__(self) -> None:
        self.peripherials: list[Peripherial] = []
        self._deprecated_main_switch: BaseSwitch | None = None
        self._threads: list[threading.Thread]  = []

        # TODO: I think this is something I want to support as it simplifies
        # pushing state around in some ways
        self.notification_service = NotificationService()
        self.started = False
    
    def detect(self) -> None:
        peripherials = itertools.chain(
            self._detect_switches(),
            self._detect_sensors()
        )

        for peripherial in peripherials:
            self._register_peripherial(peripherial=peripherial)
            

    def start(self) -> None:
        if self.started:
            raise ValueError("Manager has already been started")

        self.started = True
        for peripherial in self.peripherials:
            # TODO (lampe): Should likely keep a handle on all these threads
            def peripherial_run_fn() -> None:
                peripherial.run()

            # TODO: Doing the threading automatically might cause issues with the local switch?
            peripherial_thread = threading.Thread(target=peripherial_run_fn, daemon=True)
            peripherial_thread.start()

            self._threads.append(peripherial_thread)

    def _detect_switches(self) -> Iterator[Peripherial]:
        if Configuration.is_pi():
            switches = itertools.chain(
                Switch.detect(),
                BluetoothSwitch.detect(),
            )
        else:
            switches = FakeSwitch.detect()

        for switch in switches:
            if self._deprecated_main_switch is None:
                self._deprecated_main_switch = switch
            yield switch

    def _detect_sensors(self) -> Iterator[Peripherial]:
        yield from itertools.chain(
            Accelerometer.detect()
        )
        
    def _register_peripherial(self, peripherial: Peripherial) -> None:
        self.peripherials.append(peripherial)

    def _deprecated_get_main_switch(self):
        """
        Added this to make the legacy conversion easier, SwitchSubscriber is now subsumed by this.
        """
        if self._deprecated_main_switch is None:
            raise Exception("Unable to get switch as it has not been registered")
        
        return self._deprecated_main_switch
    
    def __del__(self) -> None:
        """
        Attempt to clean up threads and peripherals at object deletion time.
        This is not guaranteed to run in all scenarios; consider an explicit
        'close()' or context-manager approach for reliability.
        """
        for t in self._threads:
            if t.is_alive():
                try:
                    t.join(timeout=3.0)
                except Exception as e:
                    print(f"Error joining thread {t}: {e}")