"""Peripheral exposing the current LED matrix frame"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any, Mapping

from PIL import Image
from reactivex.subject import Subject

from heart.peripheral.core import Peripheral
from heart.peripheral.input_payloads import DisplayFrame
from heart.utilities.logging import get_logger

_LOGGER = get_logger(__name__)


class LEDMatrixDisplay(Peripheral[DisplayFrame]):
    """Virtual peripheral representing the rendered LED matrix image."""

    EVENT_FRAME = DisplayFrame.EVENT_TYPE

    def __init__(
        self,
        *,
        width: int,
        height: int,
    ) -> None:
        if width <= 0 or height <= 0:
            raise ValueError("Display dimensions must be positive")

        self._width = width
        self._height = height
        self._frame_lock = threading.Lock()
        self._latest_frame: DisplayFrame | None = None
        self._sequence = 0
        self._stop = threading.Event()
        self._frame_subject: Subject[DisplayFrame] = Subject()

        super().__init__()

    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height

    @property
    def latest_frame(self) -> DisplayFrame | None:
        """Return the most recently published frame, if any."""

        with self._frame_lock:
            return self._latest_frame

    def _event_stream(self) -> Subject[DisplayFrame]:
        return self._frame_subject

    def publish_image(
        self,
        image: Image.Image,
        *,
        metadata: Mapping[str, Any] | None = None,
        timestamp: datetime | None = None,
    ) -> DisplayFrame:
        """Record ``image`` as the latest frame"""

        if image.size != (self._width, self._height):
            raise ValueError(
                "Image dimensions do not match configured display size"
            )

        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        frame_metadata = dict(metadata or {})
        frame_metadata.setdefault("timestamp", timestamp.isoformat())

        with self._frame_lock:
            frame = DisplayFrame.from_image(
                image,
                frame_id=self._sequence,
                metadata=frame_metadata,
            )
            self._sequence += 1
            self._latest_frame = frame

        try:
            self._frame_subject.on_next(frame)
        except Exception:
            _LOGGER.exception("Failed to publish LED matrix frame")

        return frame
