"""Validate multicolor renderer startup behavior."""

import pygame

from heart.device import Rectangle
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers.multicolor import renderer as multicolor_module
from heart.renderers.multicolor.renderer import MulticolorRenderer
from heart.runtime.display_context import DisplayContext


def test_reinitialize_warms_pattern_generation_after_reset(monkeypatch, device) -> None:
    """Verify reset/reload paths warm the pattern again before the renderer is active."""
    calls: list[tuple[int, int, float]] = []

    def record_generate_pattern(width: int, height: int, current_time: float) -> None:
        calls.append((width, height, current_time))

    monkeypatch.setattr(
        multicolor_module,
        "generate_pattern",
        record_generate_pattern,
    )
    window = DisplayContext(device=device, screen=pygame.Surface((64, 32)))
    renderer = MulticolorRenderer()
    manager = PeripheralManager()
    orientation = Rectangle.with_layout(1, 1)

    renderer.initialize(window, manager, orientation)
    renderer.reset()
    renderer.initialize(window, manager, orientation)

    assert calls == [(64, 32, 0.0), (64, 32, 0.0)]
