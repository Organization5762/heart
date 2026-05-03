"""Microphone peripheral that publishes audio loudness events."""

from __future__ import annotations

import contextlib
import ctypes.util
import time
from collections.abc import Iterator
from types import TracebackType
from typing import Any, Self, cast

import numpy as np
from manyfold import (DetectionNode, Graph, Layer, ManagedGraphNode,
                      ManagedGraphNodeHandle, OwnerName, Plane, Schema,
                      StreamFamily, StreamName, TypedRoute, Variant, route)
from manyfold.sensor_io import (BackoffPolicy, ManagedRunLoop, RetryPolicy,
                                SensorEvent, StopToken, sensor_event_schema)

import heart.utilities.reactive as reactive
from heart.peripheral.core import Peripheral
from heart.peripheral.input_payloads.audio import MicrophoneLevel
from heart.utilities.logging import get_logger
from heart.utilities.optional_imports import optional_import
from heart.utilities.reactive import Subject

logger = get_logger(__name__)

sd: Any | None = None
if ctypes.util.find_library("portaudio") is not None:  # pragma: no cover - optional dependency
    sd = optional_import("sounddevice", logger=logger)

DEFAULT_SAMPLE_RATE = 16_000
DEFAULT_BLOCK_DURATION_SECONDS = 0.1
DEFAULT_CHANNELS = 1
DEFAULT_RETRY_DELAY_SECONDS = 1.0
MICROPHONE_GRAPH_OWNER = OwnerName("heart.microphone")
MICROPHONE_GRAPH_FAMILY = StreamFamily("peripheral")


def microphone_level_event_route() -> TypedRoute[SensorEvent]:
    return route(
        plane=Plane.Read,
        layer=Layer.Logical,
        owner=MICROPHONE_GRAPH_OWNER,
        family=MICROPHONE_GRAPH_FAMILY,
        stream=StreamName("levels"),
        variant=Variant.Meta,
        schema=sensor_event_schema("HeartMicrophoneLevelEvent"),
    )


def microphone_detection_route() -> TypedRoute[SensorEvent]:
    return route(
        plane=Plane.Read,
        layer=Layer.Logical,
        owner=MICROPHONE_GRAPH_OWNER,
        family=MICROPHONE_GRAPH_FAMILY,
        stream=StreamName("detected"),
        variant=Variant.Meta,
        schema=sensor_event_schema("HeartMicrophoneDetectionEvent"),
    )


def microphone_exception_schema() -> Schema[BaseException]:
    def encode(exc: BaseException) -> bytes:
        return f"{type(exc).__name__}:{exc}".encode("utf-8")

    def decode(payload: bytes) -> BaseException:
        return RuntimeError(payload.decode("utf-8"))

    return Schema(
        schema_id="PythonException",
        version=1,
        encode=encode,
        decode=decode,
    )


def microphone_error_route() -> TypedRoute[BaseException]:
    return route(
        plane=Plane.Read,
        layer=Layer.Logical,
        owner=MICROPHONE_GRAPH_OWNER,
        family=MICROPHONE_GRAPH_FAMILY,
        stream=StreamName("errors"),
        variant=Variant.Meta,
        schema=microphone_exception_schema(),
    )


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
        self._stop_token = StopToken(group="microphone")
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

    @classmethod
    def detection_node(
        cls,
        *,
        output_route: TypedRoute[SensorEvent] | None = None,
        level_output_route: TypedRoute[SensorEvent] | None = None,
        level_error_route: TypedRoute[BaseException] | None = None,
        spawn_sources: bool = False,
        on_detect: Any | None = None,
        start_immediately: bool = True,
    ) -> DetectionNode:
        resolved_output_route = output_route or microphone_detection_route()
        resolved_level_output_route = level_output_route or microphone_level_event_route()

        def mapper(peripheral: "Microphone") -> SensorEvent:
            return SensorEvent(
                event_type="peripheral.microphone.detected",
                data={
                    "samplerate": peripheral.samplerate,
                    "block_duration": peripheral.block_duration,
                    "channels": peripheral.channels,
                },
                observed_at=time.time(),
                identity=peripheral.peripheral_info().to_sensor_identity(),
            )

        def spawn(peripheral: "Microphone", access: Any) -> None:
            if not spawn_sources:
                return
            access.own(
                peripheral.install_node(
                    access.graph,
                    output_route=resolved_level_output_route,
                    error_route=level_error_route or microphone_error_route(),
                )
            )

        return DetectionNode(
            name="heart-microphone-detection",
            detector=cls.detect,
            output_route=resolved_output_route,
            mapper=mapper,
            on_detect=on_detect,
            spawn=spawn,
            error_route=microphone_error_route(),
            group="microphone-detection",
            start_immediately=start_immediately,
        )

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------
    @property
    def latest_level(self) -> dict[str, Any] | None:
        """Return the most recent loudness measurement."""

        return self._latest_level

    def _event_stream(self) -> reactive.Observable[MicrophoneLevel]:
        return self._level_subject

    def stop(self) -> None:
        """Signal the run-loop to stop on the next iteration."""

        self._stop_token.set()

    # ------------------------------------------------------------------
    # Run loop
    # ------------------------------------------------------------------
    def run(self) -> None:  # pragma: no cover - interacts with audio hardware
        if sd is None:
            logger.info("sounddevice not available; microphone peripheral idle")
            return

        blocksize = max(1, int(self.samplerate * self.block_duration))

        def _run_stream(stop: StopToken) -> None:
            try:
                with self._open_stream(blocksize):
                    logger.info(
                        "Microphone stream started (samplerate=%dHz, block=%d samples)",
                        self.samplerate,
                        blocksize,
                    )
                    self._wait_forever(stop)
            except KeyboardInterrupt:
                logger.info("Microphone peripheral interrupted; stopping stream")
                stop.set()
                return

        loop = ManagedRunLoop(
            body=_run_stream,
            backoff=BackoffPolicy.fixed(self._retry_delay),
            on_error=lambda _exc, _attempt: logger.exception(
                "Microphone stream failed; retrying in %.1fs",
                self._retry_delay,
            ),
            group="microphone",
        )
        try:
            loop.run(self._stop_token)
        finally:
            self._stop_token = StopToken(group="microphone")

    def install_node(
        self,
        graph: Graph,
        *,
        output_route: TypedRoute[SensorEvent] | None = None,
        error_route: TypedRoute[BaseException] | None = None,
        retry: RetryPolicy | None = None,
        backoff: BackoffPolicy | None = None,
        start_immediately: bool = True,
    ) -> ManagedGraphNodeHandle:
        """Install this microphone as a self-running Manyfold graph level source."""

        resolved_output_route = output_route or microphone_level_event_route()
        blocksize = max(1, int(self.samplerate * self.block_duration))

        def _body(stop: StopToken, graph: Graph) -> None:
            if sd is None:
                logger.info("sounddevice not available; microphone graph node idle")
                stop.set()
                return

            def _publish_audio_block(
                indata: Any,
                frames: int,
                time_info: Any,
                status: Any,
            ) -> None:
                level = self._handle_audio_block(indata, frames, time_info, status)
                if level is None:
                    return
                graph.publish(
                    resolved_output_route,
                    self._level_to_sensor_event(level),
                )

            try:
                with self._open_stream(blocksize, callback=_publish_audio_block):
                    logger.info(
                        "Microphone graph node started (samplerate=%dHz, block=%d samples)",
                        self.samplerate,
                        blocksize,
                    )
                    self._wait_forever(stop)
            except KeyboardInterrupt:
                logger.info("Microphone graph node interrupted; stopping stream")
                stop.set()
                return

        return ManagedGraphNode(
            name="heart-microphone-levels",
            body=_body,
            output_routes=(resolved_output_route,),
            error_route=error_route or microphone_error_route(),
            retry=retry or RetryPolicy(max_attempts=1_000_000),
            backoff=backoff or BackoffPolicy.fixed(self._retry_delay),
            group="microphone",
            start_immediately=start_immediately,
        ).install(graph)

    def _wait_forever(self, stop: StopToken) -> None:
        while not stop.wait(self.block_duration):
            pass

    def _open_stream(
        self,
        blocksize: int,
        *,
        callback: Any | None = None,
    ) -> Any:  # pragma: no cover - thin wrapper
        assert sd is not None
        return sd.InputStream(
            samplerate=self.samplerate,
            channels=self.channels,
            blocksize=blocksize,
            callback=callback or self._on_audio_block,
        )

    # ------------------------------------------------------------------
    # Audio processing
    # ------------------------------------------------------------------
    def _on_audio_block(
        self, indata: Any, frames: int, _time: Any, status: Any
    ) -> None:
        self._handle_audio_block(indata, frames, _time, status)

    def _handle_audio_block(
        self, indata: Any, frames: int, _time: Any, status: Any
    ) -> MicrophoneLevel | None:
        if status:  # pragma: no cover - requires real hardware conditions
            logger.warning("Microphone stream status: %s", status)
        try:
            audio = np.asarray(indata)
        except Exception:
            logger.exception("Failed to convert audio buffer to numpy array")
            return None
        if audio.size == 0:
            return None
        return self._process_audio_chunk(audio, frames)

    def _process_audio_chunk(self, audio: np.ndarray, frames: int) -> MicrophoneLevel:
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
        return level

    def _level_to_sensor_event(self, level: MicrophoneLevel) -> SensorEvent:
        return SensorEvent(
            event_type=level.event_type,
            data=level.to_input().data,
            observed_at=level.timestamp,
            identity=self.peripheral_info().to_sensor_identity(),
        )

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
            self._stop_token.set()
