"""Validate bouncing ball playlist registration."""

from heart.programs.configurations.lib_2026 import configure
from heart.renderers.bouncing_ball import (BouncingBallRenderer,
                                           BouncingBallStateProvider)


def test_registers_bouncing_ball_mode(loop) -> None:
    configure(loop)

    entry = next(
        entry
        for entry in loop.components.game_modes.state.entries
        if any(
            isinstance(renderer, BouncingBallRenderer)
            for renderer in getattr(entry.renderer, "renderers", ())
        )
    )

    renderer = next(
        renderer
        for renderer in getattr(entry.renderer, "renderers", ())
        if isinstance(renderer, BouncingBallRenderer)
    )

    assert entry.title_renderer._provider._text == ("bounce",)
    assert isinstance(renderer.builder, BouncingBallStateProvider)
