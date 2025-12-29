"""Exercise SlidingImage reactive outputs with marble diagrams."""

from __future__ import annotations

from dataclasses import dataclass

import pygame
import pytest
import reactivex
from reactivex import operators as ops
from reactivex.testing.marbles import marbles_testing

from heart.renderers.sliding_image.provider import SlidingImageStateProvider
from heart.renderers.sliding_image.state import SlidingImageState
from heart.utilities.reactivex_threads import pipe_in_background


@dataclass(frozen=True)
class _StubManager:
    window: reactivex.Observable[pygame.Surface | None]
    game_tick: reactivex.Observable[object]


def _render_sliding_frame(
    state: SlidingImageState,
    base_image: pygame.Surface,
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
    return frame


class TestSlidingImageMarbleOutputs:
    """Validate marble-timed SlidingImage states produce accurate output frames."""

    @pytest.mark.parametrize(
        ("speed", "tick_pattern", "expected_offsets"),
        [
            (1, "-a-b-c-d-|", [0, 1, 2, 3, 0]),
            (2, "-a-b-c-|", [0, 2, 0, 2]),
        ],
        ids=["speed-1-wrap", "speed-2-steps"],
    )
    def test_marble_stream_renders_expected_offsets(
        self,
        speed: int,
        tick_pattern: str,
        expected_offsets: list[int],
    ) -> None:
        """Ensure marbled game ticks advance slide offsets so image wraps stay correct."""

        pygame.display.set_mode((1, 1))
        base_surface = pygame.Surface((4, 1), pygame.SRCALPHA)
        colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]
        for index, color in enumerate(colors):
            base_surface.set_at((index, 0), (*color, 255))

        window_surface = pygame.Surface((4, 1), pygame.SRCALPHA)
        initial_state = SlidingImageState(speed=speed, width=4)
        provider = SlidingImageStateProvider(initial_state=initial_state)

        tick_values = {label: True for label in tick_pattern if label.isalpha()}

        with marbles_testing() as (start, cold, _hot, _exp):
            window_stream = cold("a------|", {"a": window_surface})
            tick_stream = cold(tick_pattern, tick_values)
            manager = _StubManager(window=window_stream, game_tick=tick_stream)
            image_stream = pipe_in_background(provider.observable(manager),
                ops.filter(lambda state: state.width > 0),
                ops.map(lambda state: _render_sliding_frame(state, base_surface)),
                ops.map(
                    lambda image: [
                        image.getpixel((x, 0)) for x in range(image.size[0])
                    ]
                ),
            )
            records = start(image_stream)

        images = [
            record.value.value
            for record in records
            if record.value.kind == "N"
        ]

        expected = [
            colors[offset:] + colors[:offset] for offset in expected_offsets
        ]

        assert images == expected
