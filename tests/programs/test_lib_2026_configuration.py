"""Validate 2026 library configuration details."""

from heart.display.color import Color
from heart.programs.configurations.lib_2026 import configure
from heart.renderers.controller_pairing import ControllerPairingRenderer
from heart.renderers.mandelbrot.scene import MandelbrotMode
from heart.renderers.mandelbulb import MandelbulbScene
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


def test_vibe_title_uses_centered_kirby_title(loop) -> None:
    configure(loop)

    vibe_entry = next(
        entry
        for entry in loop.components.game_modes.state.entries
        if isinstance(entry.title_renderer, TextRendering)
        and entry.title_renderer._provider._text == ("vibe",)
    )
    title_renderer = vibe_entry.title_renderer

    assert title_renderer._provider._color == Color.kirby()
    assert title_renderer._provider._y_location == 0.3359375


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


def test_mandelbulb_mode_follows_mandelbrot(loop) -> None:
    configure(loop)

    entries = loop.components.game_modes.state.entries
    mandelbrot_index = next(
        index
        for index, entry in enumerate(entries)
        if any(isinstance(renderer, MandelbrotMode) for renderer in entry.renderer.renderers)
    )
    mandelbulb_entry = entries[mandelbrot_index + 1]

    assert any(
        isinstance(renderer, MandelbulbScene)
        for renderer in mandelbulb_entry.renderer.renderers
    )
    assert isinstance(mandelbulb_entry.title_renderer, TextRendering)
    assert mandelbulb_entry.title_renderer._provider._text == ("mandel\nbulb",)


def test_pair_bluetooth_mode_precedes_sleep(loop) -> None:
    configure(loop)
    loop.add_sleep_mode()

    entries = loop.components.game_modes.state.entries
    pair_entry = entries[-2]
    sleep_entry = entries[-1]

    assert any(
        isinstance(renderer, ControllerPairingRenderer)
        for renderer in pair_entry.renderer.renderers
    )
    assert isinstance(sleep_entry.title_renderer.renderers[-1], TextRendering)
    assert sleep_entry.title_renderer.renderers[-1]._provider._text == ("sleep",)
