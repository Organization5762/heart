import collections
import json
import time
from dataclasses import dataclass
from typing import Any, Iterator, NoReturn, Self

import serial

from heart.events.types import AccelerometerVector
from heart.peripheral.core import Peripheral
from heart.peripheral.core.event_bus import EventBus
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
    def __init__(
        self,
        port: str,
        baudrate: int,
        *,
        event_bus: EventBus | None = None,
        producer_id: int | None = None,
    ) -> None:
        self.acceleration_value: dict[str, float] | None = None
        self.port = port
        self.baudrate = baudrate

        self.x_distribution = Distribution()
        self.y_distribution = Distribution()
        self.z_distribution = Distribution()

        self._event_bus = event_bus
        self._producer_id = producer_id if producer_id is not None else id(self)

        super().__init__()

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
        self._update_due_to_data(parsed)

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

    def attach_event_bus(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus

    def _update_due_to_data(self, data: dict[str, Any]) -> None:
        event_type = data.get("event_type")
        payload = data.get("data")
        if event_type not in {"acceleration", "sensor.acceleration"}:
            return
        if not isinstance(payload, dict):
            logger.debug("Ignoring malformed accelerometer payload: %s", payload)
            return

        try:
            vector = AccelerometerVector(
                x=float(payload["x"]),
                y=float(payload["y"]),
                z=float(payload["z"]),
            )
        except (KeyError, TypeError, ValueError):
            logger.debug("Accelerometer payload missing axis components: %s", payload)
            return

        input_event = vector.to_input(producer_id=self._producer_id)
        self.acceleration_value = input_event.data  # type: ignore[assignment]

        self.x_distribution.add_value(vector.x)
        self.y_distribution.add_value(vector.y)
        self.z_distribution.add_value(vector.z)

        event_bus = self._event_bus
        if event_bus is not None:
            try:
                event_bus.emit(input_event)
            except Exception:
                logger.exception("Failed to emit accelerometer vector")
