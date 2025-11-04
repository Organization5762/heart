import pytest
from pytest_benchmark.fixture import BenchmarkFixture

from heart.display.renderers.pixels import RandomPixel
from heart.environment import GameLoop, RendererVariant


@pytest.mark.parametrize("num_renderers", [1, 5, 10, 25, 50, 100, 1000])
@pytest.mark.parametrize(
    "renderer_variant", [RendererVariant.BINARY, RendererVariant.ITERATIVE]
)
def test_rendering_many_objects(
    benchmark: BenchmarkFixture,
    loop: GameLoop,
    num_renderers: int,
    renderer_variant: RendererVariant,
) -> None:
    mode = loop.add_mode("Test")

    for _ in range(num_renderers):
        mode.add_renderer(RandomPixel(num_pixels=1, brightness=1))

    # https://chatgpt.com/share/68056214-a5e4-8001-8fd0-ca966dbecf9b
    benchmark(
        lambda: loop._one_loop(
            mode.renderers, override_renderer_variant=renderer_variant
        )
    )
