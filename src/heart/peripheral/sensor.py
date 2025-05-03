import collections
import json
import time
from dataclasses import dataclass
from typing import Iterator, NoReturn, Self

import serial

from heart.peripheral import Peripheral
from heart.utilities.env import get_device_ports


@dataclass
class Acceleration:
    x: float
    y: float
    z: float


# TODO (lampe): This is fundamentally useless right now
class Distribution:
    def __init__(self) -> None:
        self.historic_values = collections.deque([], maxlen=100)

    def _get_time(self) -> float:
        return time.monotonic()

    def add_value(self, value: float):
        self.historic_values.append((self._get_time(), value))


class   Accelerometer(Peripheral):
    def __init__(self, port: str, baudrate: int, *args, **kwargs) -> None:
        self.acceleration_value = None
        self.port = port
        self.baudrate = baudrate

        self.x_distribution = Distribution()
        self.y_distribution = Distribution()
        self.z_distribution = Distribution()

        super().__init__(*args, **kwargs)

    @classmethod
    def detect(cls) -> Iterator[Self]:
        return [
            Accelerometer(port=port, baudrate=115200)
            for port in get_device_ports("usb-Adafruit_KB2040")
        ]

    def _connect_to_ser(self) -> serial.Serial:
        return serial.Serial(self.port, self.baudrate)

    def run(self) -> NoReturn:
        # If it crashes, try to re-connect
        while True:
            try:
                ser = self._connect_to_ser()
                try:
                    while True:
                        data = ser.readlines(ser.in_waiting or 1)
                        for datum in data:
                            self._process_data(data=datum)
                except KeyboardInterrupt:
                    print("Program terminated")
                except Exception:
                    pass
                finally:
                    ser.close()
            except Exception:
                pass

    def _process_data(self, data: bytes) -> None:
        bus_data = data.decode("utf-8").rstrip()
        if not bus_data or not bus_data.startswith("{"):
            # TODO: This happens on first connect due to some weird `b'\x1b]0;\xf0\x9f\x90\x8dcode.py | 9.2.7\x1b\\` bytes
            return

        data = json.loads(bus_data)
        self._update_due_to_data(data)

    def get_acceleration(self) -> Acceleration | None:
        if self.acceleration_value is None:
            return None
        return Acceleration(
            self.acceleration_value["x"],
            self.acceleration_value["y"],
            self.acceleration_value["z"],
        )

    def _update_due_to_data(self, data: dict) -> None:
        event_type = data["event_type"]
        data_value = data["data"]

        if event_type == "acceleration" or event_type == "sensor.acceleration":
            self.acceleration_value = data_value
            self.x_distribution.add_value(data_value["x"])
            self.y_distribution.add_value(data_value["y"])
            self.z_distribution.add_value(data_value["z"])
