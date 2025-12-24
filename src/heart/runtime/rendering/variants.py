from __future__ import annotations

import enum
from typing import TYPE_CHECKING, Any, Callable, Literal

import pygame

if TYPE_CHECKING:
    from heart.renderers import StatefulBaseRenderer

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
