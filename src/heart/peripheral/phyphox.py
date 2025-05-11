from typing import Generic, Iterator, NoReturn, Self
import requests
import time

from heart.peripheral import Peripheral
from heart.peripheral.sensor import Acceleration


class Phyphox(Peripheral):
    def __init__(self, url: str) -> None:
        self.url = url
        self.acc_x = 0
        self.acc_y = 0
        self.acc_z = 0

    @classmethod
    def detect(cls) -> Iterator[Self]:
        return [Phyphox("http://192.168.5.31")]

    def run(self) -> NoReturn:
        while True:
            try:
                resp = requests.get(f"{self.url}/get?accY&accX&accZ", timeout=1)
                data = resp.json()
                self.acc_x = data['buffer']['accX']['buffer'][-1]
                self.acc_y = data['buffer']['accY']['buffer'][-1]
                self.acc_z = data['buffer']['accZ']['buffer'][-1]
            except Exception:
                pass
            time.sleep(0.05)
    
    def get_acceleration(self) -> Acceleration | None:
        if self.acc_y is None:
            return None
        return Acceleration(
            self.acc_x,
            self.acc_y,
            self.acc_z,
        )
