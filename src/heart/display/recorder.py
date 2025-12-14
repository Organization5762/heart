"""Utilities for recording :class:`~heart.environment.GameLoop` output."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING

import pygame
from PIL import Image

if TYPE_CHECKING:  # pragma: no cover - import cycle guard
    from heart.environment import GameLoop
    from heart.renderers import BaseRenderer


class ScreenRecorder:
    """Record frames produced by a :class:`~heart.environment.GameLoop`.

    The recorder advances the provided ``GameLoop`` through a sequence of
    renderer batches, captures the resulting screen for each step, and writes an
    animated GIF to ``output_path``.  GIF provides a simple, dependency-light
    container that behaves like a video when inspected during development.
    """

    def __init__(self, loop: "GameLoop", *, fps: int = 30) -> None:
        if fps <= 0:
            raise ValueError("fps must be a positive integer")
        self._loop = loop
        self._fps = fps

    @property
    def fps(self) -> int:
        """Frames per second used for the recorded animation."""

        return self._fps

    def record(
        self,
        inputs: Iterable[Sequence["BaseRenderer"] | list["BaseRenderer"]],
        output_path: str | Path,
    ) -> Path:
        """Record the screen for each batch of ``inputs``.

        Parameters
        ----------
        inputs:
            Iterable of renderer sequences.  Each sequence represents the
            renderers that should run for a single frame.
        output_path:
            Destination for the generated GIF.
        """

        path = Path(output_path)
        frames: list[Image.Image] = []

        for batch in inputs:
            renderers = list(batch)
            self._loop._one_loop(renderers)  # noqa: SLF001 - exercised via tests
            screen = self._loop.screen
            if screen is None:  # pragma: no cover - defensive guard
                raise RuntimeError("GameLoop screen not initialized")

            pixels = pygame.surfarray.array3d(screen).swapaxes(0, 1)
            frame = Image.fromarray(pixels, mode="RGB").copy()
            frames.append(frame)

        if not frames:
            raise ValueError("inputs must contain at least one frame")

        path.parent.mkdir(parents=True, exist_ok=True)
        # GIF durations are stored in 10 ms increments. Round to the closest
        # representable value while keeping a minimum non-zero duration.
        duration_ms = max(int(round((1000 / self._fps) / 10.0) * 10), 10)

        first, *rest = frames
        first.save(
            path,
            save_all=True,
            append_images=rest,
            format="GIF",
            duration=duration_ms,
            loop=0,
        )
        return path
