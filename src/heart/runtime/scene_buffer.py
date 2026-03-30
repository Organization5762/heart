from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from types import ModuleType
from typing import Protocol, TypeAlias, cast, runtime_checkable

import numpy as np
import numpy.typing as npt
import pygame

from heart.utilities.logging import get_logger
from heart.utilities.optional_imports import optional_import

logger = get_logger(__name__)

SceneArray: TypeAlias = npt.NDArray[np.uint8]
ColorValue: TypeAlias = (
    pygame.Color | str | tuple[int, int, int] | tuple[int, int, int, int]
)
RectValue: TypeAlias = pygame.Rect | tuple[int, int, int, int] | None

_NATIVE_SCENE_MODULE = "heart_rust"


@runtime_checkable
class SceneCanvas(Protocol):
    """Pygame-like software scene contract for CPU renderers."""

    def blit(
        self,
        source: pygame.Surface | "SceneCanvas",
        dest: tuple[int, int] = (0, 0),
        area: RectValue = None,
        special_flags: int = 0,
    ) -> None:
        """Copy ``source`` onto this canvas."""

    def blits(
        self,
        blit_sequence: Iterable[BlitOperation],
        doreturn: bool = True,
    ) -> list[pygame.Rect] | None:
        """Copy multiple sources onto this canvas."""

    def blit_array(
        self,
        array: SceneArray,
        dest: tuple[int, int] = (0, 0),
    ) -> None:
        """Copy a surfarray-compatible array into this canvas."""

    def fill(
        self,
        color: ColorValue,
        rect: RectValue = None,
        special_flags: int = 0,
    ) -> None:
        """Fill all or part of the canvas."""

    def get_size(self) -> tuple[int, int]:
        """Return the canvas size."""

    def get_width(self) -> int:
        """Return the canvas width."""

    def get_height(self) -> int:
        """Return the canvas height."""

    def to_pygame_surface(self) -> pygame.Surface:
        """Materialize the canvas as a pygame surface."""


SceneSource: TypeAlias = pygame.Surface | SceneCanvas
BlitOperation: TypeAlias = (
    tuple[SceneSource, tuple[int, int]]
    | tuple[SceneSource, tuple[int, int], RectValue | None]
    | tuple[SceneSource, tuple[int, int], RectValue | None, int | None]
)


@dataclass(slots=True)
class PygameSceneCanvas:
    """SceneCanvas adapter backed directly by a ``pygame.Surface``."""

    surface: pygame.Surface

    def blit(
        self,
        source: SceneSource,
        dest: tuple[int, int] = (0, 0),
        area: RectValue = None,
        special_flags: int = 0,
    ) -> None:
        self.surface.blit(
            _coerce_pygame_surface(source),
            dest,
            area,
            special_flags,
        )

    def blits(
        self,
        blit_sequence: Iterable[BlitOperation],
        doreturn: bool = True,
    ) -> list[pygame.Rect] | None:
        normalized = [
            (
                _coerce_pygame_surface(operation[0]),
                operation[1],
                _blit_area(operation),
                _blit_special_flags(operation),
            )
            for operation in blit_sequence
        ]
        return self.surface.blits(normalized, doreturn=doreturn)

    def blit_array(
        self,
        array: SceneArray,
        dest: tuple[int, int] = (0, 0),
    ) -> None:
        source_surface = _array_to_surface(array)
        self.surface.blit(source_surface, dest)

    def fill(
        self,
        color: ColorValue,
        rect: RectValue = None,
        special_flags: int = 0,
    ) -> None:
        self.surface.fill(color, rect, special_flags)

    def get_size(self) -> tuple[int, int]:
        return self.surface.get_size()

    def get_width(self) -> int:
        return self.surface.get_width()

    def get_height(self) -> int:
        return self.surface.get_height()

    def to_pygame_surface(self) -> pygame.Surface:
        return self.surface


@dataclass(slots=True)
class NativeSceneCanvas:
    """SceneCanvas adapter backed by ``heart_rust.SoftwareSceneBuffer``."""

    buffer: object

    @classmethod
    def create(cls, size: tuple[int, int]) -> "NativeSceneCanvas":
        native_type = _native_scene_buffer_type()
        return cls(native_type(*size))

    def blit(
        self,
        source: SceneSource,
        dest: tuple[int, int] = (0, 0),
        area: RectValue = None,
        special_flags: int = 0,
    ) -> None:
        if special_flags != 0:
            raise ValueError("NativeSceneCanvas does not support special_flags yet.")

        normalized_area = _normalize_rect(area)
        if isinstance(source, NativeSceneCanvas):
            self.buffer.blit(source.buffer, dest, normalized_area)
            return

        source_array = _surface_to_rgba_array(_coerce_pygame_surface(source))
        if normalized_area is not None:
            x, y, width, height = normalized_area
            source_array = source_array[x : x + width, y : y + height, :]
        self.buffer.blit_array(source_array, dest)

    def blits(
        self,
        blit_sequence: Iterable[BlitOperation],
        doreturn: bool = True,
    ) -> list[pygame.Rect] | None:
        rects: list[pygame.Rect] = []
        for operation in blit_sequence:
            source = operation[0]
            dest = operation[1]
            area = _blit_area(operation)
            special_flags = _blit_special_flags(operation)
            source_surface = _coerce_pygame_surface(source)
            self.blit(
                source,
                dest,
                area,
                special_flags,
            )
            rect_size = pygame.Rect(area).size if area is not None else source_surface.get_size()
            rects.append(pygame.Rect(dest, rect_size))
        return rects if doreturn else None

    def blit_array(
        self,
        array: SceneArray,
        dest: tuple[int, int] = (0, 0),
    ) -> None:
        self.buffer.blit_array(_normalize_array(array), dest)

    def fill(
        self,
        color: ColorValue,
        rect: RectValue = None,
        special_flags: int = 0,
    ) -> None:
        if special_flags != 0:
            raise ValueError("NativeSceneCanvas does not support special_flags yet.")
        red, green, blue, alpha = _normalize_color(color)
        self.buffer.fill_rect_rgba(red, green, blue, alpha, _normalize_rect(rect))

    def get_size(self) -> tuple[int, int]:
        return cast(tuple[int, int], self.buffer.get_size())

    def get_width(self) -> int:
        return cast(int, self.buffer.get_width())

    def get_height(self) -> int:
        return cast(int, self.buffer.get_height())

    def rgba_array(self) -> SceneArray:
        return cast(SceneArray, self.buffer.rgba_array())

    def to_safetensors(self) -> bytes:
        return bytes(self.buffer.to_safetensors())

    @classmethod
    def from_safetensors(cls, payload: bytes) -> "NativeSceneCanvas":
        native_type = _native_scene_buffer_type()
        return cls(native_type.from_safetensors(payload))

    def to_pygame_surface(self) -> pygame.Surface:
        rgba_array = np.ascontiguousarray(self.rgba_array())
        surface = pygame.image.frombuffer(
            rgba_array.tobytes(),
            (self.get_width(), self.get_height()),
            "RGBA",
        )
        return surface.copy()


def build_scene_canvas(
    size: tuple[int, int],
    *,
    prefer_native: bool = True,
) -> SceneCanvas:
    """Build a CPU scene canvas, preferring the native backend when installed."""

    if prefer_native and supports_native_scene_canvas():
        return NativeSceneCanvas.create(size)
    return PygameSceneCanvas(pygame.Surface(size, pygame.SRCALPHA))


def supports_native_scene_canvas() -> bool:
    """Return whether the optional native scene buffer is installed."""

    return _load_native_scene_module() is not None


def _coerce_pygame_surface(source: SceneSource) -> pygame.Surface:
    if isinstance(source, pygame.Surface):
        return source
    return source.to_pygame_surface()


def _blit_area(operation: BlitOperation) -> RectValue:
    if len(operation) < 3:
        return None
    return operation[2]


def _blit_special_flags(operation: BlitOperation) -> int:
    if len(operation) < 4 or operation[3] is None:
        return 0
    return operation[3]


def _normalize_array(array: SceneArray) -> SceneArray:
    if array.ndim != 3 or array.shape[2] not in (3, 4):
        raise ValueError("Scene arrays must be shaped as (width, height, 3|4).")
    return np.ascontiguousarray(array.astype(np.uint8, copy=False))


def _array_to_surface(array: SceneArray) -> pygame.Surface:
    normalized = _normalize_array(array)
    width, height = normalized.shape[:2]
    surface = pygame.Surface((width, height), pygame.SRCALPHA)
    pygame.surfarray.blit_array(surface, normalized[:, :, :3])
    if normalized.shape[2] == 4:
        alpha_view = pygame.surfarray.pixels_alpha(surface)
        alpha_view[:] = normalized[:, :, 3]
        del alpha_view
    return surface


def _surface_to_rgba_array(surface: pygame.Surface) -> SceneArray:
    rgb = pygame.surfarray.array3d(surface)
    alpha = pygame.surfarray.array_alpha(surface)
    return np.dstack((rgb, alpha))


def _normalize_color(color: ColorValue) -> tuple[int, int, int, int]:
    resolved = pygame.Color(color)
    return resolved.r, resolved.g, resolved.b, resolved.a


def _normalize_rect(
    rect: RectValue,
) -> tuple[int, int, int, int] | None:
    if rect is None:
        return None
    resolved = pygame.Rect(rect)
    return resolved.x, resolved.y, resolved.width, resolved.height


def _load_native_scene_module() -> ModuleType | None:
    module = optional_import(_NATIVE_SCENE_MODULE, logger=logger)
    if module is None:
        logger.debug("Native scene buffer support is unavailable.")
        return None
    return cast(ModuleType, module)


def _native_scene_buffer_type() -> type[object]:
    module = _load_native_scene_module()
    if module is None:
        raise RuntimeError("heart_rust.SoftwareSceneBuffer is not installed.")
    native_type = getattr(module, "SoftwareSceneBuffer", None)
    if native_type is None:
        raise RuntimeError("heart_rust is missing SoftwareSceneBuffer.")
    return cast(type[object], native_type)
