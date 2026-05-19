from __future__ import annotations

import time
from dataclasses import dataclass
from typing import cast

import pygame
from manyfold import Graph, StreamNode

from heart.peripheral.core.input.debug import InputDebugStage, InputDebugTap
from heart.peripheral.core.streams import EventStream


@dataclass(frozen=True, slots=True)
class FrameTick:
    frame_index: int
    delta_ms: float
    delta_s: float
    monotonic_s: float
    fps: float | None = None


class FrameTickController:
    def __init__(self, debug_tap: InputDebugTap, graph: Graph | None = None) -> None:
        del graph
        self._debug_tap = debug_tap
        self._frame_index = 0
        self._stream: EventStream[FrameTick] = EventStream()

    def advance(self, clock: pygame.time.Clock) -> FrameTick:
        fps = float(clock.get_fps())
        frame = FrameTick(
            frame_index=self._frame_index,
            delta_ms=float(clock.get_time()),
            delta_s=max(float(clock.get_time()), 0.0) / 1000.0,
            monotonic_s=time.monotonic(),
            fps=fps if fps > 0 else None,
        )
        self._frame_index += 1
        self._debug_tap.record_latency("frame.tick", time.monotonic() - frame.monotonic_s)
        self._debug_tap.publish(
            stage=InputDebugStage.FRAME,
            stream_name="frame.tick",
            source_id="frame",
            payload=frame,
        )
        self._stream.emit(frame)
        return frame

    def observable(self) -> StreamNode[FrameTick]:
        return cast(StreamNode[FrameTick], self._stream.observable())
