from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FreeTextRendererState:
    text: str
    wrapped_lines: tuple[str, ...]
    window_size: tuple[int, int]
    font_size: int
    line_height: int
