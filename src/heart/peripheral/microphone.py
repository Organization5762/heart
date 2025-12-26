"""Microphone peripheral that publishes audio loudness events."""

from __future__ import annotations

import contextlib
import ctypes.util
import threading
import time
from collections.abc import Iterator
from types import TracebackType
from typing import Any, Self, cast

import numpy as np
import reactivex
from reactivex import operators as ops
from reactivex.subject import Subject

from heart.peripheral.core import Peripheral
from heart.peripheral.input_payloads.audio import MicrophoneLevel
from heart.utilities.logging import get_logger
from heart.utilities.optional_imports import optional_import
from heart.utilities.reactivex_threads import input_scheduler

logger = get_logger(__name__)

sd: Any | None = None
if ctypes.util.find_library("portaudio") is not None:  # pragma: no cover - optional dependency
    sd = optional_import("sounddevice", logger=logger)

DEFAULT_SAMPLE_RATE = 16_000
DEFAULT_BLOCK_DURATION_SECONDS = 0.1
DEFAULT_CHANNELS = 1
DEFAULT_RETRY_DELAY_SECONDS = 1.0


class Microphone(Peripheral[MicrophoneLevel]):
    """Capture audio input and emit loudness metrics"""

    EVENT_LEVEL = "peripheral.microphone.level"

    def __init__(
        self,
        *,
        samplerate: int = DEFAULT_SAMPLE_RATE,
        block_duration: float = DEFAULT_BLOCK_DURATION_SECONDS,
        channels: int = DEFAULT_CHANNELS,
        retry_delay: float = DEFAULT_RETRY_DELAY_SECONDS,
    ) -> None:
        super().__init__()
        self.samplerate = samplerate
        self.block_duration = block_duration
        self.channels = channels
        self._retry_delay = retry_delay

        self._latest_level: dict[str, Any] | None = None
        self._stop_event = threading.Event()
        self._level_subject: Subject[MicrophoneLevel] = Subject()

    # ------------------------------------------------------------------
    # Detection lifecycle
    # ------------------------------------------------------------------
    @classmethod
    def detect(cls) -> Iterator[Self]:
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

    def _event_stream(self) -> reactivex.Observable[MicrophoneLevel]:
        return self._level_subject.pipe(ops.observe_on(input_scheduler()))

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
        self._level_subject.on_next(level)

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
