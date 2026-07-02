from __future__ import annotations

from dataclasses import dataclass

import pygame

from heart.peripheral.core.manager import PeripheralManager
from heart.renderers.free_text.provider import FreeTextStateProvider
from heart.renderers.free_text.state import FreeTextRendererState


@dataclass(frozen=True, slots=True)
class _Clock:
    delta_ms: float = 16.0

    def get_time(self) -> float:
        return self.delta_ms

    def get_fps(self) -> float:
        return 60.0


def test_free_text_provider_uses_value_for_current_text(monkeypatch) -> None:
    provider = FreeTextStateProvider()
    manager = PeripheralManager()
    observed: list[FreeTextRendererState] = []
    font = pygame.font.Font(None, 12)
    monkeypatch.setattr(provider, "get_font", lambda _size: font)

    provider.observable(manager).subscribe(observed.append)
    manager.window.on_next(pygame.Surface((64, 32)))
    provider.set_text("hello")
    manager.input_io.frame_ticks.advance(_Clock())

    assert observed[-1].text == "hello"
    assert observed[-1].window_size == (64, 32)
