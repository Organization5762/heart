
import pytest
from pytest_benchmark.fixture import BenchmarkFixture

from heart.renderers.random_pixel import RandomPixel
from heart.runtime.game_loop import GameLoop, RendererVariant


class TestEnvironment:
    """Group runtime loop tests so rendering behaviour stays reliable. This preserves confidence in runtime orchestration for end-to-end scenarios."""

    @pytest.mark.parametrize("num_renderers", [1, 5, 10, 25, 50, 100, 1000])
    def test_rendering_many_objects(
        self,
        benchmark: BenchmarkFixture,
        loop: GameLoop,
        num_renderers: int,
    ) -> None:
        """Verify that rendering many objects. This keeps rendering behaviour consistent across scenes."""
        mode = loop.add_mode("Test")

        for _ in range(num_renderers):
            mode.add_renderer(RandomPixel(num_pixels=1, brightness=1))

        # https://chatgpt.com/share/68056214-a5e4-8001-8fd0-ca966dbecf9b
        benchmark(
            lambda: loop._one_loop(
                mode.renderers
            )
        )
