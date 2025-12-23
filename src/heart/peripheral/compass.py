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
from heart.utilities.env import Configuration
from heart.utilities.logging import get_logger

logger = get_logger(__name__)

Vector3 = tuple[float, float, float]

class Compass(Peripheral[Vector3 | None]):
    """Maintain a smoothed magnetic heading derived from sensor bus events."""

    _VALID_SMOOTHING_MODES = ("window", "ema")

    def __init__(
        self,
        *,
        window_size: int | None = None,
        smoothing_mode: str | None = None,
        ema_alpha: float | None = None,
    ) -> None:
        resolved_window_size = (
            window_size
            if window_size is not None
            else Configuration.compass_window_size()
        )
        if resolved_window_size < 1:
            raise ValueError("window_size must be at least one")
        resolved_mode = (
            smoothing_mode
            if smoothing_mode is not None
            else Configuration.compass_smoothing_mode()
        ).lower()
        if resolved_mode not in self._VALID_SMOOTHING_MODES:
            raise ValueError(
                "smoothing_mode must be one of "
                f"{', '.join(self._VALID_SMOOTHING_MODES)}"
            )
        resolved_alpha = (
            ema_alpha
            if ema_alpha is not None
            else Configuration.compass_ema_alpha()
        )
        if not 0.0 < resolved_alpha <= 1.0:
            raise ValueError("ema_alpha must be in the range (0.0, 1.0]")

        super().__init__()
        self._window_size = resolved_window_size
        self._smoothing_mode = resolved_mode
        self._ema_alpha = resolved_alpha
        self._history: Deque[Vector3] = deque(maxlen=resolved_window_size)
        self._latest: Vector3 | None = None
        self._sum_x = 0.0
        self._sum_y = 0.0
        self._sum_z = 0.0
        self._ema_vector: Vector3 | None = None
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
            if self._smoothing_mode == "window":
                if len(self._history) == self._window_size:
                    oldest = self._history[0]
                    self._sum_x -= oldest[0]
                    self._sum_y -= oldest[1]
                    self._sum_z -= oldest[2]
                self._history.append(vector)
                self._sum_x += vector[0]
                self._sum_y += vector[1]
                self._sum_z += vector[2]
            else:
                if self._ema_vector is None:
                    self._ema_vector = vector
                else:
                    alpha = self._ema_alpha
                    self._ema_vector = (
                        alpha * vector[0] + (1 - alpha) * self._ema_vector[0],
                        alpha * vector[1] + (1 - alpha) * self._ema_vector[1],
                        alpha * vector[2] + (1 - alpha) * self._ema_vector[2],
                    )

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
            if self._smoothing_mode == "ema":
                return self._ema_vector
            if not self._history:
                return None
            count = len(self._history)
            return (self._sum_x / count, self._sum_y / count, self._sum_z / count)

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
