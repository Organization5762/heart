import json
import random
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Iterator, Mapping, NoReturn, Self, cast

import reactivex
import serial
from reactivex import operators as ops

from heart.peripheral.core import Peripheral, PeripheralInfo, PeripheralTag
from heart.peripheral.input_payloads import (AccelerometerVector,
                                             MagnetometerVector)
from heart.utilities.env import get_device_ports
from heart.utilities.logging import get_logger

logger = get_logger(__name__)


@dataclass
class Acceleration:
    x: float
    y: float
    z: float


class Accelerometer(Peripheral[Acceleration | None]):
    def __init__(
        self,
        port: str,
        baudrate: int,
    ) -> None:
        super().__init__()
        self.acceleration_value: dict[str, float] | None = None
        self.magnetometer_value: dict[str, float] | None = None
        self.port = port
        self.baudrate = baudrate

    def _event_stream(
        self
    ) -> reactivex.Observable[Acceleration | None]:
        return reactivex.interval(timedelta(milliseconds=10)).pipe(
            ops.map(lambda _: self.get_acceleration()),
            ops.distinct_until_changed(lambda x: x)
        )

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
                    logger.info("Accelerometer monitor terminated")
                except Exception:
                    logger.exception("Accelerometer monitor encountered an error")
                finally:
                    ser.close()
            except Exception:
                logger.exception("Failed to connect to accelerometer")

    def _process_data(self, data: bytes) -> None:
        bus_data = data.decode("utf-8").rstrip()
        if not bus_data or not bus_data.startswith("{"):
            logger.debug("Ignoring non-JSON sensor payload: %r", bus_data)
            return

        try:
            parsed: dict[str, Any] = json.loads(bus_data)
        except json.JSONDecodeError:
            logger.debug("Failed to decode JSON: %s", bus_data)
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


    def _update_due_to_data(self, data: dict[str, Any]) -> None:
        event_type = data.get("event_type")
        payload = data.get("data")
        if not isinstance(payload, dict):
            logger.debug("Ignoring malformed sensor payload: %s", payload)
            return

        if event_type in {"acceleration", "sensor.acceleration"}:
            self._handle_acceleration(payload)
            return
        if event_type in {"magnetic", "sensor.magnetic"}:
            self._handle_magnetic(payload)

    def _handle_acceleration(self, payload: Mapping[str, Any]) -> None:
        try:
            vector = AccelerometerVector(
                x=float(payload["x"]),
                y=float(payload["y"]),
                z=float(payload["z"]),
            )
        except (KeyError, TypeError, ValueError):
            logger.debug("Accelerometer payload missing axis components: %s", payload)
            return

        input_event = vector.to_input()
        self.acceleration_value = cast(dict[str, float], input_event.data)

    def _handle_magnetic(self, payload: Mapping[str, Any]) -> None:
        try:
            vector = MagnetometerVector(
                x=float(payload["x"]),
                y=float(payload["y"]),
                z=float(payload["z"]),
            )
        except (KeyError, TypeError, ValueError):
            logger.debug("Magnetometer payload missing axis components: %s", payload)
            return

        input_event = vector.to_input()
        self.magnetometer_value = cast(dict[str, float], input_event.data)

class FakeAccelerometer(Peripheral[Acceleration | None]):
    @classmethod
    def detect(cls) -> Iterator[Self]:
        yield cls()

    def peripheral_info(self) -> PeripheralInfo:
        return PeripheralInfo(
            id="fake_accelerometer",
            tags=[
                PeripheralTag(name="input_variant", variant="accelerometer"),
            ],
        )

    def _event_stream(
        self
    ) -> reactivex.Observable[Acceleration | None]:
        def random_accel(_: int) -> Acceleration:
            return Acceleration(
                x=random.random(),
                y=random.random(),
                z=9.8,
            )
        return reactivex.interval(timedelta(milliseconds=500)).pipe(
            ops.map(random_accel)
        )
