"""Validate 2026 library configuration details."""

from heart.display.color import Color
from heart.programs.configurations.lib_2026 import configure
from heart.renderers.text import TextRendering


def test_centered_titles_use_kirby_color(loop) -> None:
    configure(loop)

    fractal_entry = next(
        entry
        for entry in loop.components.game_modes.state.entries
        if isinstance(entry.title_renderer, TextRendering)
        and entry.title_renderer._provider._text == ("3d\nfractal",)
    )

    assert fractal_entry.title_renderer._provider._color == Color.kirby()


def test_spectrum_title_uses_smaller_pixel_font(loop) -> None:
    configure(loop)

    spectrum_entry = next(
        entry
        for entry in loop.components.game_modes.state.entries
        if isinstance(entry.title_renderer, TextRendering)
        and entry.title_renderer._provider._text == ("spectrum",)
    )
    title_renderer = spectrum_entry.title_renderer

    assert isinstance(title_renderer, TextRendering)
    assert title_renderer._provider._font_size == 12
