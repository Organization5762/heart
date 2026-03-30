import pygame

from heart.peripheral.core.manager import PeripheralManager
from heart.runtime.display_context import DisplayContext
from heart.runtime.rendering.pipeline import RendererVariant, RenderPipeline


def _solid_surface(color: tuple[int, int, int]) -> pygame.Surface:
    surface = pygame.Surface((8, 8), pygame.SRCALPHA)
    surface.fill(color)
    return surface


class _StubExecutor:
    def __init__(self) -> None:
        self.map_called = False

    def map(self, fn, items):
        self.map_called = True
        return [fn(item) for item in items]


class TestRenderPipeline:
    """Verify render pipeline execution stays direct so render orchestration remains easier to follow and change."""

    def test_render_returns_surface_directly(
        self,
        device,
        monkeypatch,
        render_merge_strategy_in_place,
    ) -> None:
        """Verify RenderPipeline returns the composed surface directly. This matters because callers should not need a wrapper object to access the only useful render result."""
        pipeline = RenderPipeline(
            DisplayContext(device=device, screen=pygame.Surface((8, 8))),
            PeripheralManager(),
            render_variant=RendererVariant.ITERATIVE,
        )
        surfaces = iter(
            [
                _solid_surface((255, 0, 0)),
                _solid_surface((0, 0, 255)),
            ]
        )
        monkeypatch.setattr(pipeline, "process_renderer", lambda _renderer: next(surfaces))

        result = pipeline.render([object(), object()])

        assert isinstance(result, pygame.Surface)
        assert result.get_at((0, 0))[:3] == (0, 0, 255)

    def test_render_skips_missing_surfaces(
        self,
        device,
        monkeypatch,
        render_merge_strategy_in_place,
    ) -> None:
        """Verify RenderPipeline ignores `None` renderer outputs. This matters because renderer failures should degrade by dropping a frame contribution instead of breaking the whole merge path."""
        pipeline = RenderPipeline(
            DisplayContext(device=device, screen=pygame.Surface((8, 8))),
            PeripheralManager(),
            render_variant=RendererVariant.ITERATIVE,
        )
        surfaces = iter([None, _solid_surface((10, 20, 30))])
        monkeypatch.setattr(pipeline, "process_renderer", lambda _renderer: next(surfaces))

        result = pipeline.render([object(), object()])

        assert isinstance(result, pygame.Surface)
        assert result.get_at((0, 0))[:3] == (10, 20, 30)

    def test_binary_variant_uses_executor_collection(
        self,
        device,
        monkeypatch,
        render_merge_strategy_in_place,
    ) -> None:
        """Verify the binary render path uses the shared executor. This matters because the binary variant exists to parallelize renderer work instead of routing through another wrapper layer."""
        pipeline = RenderPipeline(
            DisplayContext(device=device, screen=pygame.Surface((8, 8))),
            PeripheralManager(),
            render_variant=RendererVariant.BINARY,
        )
        executor = _StubExecutor()
        surfaces = iter(
            [
                _solid_surface((1, 2, 3)),
                _solid_surface((4, 5, 6)),
            ]
        )
        monkeypatch.setattr(pipeline, "_get_render_executor", lambda: executor)
        monkeypatch.setattr(pipeline, "process_renderer", lambda _renderer: next(surfaces))

        result = pipeline.render([object(), object()])

        assert executor.map_called is True
        assert isinstance(result, pygame.Surface)
