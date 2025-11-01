from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Tuple

from PIL import Image


@dataclass
class FrameSnapshot:
    image: Image.Image
    version: int


class FrameBuffer:
    """Thread-safe container for the latest matrix frame."""

    def __init__(self, size: Tuple[int, int], mode: str = "RGB") -> None:
        self.size = size
        self.mode = mode
        self._lock = threading.Lock()
        self._image = Image.new(self.mode, size)
        self._version = 0
        self._updates_since_metric = 0
        self._last_update_ts = time.perf_counter()

    def update_raw(self, width: int, height: int, payload: bytes) -> None:
        expected_len = width * height * len(self.mode)
        if (width, height) != self.size:
            raise ValueError(
                f"Frame size {width}x{height} does not match target {self.size[0]}x{self.size[1]}"
            )
        if len(payload) != expected_len:
            raise ValueError(
                f"Frame payload length {len(payload)} does not match expected {expected_len}"
            )

        image = Image.frombytes(self.mode, (width, height), payload)
        self.update_image(image)

    def update_image(self, image: Image.Image) -> None:
        if image.size != self.size:
            raise ValueError(
                f"Frame size {image.size} does not match target {self.size}"
            )

        with self._lock:
            self._image = image
            self._version += 1
            self._updates_since_metric += 1
            self._last_update_ts = time.perf_counter()

    def snapshot(self) -> FrameSnapshot:
        with self._lock:
            image = self._image
            version = self._version
        return FrameSnapshot(image=image, version=version)

    def drain_update_count(self) -> int:
        with self._lock:
            updates = self._updates_since_metric
            self._updates_since_metric = 0
        return updates

    @property
    def last_update_timestamp(self) -> float:
        return self._last_update_ts
