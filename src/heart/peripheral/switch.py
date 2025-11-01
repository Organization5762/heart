import json
import time
from typing import Iterator, NoReturn, Self

import serial
from bleak.backends.device import BLEDevice

from heart.firmware_io.constants import BUTTON_LONG_PRESS, BUTTON_PRESS, SWITCH_ROTATION
from heart.peripheral.bluetooth import UartListener
from heart.peripheral.core import Input, Peripheral
from heart.utilities.env import get_device_ports
from heart.utilities.logging import get_logger

logger = get_logger(__name__)


class BaseSwitch(Peripheral):
    def __init__(self) -> None:
        self.rotational_value = 0

        self.button_value = 0
        self.rotation_value_at_last_button_press = self.rotational_value

        self.button_long_press_value = 0
        self.rotation_value_at_last_long_button_press = self.rotational_value

    def run(self) -> None:
        return

    def get_rotation_since_last_button_press(self) -> int:
        return self.rotational_value - self.rotation_value_at_last_button_press

    def get_rotation_since_last_long_button_press(self) -> int:
        return self.rotational_value - self.rotation_value_at_last_long_button_press

    def get_rotational_value(self) -> int:
        return self.rotational_value

    def get_button_value(self) -> int:
        return self.button_value

    def get_long_button_value(self) -> int:
        return self.button_long_press_value

    def handle_input(self, data: Input) -> None:
        if data.event_type == BUTTON_PRESS:
            self.button_value += int(data.data)
            # Button was pressed, update last_rotational_value
            self.rotation_value_at_last_button_press = self.rotational_value

        if data.event_type == BUTTON_LONG_PRESS:
            self.button_long_press_value += int(data.data)
            # Button was pressed, update last_rotational_value
            self.rotation_value_at_last_long_button_press = self.rotational_value

        if data.event_type == SWITCH_ROTATION:
            self.rotational_value = int(data.data)


class FakeSwitch(BaseSwitch):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    @classmethod
    def detect(cls) -> Iterator[Self]:
        yield cls()

    def run(self) -> None:
        return


class Switch(BaseSwitch):
    def __init__(self, port: str, baudrate: int, *args, **kwargs) -> None:
        self.port = port
        self.baudrate = baudrate
        super().__init__(*args, **kwargs)

    @classmethod
    def detect(cls) -> Iterator[Self]:
        for port in get_device_ports("usb-Adafruit_Industries_LLC_Rotary_Trinkey_M0"):
            yield cls(port=port, baudrate=115200)

    def _connect_to_ser(self):
        return serial.Serial(self.port, self.baudrate)

    def run(self) -> NoReturn:
        # If it crashes, try to re-connect
        while True:
            try:
                ser = self._connect_to_ser()
                try:
                    while True:
                        if ser.in_waiting > 0:
                            bus_data = ser.readline().decode("utf-8").rstrip()
                            data = json.loads(bus_data)
                            self.update_due_to_data(data)
                except KeyboardInterrupt:
                    print("Program terminated")
                except Exception:
                    pass
                finally:
                    ser.close()
            except Exception:
                pass

            time.sleep(0.1)


class BluetoothSwitch(BaseSwitch):
    def __init__(self, device: BLEDevice, *args, **kwargs) -> None:
        self.listener = UartListener(device=device)
        self.switches = [
            BaseSwitch(),
            BaseSwitch(),
            BaseSwitch(),
            BaseSwitch(),
        ]
        self.connected = False
        super().__init__(*args, **kwargs)

    def update_due_to_data(self, data: dict[str, int]) -> None:
        producer_id = data.get("producer_id", 0)
        self.switches[producer_id].update_due_to_data(data)

        # Update first producer as if it is the main switch
        if producer_id == 0:
            main_switch = self.switches[0]
            self.rotational_value = main_switch.rotational_value

            self.button_value = main_switch.button_value
            self.rotation_value_at_last_button_press = (
                main_switch.rotation_value_at_last_button_press
            )

            self.button_long_press_value = main_switch.button_long_press_value
            self.rotation_value_at_last_long_button_press = (
                main_switch.rotation_value_at_last_long_button_press
            )

    def switch_zero(self) -> BaseSwitch | None:
        if not self.connected:
            return None
        return self.switches[0]

    def switch_one(self) -> BaseSwitch | None:
        if not self.connected:
            return None
        return self.switches[1]

    def switch_two(self) -> BaseSwitch | None:
        if not self.connected:
            return None
        return self.switches[2]

    def switch_three(self) -> BaseSwitch | None:
        if not self.connected:
            return None
        return self.switches[3]

    @classmethod
    def detect(cls) -> Iterator[Self]:
        for device in UartListener._discover_devices():
            yield cls(device=device)

    def _connect_to_ser(self) -> None:
        return self.listener.start()

    def run(self) -> NoReturn:
        slow_poll = False
        number_of_retries_without_success = 0
        # If it crashes, try to re-connect
        while True:
            try:
                self._connect_to_ser()
                number_of_retries_without_success = 0
                slow_poll = False
                self.connected = True
                try:
                    while True:
                        for event in self.listener.consume_events():
                            self.update_due_to_data(event)
                        time.sleep(0.1)
                except KeyboardInterrupt:
                    print("Program terminated")
                except Exception:
                    self.connected = False
                    pass
                finally:
                    self.connected = False
                    self.listener.close()
            except Exception:
                self.connected = False
                number_of_retries_without_success += 1
                if number_of_retries_without_success > 5:
                    slow_poll = True

            time.sleep(30 if slow_poll else 5)
