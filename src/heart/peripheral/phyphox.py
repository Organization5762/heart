import time
from typing import Iterator, NoReturn, Self

import requests

from heart.peripheral.core import Peripheral
from heart.peripheral.sensor import Acceleration
from heart.utilities.logging import get_logger

logger = get_logger(__name__)
DEFAULT_PHYPOX_URL = "http://192.168.1.42"
PHYPOX_ACCEL_ENDPOINT = "/get?accY&accX&accZ"
REQUEST_TIMEOUT_SECONDS = 1
REQUEST_SLEEP_SECONDS = 0.05


class Phyphox(Peripheral[Acceleration]):
    def __init__(self, url: str) -> None:
        super().__init__()
        self.url = url
        self.acc_x: float | None = None
        self.acc_y: float | None = None
        self.acc_z: float | None = None

    @classmethod
    def detect(cls) -> Iterator[Self]:
        yield cls(DEFAULT_PHYPOX_URL)

    def run(self) -> NoReturn:
        while True:
            try:
                resp = requests.get(
                    f"{self.url}{PHYPOX_ACCEL_ENDPOINT}",
                    timeout=REQUEST_TIMEOUT_SECONDS,
                )
                data = resp.json()
                self.acc_x = float(data["buffer"]["accX"]["buffer"][-1])
                self.acc_y = float(data["buffer"]["accY"]["buffer"][-1])
                self.acc_z = float(data["buffer"]["accZ"]["buffer"][-1])
            except Exception as exc:
                logger.debug("Phyphox request failed: %s", exc)
            time.sleep(REQUEST_SLEEP_SECONDS)

    def get_acceleration(self) -> Acceleration | None:
        if self.acc_x is None or self.acc_y is None or self.acc_z is None:
            return None
        return Acceleration(
            self.acc_x,
            self.acc_y,
            self.acc_z,
        )
