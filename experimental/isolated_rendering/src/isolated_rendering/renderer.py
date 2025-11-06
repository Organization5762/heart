import threading
import time
from dataclasses import dataclass
from typing import Optional, cast

from heart.device import Cube, Device
from heart.device.local import LocalScreen
from heart.utilities.env import Configuration
from heart.utilities.logging import get_logger

from .buffer import FrameBuffer

try:
    from heart.device.rgb_display import LEDMatrix as _LEDMatrix
except ImportError:  # pragma: no cover - not available outside Pi
    _LEDMatrix = None

LEDMatrix: Optional[type[Device]] = cast(Optional[type[Device]], _LEDMatrix)

logger = get_logger(__name__)


@dataclass
class RendererMetrics:
    fps: float
    updates: int
    latest_version: int
    last_update_age: float


class RenderLoop:
    def __init__(
        self,
        device: Device,
        frame_buffer: FrameBuffer,
        fps: float,
        debug: bool = False,
    ) -> None:
        self.device = device
        self.frame_buffer = frame_buffer
        self.debug = debug
        self._interval = 0.0 if fps <= 0 else 1.0 / fps
        self._stop_event = threading.Event()
        self._last_metrics_time = time.perf_counter()
        self._frames_since_metrics = 0

    def stop(self) -> None:
        self._stop_event.set()

    def run_forever(self) -> None:
        try:
            while not self._stop_event.is_set():
                frame_start = time.perf_counter()
                snapshot = self.frame_buffer.snapshot()
                self.device.set_image(snapshot.image)
                self._frames_since_metrics += 1

                if self.debug:
                    self._maybe_report_metrics(snapshot)

                if self._interval > 0:
                    elapsed = time.perf_counter() - frame_start
                    sleep_time = self._interval - elapsed
                    if sleep_time > 0:
                        time.sleep(sleep_time)
        finally:
            worker = getattr(self.device, "worker", None)
            if worker is not None and hasattr(worker, "shutdown"):
                worker.shutdown()
            if isinstance(self.device, LocalScreen):
                import pygame

                pygame.quit()

    def _maybe_report_metrics(self, snapshot) -> None:
        now = time.perf_counter()
        window = now - self._last_metrics_time
        if window < 1.0:
            return

        fps = self._frames_since_metrics / window if window else 0.0
        updates = self.frame_buffer.drain_update_count()
        age = now - self.frame_buffer.last_update_timestamp
        metrics = RendererMetrics(
            fps=fps,
            updates=updates,
            latest_version=snapshot.version,
            last_update_age=age,
        )
        logger.info(
            "fps=%.1f updates=%d version=%d update_age=%.3fs",
            metrics.fps,
            metrics.updates,
            metrics.latest_version,
            metrics.last_update_age,
        )
        self._frames_since_metrics = 0
        self._last_metrics_time = now


def create_device(x11_forward: bool) -> Device:
    orientation = Cube.sides()

    def _local() -> Device:
        import pygame

        pygame.init()
        return LocalScreen(width=64, height=64, orientation=orientation)

    if Configuration.is_pi() and not x11_forward and not Configuration.is_x11_forward():
        if LEDMatrix is None:
            logger.warning("rgbmatrix library unavailable; falling back to LocalScreen")
            return _local()
        return LEDMatrix(orientation=orientation)

    logger.info("Using LocalScreen renderer")
    return _local()
