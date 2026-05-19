"""Validate the minimal OpenGL transition test program wiring."""

from heart import DeviceDisplayMode
from heart.navigation.debug_cycle import TotemDebugCycle
from heart.programs.configurations.gl_test import configure
from heart.renderers.palette_tunnel import PaletteTunnelScene
from heart.renderers.text import TextRendering


def test_gl_test_bounces_between_shader_and_pygame_modes(loop) -> None:
    configure(loop)

    entries = loop.components.game_modes.state.entries

    assert len(entries) == 2
    shader_renderer = entries[0].renderer.renderers[0]
    pygame_renderers = entries[1].renderer.renderers
    assert isinstance(shader_renderer, PaletteTunnelScene)
    assert shader_renderer.device_display_mode == DeviceDisplayMode.OPENGL
    assert any(isinstance(renderer, TextRendering) for renderer in pygame_renderers)
    assert entries[1].renderer.device_display_mode == DeviceDisplayMode.MIRRORED
    assert any(
        isinstance(renderer, TotemDebugCycle)
        for renderer in loop.components.game_modes.state.post_processors
    )
