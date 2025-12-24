"""Microphone peripheral that publishes audio loudness events."""

from __future__ import annotations

import contextlib
import threading
import time
from collections.abc import Iterator
from types import TracebackType
from typing import Any, Self, cast

import numpy as np

from heart.peripheral.core import Peripheral
from heart.peripheral.input_payloads.audio import MicrophoneLevel
from heart.utilities.logging import get_logger

logger = get_logger(__name__)

sd: Any | None = None
try:  # pragma: no cover - import guarded for optional dependency
    import sounddevice as _sounddevice
except Exception:  # pragma: no cover - module may be missing on CI
    _sounddevice = None
sd = cast(Any | None, _sounddevice)


class Microphone(Peripheral[MicrophoneLevel]):
    """Capture audio input and emit loudness metrics"""

    EVENT_LEVEL = "peripheral.microphone.level"

    def __init__(
        self,
        *,
        samplerate: int = 16_000,
        block_duration: float = 0.1,
        channels: int = 1,
        retry_delay: float = 1.0,
    ) -> None:
        super().__init__()
        self.samplerate = samplerate
        self.block_duration = block_duration
        self.channels = channels
        self._retry_delay = retry_delay

        self._latest_level: dict[str, Any] | None = None
        self._stop_event = threading.Event()

    # ------------------------------------------------------------------
    # Detection lifecycle
    # ------------------------------------------------------------------
    @classmethod
    def detect(cls) -> Iterator[Self]:
        return
        """Yield a microphone peripheral if audio backends are available."""

        if sd is None:
            logger.info("sounddevice not available; skipping microphone detection")
            return

        try:
            devices = sd.query_devices()
        except Exception as exc:  # pragma: no cover - depends on host
            logger.warning("Failed to query audio devices: %s", exc)
            return

        input_present = any(device.get("max_input_channels", 0) > 0 for device in devices)
        if not input_present:
            logger.info("No audio input devices detected; skipping microphone peripheral")
            return

        yield cls()

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------
    @property
    def latest_level(self) -> dict[str, Any] | None:
        """Return the most recent loudness measurement."""

        return self._latest_level

    def stop(self) -> None:
        """Signal the run-loop to stop on the next iteration."""

        self._stop_event.set()

    # ------------------------------------------------------------------
    # Run loop
    # ------------------------------------------------------------------
    def run(self) -> None:  # pragma: no cover - interacts with audio hardware
        if sd is None:
            logger.info("sounddevice not available; microphone peripheral idle")
            return

        blocksize = max(1, int(self.samplerate * self.block_duration))

        while not self._stop_event.is_set():
            try:
                with self._open_stream(blocksize):
                    logger.info(
                        "Microphone stream started (samplerate=%dHz, block=%d samples)",
                        self.samplerate,
                        blocksize,
                    )
                    self._wait_forever()
            except KeyboardInterrupt:
                logger.info("Microphone peripheral interrupted; stopping stream")
                break
            except Exception:
                logger.exception("Microphone stream failed; retrying in %.1fs", self._retry_delay)
                time.sleep(self._retry_delay)

        self._stop_event.clear()

    def _wait_forever(self) -> None:
        while not self._stop_event.wait(self.block_duration):
            pass

    def _open_stream(self, blocksize: int) -> Any:  # pragma: no cover - thin wrapper
        assert sd is not None
        return sd.InputStream(
            samplerate=self.samplerate,
            channels=self.channels,
            blocksize=blocksize,
            callback=self._on_audio_block,
        )

    # ------------------------------------------------------------------
    # Audio processing
    # ------------------------------------------------------------------
    def _on_audio_block(
        self, indata: Any, frames: int, _time: Any, status: Any
    ) -> None:
        if status:  # pragma: no cover - requires real hardware conditions
            logger.warning("Microphone stream status: %s", status)
        try:
            audio = np.asarray(indata)
        except Exception:
            logger.exception("Failed to convert audio buffer to numpy array")
            return
        if audio.size == 0:
            return
        self._process_audio_chunk(audio, frames)

    def _process_audio_chunk(self, audio: np.ndarray, frames: int) -> None:
        """Compute loudness metrics and publish an event."""

        flattened = audio.reshape(-1)
        rms = float(np.sqrt(np.mean(np.square(flattened))))
        peak = float(np.max(np.abs(flattened)))
        timestamp = time.time()

        level = MicrophoneLevel(
            rms=rms,
            peak=peak,
            frames=frames,
            samplerate=self.samplerate,
            timestamp=timestamp,
        )
        payload = level.to_input()
        self._latest_level = cast(dict[str, Any], payload.data)

        raise NotImplementedError("")

    # ------------------------------------------------------------------
    # Context manager helpers
    # ------------------------------------------------------------------
    def __enter__(self) -> "Microphone":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.stop()
        # Drain any context managers to avoid suppressing exceptions
        with contextlib.suppress(Exception):
            self._stop_event.set()
