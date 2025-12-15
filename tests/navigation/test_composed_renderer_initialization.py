"""Ensure composed navigation initializes child renderers before processing."""

import pygame

from heart.device import Rectangle
from heart.navigation import ComposedRenderer
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers import StatefulBaseRenderer


class _ColdAtomicRenderer(StatefulBaseRenderer[int]):
    """Atomic renderer without warmup that still requires initialization."""

    def __init__(self) -> None:
        super().__init__()
        self.warmup = False

    def _create_initial_state(self, *_args, **_kwargs) -> int:
        return 0

    def real_process(self, *_args, **_kwargs) -> None:
        return None


class TestComposedRendererInitialization:
    """Validate composed renderer warms up child state even when warmup is disabled."""

    def test_initializes_child_renderer_with_warmup_disabled(self) -> None:
        """The composed renderer should initialize children regardless of warmup flags to avoid atomic errors."""

        renderer = _ColdAtomicRenderer()
        composed = ComposedRenderer([renderer])

        window = pygame.Surface((2, 2))
        composed.initialize(
            window=window,
            clock=pygame.time.Clock(),
            peripheral_manager=PeripheralManager(),
            orientation=Rectangle.with_layout(1, 1),
        )

        assert renderer.is_initialized() is True
