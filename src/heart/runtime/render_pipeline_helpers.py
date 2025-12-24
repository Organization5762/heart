from __future__ import annotations

import enum
from typing import TYPE_CHECKING, Any, Callable, Literal

import pygame

from heart import DeviceDisplayMode
from heart.device import Device
from heart.renderers.internal import FrameAccumulator
from heart.utilities.env import Configuration
from heart.utilities.logging import get_logger

if TYPE_CHECKING:
    from heart.renderers import StatefulBaseRenderer

logger = get_logger(__name__)

RGBA_IMAGE_FORMAT: Literal["RGBA"] = "RGBA"

RenderMethod = Callable[[list["StatefulBaseRenderer[Any]"]], pygame.Surface | None]


class RendererVariant(enum.StrEnum):
    BINARY = "BINARY"
    ITERATIVE = "ITERATIVE"
    AUTO = "AUTO"
    # TODO: Add more

    @classmethod
    def parse(cls, value: str) -> "RendererVariant":
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("HEART_RENDER_VARIANT must not be empty")
        try:
            return cls[normalized]
        except KeyError as exc:
            options = ", ".join(variant.name.lower() for variant in cls)
            raise ValueError(
                f"Unknown render variant '{value}'. Expected one of: {options}"
            ) from exc


class DisplayModeManager:
    def __init__(self, device: Device) -> None:
        self._device = device
        self._last_render_mode = pygame.SHOWN

    def ensure_mode(self, display_mode: DeviceDisplayMode) -> None:
        target_mode = self._to_pygame_mode(display_mode)
        if self._last_render_mode == target_mode:
            return
        logger.info("Switching to %s mode", display_mode.name)
        pygame.display.set_mode(self._display_size(), target_mode)
        self._last_render_mode = target_mode

    def _display_size(self) -> tuple[int, int]:
        width, height = self._device.full_display_size()
        return (width * self._device.scale_factor, height * self._device.scale_factor)

    @staticmethod
    def _to_pygame_mode(display_mode: DeviceDisplayMode) -> int:
        if display_mode == DeviceDisplayMode.OPENGL:
            return pygame.OPENGL | pygame.DOUBLEBUF
        return pygame.SHOWN


class SurfaceComposer:
    def __init__(self) -> None:
        self._composite_surface_cache: dict[tuple[int, int], pygame.Surface] = {}
        self._composite_accumulator: FrameAccumulator | None = None

    def compose_batched(self, surfaces: list[pygame.Surface]) -> pygame.Surface:
        size = surfaces[0].get_size()
        composite = self._get_composite_surface(size)
        accumulator = self._get_composite_accumulator(composite)
        for surface in surfaces:
            accumulator.queue_blit(surface)
        return accumulator.flush(clear=False)

    def _get_composite_surface(self, size: tuple[int, int]) -> pygame.Surface:
        if not Configuration.render_screen_cache_enabled():
            surface = pygame.Surface(size, pygame.SRCALPHA)
            surface.fill((0, 0, 0, 0))
            return surface

        cached = self._composite_surface_cache.get(size)
        if cached is None:
            cached = pygame.Surface(size, pygame.SRCALPHA)
            self._composite_surface_cache[size] = cached
        cached.fill((0, 0, 0, 0))
        return cached

    def _get_composite_accumulator(
        self, surface: pygame.Surface
    ) -> FrameAccumulator:
        if (
            self._composite_accumulator is None
            or self._composite_accumulator.surface is not surface
        ):
            self._composite_accumulator = FrameAccumulator(surface)
        else:
            self._composite_accumulator.reset()
        return self._composite_accumulator
