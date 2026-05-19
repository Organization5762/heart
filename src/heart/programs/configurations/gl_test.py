"""Minimal OpenGL context transition test configuration."""

import os

from heart.display.color import Color
from heart.navigation.debug_cycle import TotemDebugCycle
from heart.renderers.color import RenderColor
from heart.renderers.palette_tunnel import PaletteTunnelScene
from heart.renderers.text import TextRendering
from heart.runtime.game_loop import GameLoop

DEFAULT_GL_TEST_CYCLE_SECONDS = 1.0


def configure(loop: GameLoop) -> None:
    shader_mode = loop.add_mode("gl shader")
    shader_mode.add_renderer(PaletteTunnelScene())

    pygame_mode = loop.add_mode("pygame")
    pygame_mode.add_renderer(
        RenderColor(Color(12, 18, 28)),
        TextRendering(
            text=["pygame"],
            font="Grand9K Pixel.ttf",
            font_size=12,
            color=Color(255, 105, 180),
            y_location=0.5,
        ),
    )

    post_processors = loop.components.game_modes.state.post_processors
    if not post_processors:
        post_processors.extend(loop.components.game_modes._default_post_processors())
    post_processors.append(
        TotemDebugCycle(
            loop.components.game_modes,
            interval_seconds=_cycle_seconds(),
            start_mode="gl shader",
        )
    )


def _cycle_seconds() -> float:
    raw_value = os.environ.get("HEART_GL_TEST_CYCLE_SECONDS")
    if raw_value is None:
        return DEFAULT_GL_TEST_CYCLE_SECONDS
    try:
        return float(raw_value)
    except ValueError:
        return DEFAULT_GL_TEST_CYCLE_SECONDS
