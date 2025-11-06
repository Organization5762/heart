import collections
import json
import time
from dataclasses import dataclass
from typing import Any, Iterator, NoReturn, Self

import serial

from heart.firmware_io import constants
from heart.peripheral import Input
from heart.peripheral.core import Peripheral
from heart.utilities.env import get_device_ports
from heart.utilities.logging import get_logger

logger = get_logger(__name__)


@dataclass
class Acceleration:
    x: float
    y: float
    z: float


# TODO (lampe): This is fundamentally useless right now
class Distribution:
    def __init__(self) -> None:
        self.historic_values: collections.deque[tuple[float, float]] = (
            collections.deque([], maxlen=100)
        )

    def _get_time(self) -> float:
        return time.monotonic()

    def add_value(self, value: float) -> None:
        self.historic_values.append((self._get_time(), value))


class Accelerometer(Peripheral):
    def __init__(self, port: str, baudrate: int, *args, **kwargs) -> None:
        self.acceleration_value: dict[str, float] | None = None
        self.port = port
        self.baudrate = baudrate

        self.x_distribution = Distribution()
        self.y_distribution = Distribution()
        self.z_distribution = Distribution()

        super().__init__(*args, **kwargs)

    @classmethod
    def detect(cls) -> Iterator[Self]:
        for port in get_device_ports("usb-Adafruit_KB2040"):
            yield cls(port=port, baudrate=115200)

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
                            self._process_data(datum)
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

        try:
            parsed: dict[str, Any] = json.loads(bus_data)
        except json.JSONDecodeError:
            print(f"Failed to decode JSON: {bus_data}")
            return

        event_type = parsed.get("event_type")
        payload = parsed.get("data")
        if not isinstance(event_type, str):
            logger.debug("Ignoring payload without valid event_type: %s", parsed)
            return

        if payload is None:
            logger.debug("Ignoring payload without data: %s", parsed)
            return

        self.emit_event(event_type, payload)
        self.update_due_to_data(parsed)

    def get_acceleration(self) -> Acceleration | None:
        if self.acceleration_value is None:
            return None
        try:
            return Acceleration(
                self.acceleration_value["x"],
                self.acceleration_value["y"],
                self.acceleration_value["z"],
            )
        except KeyError:
            logger.warning(
                "Failed to get acceleration, data: %s", self.acceleration_value
            )
            return None

    def handle_input(self, input: Input) -> None:
        if input.event_type in {constants.ACCELERATION, "acceleration"}:
            data_value = input.data
            if not isinstance(data_value, dict):
                logger.debug(
                    "Acceleration payload is not a mapping: event=%s payload=%s",
                    input.event_type,
                    data_value,
                )
                return

            self.acceleration_value = data_value
            try:
                self.x_distribution.add_value(data_value["x"])
                self.y_distribution.add_value(data_value["y"])
                self.z_distribution.add_value(data_value["z"])
            except KeyError:
                logger.debug("Missing axis in acceleration payload: %s", data_value)
        else:
            super().handle_input(input)
