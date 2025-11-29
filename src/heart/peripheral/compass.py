"""Compass peripheral that derives heading from magnetometer vectors."""

from __future__ import annotations

import math
import threading
from collections import deque
from collections.abc import Iterator
from datetime import timedelta
from typing import Deque, Mapping, Self

import reactivex
from reactivex import operators as ops

from heart.peripheral.core import Input, Peripheral
from heart.utilities.logging import get_logger

logger = get_logger(__name__)

Vector3 = tuple[float, float, float]

class Compass(Peripheral[Vector3 | None]):
    """Maintain a smoothed magnetic heading derived from sensor bus events."""

    def __init__(
        self,
        *,
        window_size: int = 5,
    ) -> None:
        if window_size < 1:
            raise ValueError("window_size must be at least one")

        super().__init__()
        self._window_size = window_size
        self._history: Deque[Vector3] = deque(maxlen=window_size)
        self._latest: Vector3 | None = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Peripheral API
    # ------------------------------------------------------------------
    def run(self) -> None:  # pragma: no cover - no active loop required
        """Compass reacts to event bus updates; no background loop needed."""

    @classmethod
    def detect(cls) -> Iterator[Self]:
        """Always expose a single compass peripheral."""

        yield cls()


    def _handle_magnetometer(self, event: Input) -> None:
        payload = event.data
        if not isinstance(payload, Mapping):
            logger.debug("Ignoring non-mapping magnetometer payload: %s", payload)
            return

        try:
            vector = (
                float(payload["x"]),
                float(payload["y"]),
                float(payload["z"]),
            )
        except (KeyError, TypeError, ValueError):
            logger.debug("Magnetometer payload missing axis components: %s", payload)
            return

        with self._lock:
            self._latest = vector
            self._history.append(vector)

    def _event_stream(
        self
    ) -> reactivex.Observable[Vector3 | None]:
        return reactivex.interval(timedelta(milliseconds=10)).pipe(
            ops.map(lambda _: self.get_latest_vector()),
            ops.distinct_until_changed(lambda x: x)
        )
    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------
    def get_latest_vector(self) -> Vector3 | None:
        """Return the most recent magnetic field sample."""

        with self._lock:
            return self._latest

    def get_average_vector(self) -> Vector3 | None:
        """Return the rolling average vector across the smoothing window."""

        with self._lock:
            if not self._history:
                return None
            count = len(self._history)
            x = sum(vector[0] for vector in self._history) / count
            y = sum(vector[1] for vector in self._history) / count
            z = sum(vector[2] for vector in self._history) / count
            return (x, y, z)

    def get_heading_degrees(self) -> float | None:
        """Return the smoothed magnetic heading in degrees clockwise from north."""

        vector = self.get_average_vector()
        if vector is None:
            return None

        x, y, _ = vector
        if math.isclose(x, 0.0, abs_tol=1e-9) and math.isclose(y, 0.0, abs_tol=1e-9):
            return None

        heading = math.degrees(math.atan2(x, y))
        if heading < 0:
            heading += 360.0
        return heading

    @property
    def window_size(self) -> int:
        return self._window_size
