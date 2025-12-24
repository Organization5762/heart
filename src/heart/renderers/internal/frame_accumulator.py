"""Frame accumulation utilities for renderer batching and tracing."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np
import pygame

from heart.utilities.env import Configuration, FrameArrayStrategy

_ColorInput = pygame.Color | str | tuple[int, int, int] | tuple[int, int, int, int]
_RectInput = pygame.Rect | tuple[int, int, int, int] | None


@dataclass(slots=True)
class _BlitCommand:
    surface: pygame.Surface
    dest: tuple[int, int]
    area: pygame.Rect | tuple[int, int, int, int] | None
    special_flags: int


@dataclass(slots=True)
class _FillCommand:
    color: _ColorInput
    rect: _RectInput
    special_flags: int


_Command = _BlitCommand | _FillCommand


class FrameAccumulator:
    """Collect drawing commands and flush them onto a shared surface."""

    __slots__ = ("_surface", "_commands", "_array_cache")

    def __init__(self, surface: pygame.Surface) -> None:
        self._surface = surface
        self._commands: list[_Command] = []
        self._array_cache: np.ndarray | None = None

    @classmethod
    def from_surface(
        cls, surface: pygame.Surface, *, clear: bool = True
    ) -> "FrameAccumulator":
        """Create an accumulator that reuses an existing surface."""

        if clear:
            surface.fill((0, 0, 0, 0))
        return cls(surface)

    @property
    def surface(self) -> pygame.Surface:
        """Return the underlying surface used for accumulation."""

        return self._surface

    def queue_blit(
        self,
        source: pygame.Surface,
        dest: tuple[int, int] = (0, 0),
        *,
        area: pygame.Rect | tuple[int, int, int, int] | None = None,
        special_flags: int = 0,
    ) -> None:
        """Schedule a blit operation for the next ``flush`` call."""

        self._commands.append(_BlitCommand(source, dest, area, special_flags))

    def queue_fill(
        self,
        color: _ColorInput,
        rect: _RectInput = None,
        *,
        special_flags: int = 0,
    ) -> None:
        """Schedule a fill operation for the next ``flush`` call."""

        self._commands.append(_FillCommand(color, rect, special_flags))

    def extend(self, commands: Iterable[_Command]) -> None:
        """Append a sequence of pre-built commands."""

        self._commands.extend(commands)

    def flush(
        self,
        target: pygame.Surface | None = None,
        *,
        clear: bool = True,
    ) -> pygame.Surface:
        """Apply queued commands to ``target`` (or the backing surface)."""

        destination = target or self._surface
        if clear:
            destination.fill((0, 0, 0, 0))

        pending_blits: list[
            tuple[
                pygame.Surface,
                tuple[int, int],
                pygame.Rect | tuple[int, int, int, int] | None,
                int,
            ]
        ] = []

        def flush_blits() -> None:
            if pending_blits:
                destination.blits(pending_blits)
                pending_blits.clear()

        for command in self._commands:
            if isinstance(command, _BlitCommand):
                pending_blits.append(
                    (
                        command.surface,
                        command.dest,
                        command.area,
                        command.special_flags,
                    )
                )
            else:
                flush_blits()
                destination.fill(command.color, command.rect, command.special_flags)

        flush_blits()

        self._commands.clear()
        self._array_cache = None
        return destination

    def as_array(self) -> np.ndarray:
        """Return an RGB array view of the accumulated frame."""

        if self._array_cache is None:
            if Configuration.frame_array_strategy() == FrameArrayStrategy.VIEW:
                array = pygame.surfarray.pixels3d(self._surface)
            else:
                array = pygame.surfarray.array3d(self._surface)
            self._array_cache = array.swapaxes(0, 1)
        return self._array_cache

    def reset(self) -> None:
        """Clear queued commands and cached pixels."""

        self._commands.clear()
        self._array_cache = None
