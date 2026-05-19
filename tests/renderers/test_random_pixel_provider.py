from __future__ import annotations

from heart.display.color import Color
from heart.peripheral.core.streams import EventStream
from heart.peripheral.providers.randomness import RandomnessProvider
from heart.renderers.random_pixel.provider import RandomPixelStateProvider
from heart.renderers.random_pixel.state import RandomPixelState


class FrameTickInputIo:
    def __init__(self) -> None:
        self.frames: EventStream[object] = EventStream()

    def frame_tick_stream(self) -> EventStream[object]:
        return self.frames


class RandomPixelPeripheralManager:
    def __init__(self) -> None:
        self.input_io = FrameTickInputIo()


def test_random_pixel_provider_emits_initial_state_synchronously() -> None:
    manager = RandomPixelPeripheralManager()
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
