from __future__ import annotations

import colorsys
from dataclasses import dataclass
from functools import cached_property

import pygame
from manyfold import StreamNode

from heart.peripheral.core.input.debug import (InputDebugNode, InputDebugStage,
                                               InputDebugTap)

COLOR_SNAPSHOT_STREAM = "color.snapshot"


@dataclass(frozen=True, slots=True)
class ColorSnapshot:
    average_rgb: tuple[int, int, int]
    hue: float
    saturation: float
    brightness: float
    value: float


class ColorInputProfile:
    """Derived color streams from the final rendered frame."""

    def __init__(
        self,
        *,
        final_frames: StreamNode[pygame.Surface],
        debug_tap: InputDebugTap,
    ) -> None:
        self._final_frames = final_frames
        self._debug_tap = debug_tap

    def average_rgb(self) -> StreamNode[tuple[int, int, int]]:
        return self.snapshot().map(lambda snapshot: snapshot.average_rgb)

    def hue(self) -> StreamNode[float]:
        return self.snapshot().map(lambda snapshot: snapshot.hue)

    def saturation(self) -> StreamNode[float]:
        return self.snapshot().map(lambda snapshot: snapshot.saturation)

    def brightness(self) -> StreamNode[float]:
        return self.snapshot().map(lambda snapshot: snapshot.brightness)

    def value(self) -> StreamNode[float]:
        return self.snapshot().map(lambda snapshot: snapshot.value)

    @cached_property
    def _snapshot_stream(self) -> StreamNode[ColorSnapshot]:
        snapshots = self._final_frames.map(_surface_color_snapshot)
        return InputDebugNode(
            tap=self._debug_tap,
            stage=InputDebugStage.VIEW,
            stream_name=COLOR_SNAPSHOT_STREAM,
            source_id="final_frame",
            upstream_ids=("runtime.window",),
        ).connect(snapshots)

    def snapshot(self) -> StreamNode[ColorSnapshot]:
        return self._snapshot_stream


def _surface_color_snapshot(surface: pygame.Surface) -> ColorSnapshot:
    red, green, blue, *_alpha = pygame.transform.average_color(surface)
    average_rgb = (int(red), int(green), int(blue))
    normalized_red = average_rgb[0] / 255.0
    normalized_green = average_rgb[1] / 255.0
    normalized_blue = average_rgb[2] / 255.0
    hue, saturation, value = colorsys.rgb_to_hsv(
        normalized_red,
        normalized_green,
        normalized_blue,
    )
    return ColorSnapshot(
        average_rgb=average_rgb,
        hue=hue,
        saturation=saturation,
        brightness=value,
        value=value,
    )
