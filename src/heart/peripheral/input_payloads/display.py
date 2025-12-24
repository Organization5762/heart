"""Display payload helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, ClassVar, Literal, Mapping

from heart.peripheral.core import Input

from .base import InputEventPayload, _normalize_timestamp

if TYPE_CHECKING:  # pragma: no cover - import for type checking only
    import pygame
    from PIL import Image


@dataclass(frozen=True, slots=True)
class DisplayFrame(InputEventPayload):
    """Raw image payload emitted by the LED matrix peripheral."""

    frame_id: int
    width: int
    height: int
    mode: str
    data: bytes
    metadata: Mapping[str, Any] | None = None

    EVENT_TYPE: ClassVar[str] = "peripheral.display.frame"
    event_type: str = EVENT_TYPE

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("DisplayFrame dimensions must be positive")
        if self.metadata is not None and not isinstance(self.metadata, Mapping):
            raise TypeError("DisplayFrame metadata must be a mapping when provided")
        if self.metadata is not None:
            object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @classmethod
    def from_image(
        cls,
        image: Image.Image,
        *,
        frame_id: int,
        metadata: Mapping[str, Any] | None = None,
    ) -> "DisplayFrame":
        from PIL import Image

        if not isinstance(image, Image.Image):
            raise TypeError("image must be a PIL.Image.Image instance")
        return cls(
            frame_id=frame_id,
            width=image.width,
            height=image.height,
            mode=image.mode,
            data=image.tobytes(),
            metadata=metadata,
        )

    def to_image(self) -> Image.Image:
        from PIL import Image

        return Image.frombytes(self.mode, (self.width, self.height), self.data)

    def to_input(self, *, timestamp: datetime | None = None) -> Input:
        return Input(
            event_type=self.event_type,
            data=self,
            timestamp=_normalize_timestamp(timestamp),
        )


@dataclass(frozen=True, slots=True)
class RendererFrame(InputEventPayload):
    """Intermediate surface snapshot emitted by renderers."""

    channel: str
    renderer: str
    frame_id: int
    width: int
    height: int
    pixel_format: Literal["RGBA", "RGB", "ARGB", "BGRA"]
    data: bytes
    metadata: Mapping[str, Any] | None = None

    EVENT_TYPE: ClassVar[str] = "display.renderer.frame"
    event_type: str = EVENT_TYPE

    def __post_init__(self) -> None:
        if not self.channel:
            raise ValueError("RendererFrame channel must be a non-empty string")
        if self.width <= 0 or self.height <= 0:
            raise ValueError("RendererFrame dimensions must be positive")
        if not self.pixel_format:
            raise ValueError("RendererFrame pixel_format must be provided")
        if not isinstance(self.data, (bytes, bytearray, memoryview)):
            raise TypeError("RendererFrame data must be a bytes-like object")
        if self.metadata is not None and not isinstance(self.metadata, Mapping):
            raise TypeError("RendererFrame metadata must be a mapping when provided")
        if isinstance(self.data, bytearray):
            object.__setattr__(self, "data", bytes(self.data))
        if isinstance(self.metadata, Mapping):
            object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @classmethod
    def from_surface(
        cls,
        channel: str,
        surface: "pygame.Surface",
        *,
        renderer: str,
        frame_id: int,
        pixel_format: Literal["RGBA", "RGB", "ARGB", "BGRA"] = "RGBA",
        metadata: Mapping[str, Any] | None = None,
    ) -> "RendererFrame":
        """Capture ``surface`` pixels into a :class:`RendererFrame` payload."""

        import pygame

        if not isinstance(surface, pygame.Surface):
            raise TypeError("surface must be a pygame.Surface instance")
        if pixel_format not in {"RGBA", "RGB", "ARGB", "BGRA"}:
            raise ValueError(f"Unsupported pixel format: {pixel_format}")
        width, height = surface.get_size()
        pixels = pygame.image.tostring(surface, pixel_format)
        return cls(
            channel=channel,
            renderer=renderer,
            frame_id=frame_id,
            width=width,
            height=height,
            pixel_format=pixel_format,
            data=pixels,
            metadata=metadata,
        )

    def to_surface(self) -> "pygame.Surface":
        """Materialize the stored buffer as a :class:`pygame.Surface`."""

        import pygame

        surface = pygame.image.frombuffer(
            self.data, (self.width, self.height), self.pixel_format
        )
        # frombuffer shares the underlying memory; copy to decouple from payload
        return surface.copy()

    def to_input(self, *, timestamp: datetime | None = None) -> Input:
        return Input(
            event_type=self.event_type,
            data=self,
            timestamp=_normalize_timestamp(timestamp),
        )
