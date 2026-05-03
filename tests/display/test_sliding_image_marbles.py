"""Exercise SlidingImage stream outputs with marble diagrams."""

from __future__ import annotations

import pygame
import pytest
from manyfold._rx.testing.marbles import marbles_testing

from heart.peripheral.core.input import FrameTick
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers.sliding_image.provider import SlidingImageStateProvider
from heart.renderers.sliding_image.state import SlidingImageState


def _render_sliding_frame(
    state: SlidingImageState, base_image: pygame.Surface
) -> pygame.Surface:
    if state.width <= 0:
        raise ValueError("State width must be positive for rendering")
    height = base_image.get_height()
    scaled_image = pygame.transform.scale(base_image, (state.width, height))
    frame = pygame.Surface((state.width, height), pygame.SRCALPHA)
    frame.fill((0, 0, 0, 0))
    offset = state.offset
    width = state.width
    frame.blit(scaled_image, (-offset, 0))
    if offset:
        frame.blit(scaled_image, (width - offset, 0))
    return frame.copy()


class TestSlidingImageMarbleOutputs:
    """Validate marble-timed SlidingImage states produce accurate output frames."""

    @pytest.mark.parametrize(
        ("speed", "tick_pattern", "expected_offsets"),
        [(1, "-a-b-c-d-|", [0, 1, 2, 3, 0]), (2, "-a-b-c-|", [0, 2, 0, 2])],
        ids=["speed-1-wrap", "speed-2-steps"],
    )
    def test_marble_stream_renders_expected_offsets(
        self,
        monkeypatch: pytest.MonkeyPatch,
        speed: int,
        tick_pattern: str,
        expected_offsets: list[int],
    ) -> None:
        """Ensure marbled frame ticks advance slide offsets so image wraps stay correct."""
        pygame.display.set_mode((1, 1))
        base_surface = pygame.Surface((4, 1), pygame.SRCALPHA)
        colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]
        for index, color in enumerate(colors):
            base_surface.set_at((index, 0), (*color, 255))
        initial_state = SlidingImageState(speed=speed, width=4)
        provider = SlidingImageStateProvider(initial_state=initial_state)
        tick_values = {label: True for label in tick_pattern if label.isalpha()}
        with marbles_testing() as (start, cold, _hot, _exp):
            tick_stream = (
                cold(tick_pattern, tick_values)
                .map_indexed(
                    lambda _tick, frame_index: FrameTick(
                        frame_index=frame_index,
                        delta_ms=0.0,
                        delta_s=0.0,
                        monotonic_s=float(frame_index),
                        fps=None,
                    )
                )
                .share()
            )
            manager = PeripheralManager()
            monkeypatch.setattr(
                manager.frame_tick_controller,
                "observable",
                lambda: tick_stream,
            )
            image_stream = (
                provider.observable(manager)
                .filter(lambda state: state.width > 0)
                .map(lambda state: _render_sliding_frame(state, base_surface))
                .map(
                    lambda image: [
                        image.get_at((x, 0))[:3] for x in range(image.get_width())
                    ]
                )
                .share()
            )
            records = start(lambda: image_stream)
        images = [record.value.value for record in records if record.value.kind == "N"]
        expected = [colors[offset:] + colors[:offset] for offset in expected_offsets]
        assert images == expected
