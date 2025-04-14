import collections
from dataclasses import dataclass
import json
import time
from typing import Generic, Iterator, NoReturn, Self

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
        self.historic_values.append(
            (self._get_time(), value)
        )

    def jerk(self) -> float | None:
        """
        Compute the instantaneous jerk using the two most recent data points.
        
        Jerk is calculated as:
        
            jerk = (value_latest - value_previous) / (time_latest - time_previous)
        
        Returns:
            The computed jerk (rate of change per second) if at least two values are available.
            If the time difference is zero or insufficient values exist, returns None.
        """
        if len(self.historic_values) < 2:
            return None  # Not enough data to compute jerk

        # Retrieve the last two entries (each is a tuple of (time, value))
        t_prev, value_prev = self.historic_values[-2]
        t_latest, value_latest = self.historic_values[-1]

        dt = t_latest - t_prev
        if dt == 0:
            return 0.0 

        # Compute jerk as the change in value divided by the change in time.
        jerk_value = (value_latest - value_prev) / dt
        return jerk_value


class Accelerometer(Peripheral):
    def __init__(self, port: str, baudrate: int, *args, **kwargs) -> None:
        self.acceleration_value = None
        self.port = port
        self.baudrate = baudrate

        self.x_distribution = Distribution()
        self.y_distribution = Distribution()
        self.z_distribution = Distribution()

        super().__init__(*args, **kwargs)
    
    @staticmethod
    def detect() -> Iterator[Self]:
        return [
            Accelerometer(
                port=port,
                baudrate=115200
            ) for port in get_device_ports("usb-Adafruit_KB2040_DF62585783393B33")
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
            print(f"Invalid packets received, '{bus_data}', skipping.")
            return
        data = json.loads(bus_data)
        self._update_due_to_data(data)

    def get_acceleration(self) -> Acceleration:
        return Acceleration(
            self.acceleration_value["x"],
            self.acceleration_value["y"],
            self.acceleration_value["z"]
        )
    
    def _update_due_to_data(self, data: dict) -> None:
        event_type = data["event_type"]
        data_value = data["data"]

        if event_type == "acceleration":
            self.acceleration_value = data_value
            self.x_distribution.add_value(data_value["x"])
            self.y_distribution.add_value(data_value["y"])
            self.z_distribution.add_value(data_value["z"])