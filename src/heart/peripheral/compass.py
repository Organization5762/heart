from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass
from typing import Deque, Iterator, NoReturn, Self

from heart.firmware_io import constants
from heart.peripheral import Input
from heart.peripheral.core import Peripheral
from heart.peripheral.core.event_bus import SubscriptionHandle
from heart.utilities.logging import get_logger

logger = get_logger(__name__)


@dataclass
class MagneticField:
    x: float
    y: float
    z: float


class Compass(Peripheral):
    """Track heading based on magnetometer samples emitted by the sensor bus."""

    def __init__(self, *, smoothing_window: int = 5, **kwargs) -> None:
        super().__init__(**kwargs)
        if smoothing_window < 1:
            raise ValueError("smoothing_window must be >= 1")
        self._smoothing_window = smoothing_window
        self._history: Deque[MagneticField] = deque(maxlen=smoothing_window)
        self._latest: MagneticField | None = None
        self._subscription: SubscriptionHandle | None = None

    def run(self) -> NoReturn:
        while True:
            time.sleep(1.0)

    @classmethod
    def detect(cls) -> Iterator[Self]:
        yield cls()

    def _on_event_bus_attached(self) -> None:
        if self.event_bus is None:
            return
        if self._subscription is not None:
            self.event_bus.unsubscribe(self._subscription)
        self._subscription = self.event_bus.subscribe(
            constants.MAGNETIC, self.handle_input
        )

    def handle_input(self, input: Input) -> None:
        if input.event_type != constants.MAGNETIC:
            super().handle_input(input)
            return

        vector = self._coerce_vector(input.data)
        if vector is None:
            return
        self._latest = vector
        self._history.append(vector)

    def _coerce_vector(self, payload) -> MagneticField | None:
        if not isinstance(payload, dict):
            logger.debug("Received non-mapping magnetic payload: %s", payload)
            return None
        try:
            return MagneticField(
                float(payload["x"]), float(payload["y"]), float(payload["z"])
            )
        except (KeyError, TypeError, ValueError):
            logger.debug("Malformed magnetic payload: %s", payload, exc_info=True)
            return None

    def get_latest_vector(self) -> MagneticField | None:
        return self._latest

    def get_smoothed_vector(self) -> MagneticField | None:
        if not self._history:
            return None
        size = len(self._history)
        accum_x = sum(item.x for item in self._history)
        accum_y = sum(item.y for item in self._history)
        accum_z = sum(item.z for item in self._history)
        return MagneticField(accum_x / size, accum_y / size, accum_z / size)

    def get_heading_degrees(self) -> float | None:
        vector = self.get_smoothed_vector()
        if vector is None:
            return None
        heading = math.degrees(math.atan2(vector.y, vector.x))
        return (heading + 360.0) % 360.0
