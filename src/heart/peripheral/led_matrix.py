"""Peripheral exposing the current LED matrix frame via the event bus."""

from __future__ import annotations

import threading
from datetime import datetime
from typing import Any, Mapping

from PIL import Image

from heart.events.types import DisplayFrame
from heart.peripheral.core import Peripheral
from heart.peripheral.core.event_bus import EventBus
from heart.utilities.logging import get_logger

_LOGGER = get_logger(__name__)


class LEDMatrixDisplay(Peripheral):
    """Virtual peripheral representing the rendered LED matrix image."""

    EVENT_FRAME = DisplayFrame.EVENT_TYPE

    def __init__(
        self,
        *,
        width: int,
        height: int,
        event_bus: EventBus | None = None,
        producer_id: int | None = None,
    ) -> None:
        if width <= 0 or height <= 0:
            raise ValueError("Display dimensions must be positive")

        self._width = width
        self._height = height
        self._producer_id = producer_id if producer_id is not None else id(self)
        self._frame_lock = threading.Lock()
        self._latest_frame: DisplayFrame | None = None
        self._sequence = 0
        self._stop = threading.Event()

        super().__init__()
        if event_bus is not None:
            self.attach_event_bus(event_bus)

    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height

    @property
    def producer_id(self) -> int:
        """Return the producer identifier used for emitted frames."""

        return self._producer_id

    @property
    def latest_frame(self) -> DisplayFrame | None:
        """Return the most recently published frame, if any."""

        with self._frame_lock:
            return self._latest_frame

    def attach_event_bus(self, event_bus: EventBus) -> None:
        super().attach_event_bus(event_bus)

    def publish_image(
        self,
        image: Image.Image,
        *,
        metadata: Mapping[str, Any] | None = None,
        timestamp: datetime | None = None,
    ) -> DisplayFrame:
        """Record ``image`` as the latest frame and emit it on the event bus."""

        if image.size != (self._width, self._height):
            raise ValueError(
                "Image dimensions do not match configured display size"
            )

        with self._frame_lock:
            frame = DisplayFrame.from_image(
                image,
                frame_id=self._sequence,
                metadata=metadata,
            )
            self._sequence += 1
            self._latest_frame = frame

        event_bus = self.event_bus
        if event_bus is not None:
            try:
                self.emit_input(
                    frame.to_input(
                        producer_id=self._producer_id,
                        timestamp=timestamp,
                    )
                )
            except Exception:  # pragma: no cover - defensive logging only
                _LOGGER.exception("Failed to emit LED matrix frame update")
        return frame

    def run(self) -> None:  # noqa: D401 - signature defined by base class
        """Idle loop to satisfy the :class:`Peripheral` contract."""

        while not self._stop.wait(timeout=60.0):
            continue

    def stop(self) -> None:
        """Signal the background thread to exit."""

        self._stop.set()

