
import pygame
import pytest
from pytest_benchmark.fixture import BenchmarkFixture

from heart.display.renderers.pixels import RandomPixel
from heart.environment import GameLoop, RendererVariant
from heart.peripheral.core.manager import PeripheralManager
from tests.conftest import FakeFixtureDevice


class TestEnvironment:
    """Group Environment tests so environment behaviour stays reliable. This preserves confidence in environment for end-to-end scenarios."""

    @pytest.mark.parametrize("num_renderers", [1, 5, 10, 25, 50, 100, 1000])
    @pytest.mark.parametrize(
        "renderer_variant", [RendererVariant.BINARY, RendererVariant.ITERATIVE]
    )
    def test_rendering_many_objects(
        self,
        benchmark: BenchmarkFixture,
        loop: GameLoop,
        num_renderers: int,
        renderer_variant: RendererVariant,
    ) -> None:
        """Verify that rendering many objects. This keeps rendering behaviour consistent across scenes."""
        mode = loop.add_mode("Test")

        for _ in range(num_renderers):
            mode.add_renderer(RandomPixel(num_pixels=1, brightness=1))

        # https://chatgpt.com/share/68056214-a5e4-8001-8fd0-ca966dbecf9b
        benchmark(
            lambda: loop._one_loop(
                mode.renderers, override_renderer_variant=renderer_variant
            )
        )


    def test_multiple_game_loops_can_coexist(self, orientation) -> None:
        """Verify that multiple game loops can coexist. This maintains stable runtime control flow."""
        manager_one = PeripheralManager()
        device_one = FakeFixtureDevice(orientation=orientation)
        loop_one = GameLoop(device=device_one, peripheral_manager=manager_one)
        loop_one._initialize_screen()

        manager_two = PeripheralManager()
        device_two = FakeFixtureDevice(orientation=orientation)
        loop_two = GameLoop(device=device_two, peripheral_manager=manager_two)
        loop_two._initialize_screen()

        assert loop_one.device is device_one
        assert loop_two.device is device_two

        pygame.quit()
