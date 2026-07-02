from __future__ import annotations

from heart.display.color import Color
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.providers.randomness import RandomnessProvider
from heart.renderers.random_pixel.provider import RandomPixelStateProvider
from heart.renderers.random_pixel.state import RandomPixelState


def test_random_pixel_provider_emits_initial_state_synchronously() -> None:
    manager = PeripheralManager()
    provider = RandomPixelStateProvider(
        width=8,
        height=8,
        num_pixels=3,
        peripheral_manager=manager,
        initial_color=Color(1, 2, 3),
        randomness=RandomnessProvider(seed=1),
    )
    observed: list[RandomPixelState] = []

    subscription = provider.observable().subscribe(observed.append)
    try:
        assert len(observed) == 1
        assert observed[0].color == Color(1, 2, 3)
        assert observed[0].pixels.shape == (3, 2)
    finally:
        subscription.dispose()
