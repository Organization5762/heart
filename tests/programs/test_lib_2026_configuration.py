"""Validate 2026 library configuration details."""

from heart.display.color import Color
from heart.navigation import MultiScene
from heart.programs.configurations.lib_2026 import (
    FRIEND_BEACON_COLOR, JUICEBOX_FRIEND_BEACON_COLOR, configure)
from heart.renderers.bird_flock import BirdFlockRenderer
from heart.renderers.controller_pairing import ControllerPairingRenderer
from heart.renderers.mandelbrot.scene import MandelbrotMode
from heart.renderers.mandelbulb import MandelbulbScene
from heart.renderers.text import TextRendering
from heart.renderers.waving_tree import WavingTreeRenderer


def test_centered_titles_use_kirby_color(loop) -> None:
    configure(loop)

    sphere_entry = next(
        entry
        for entry in loop.components.game_modes.state.entries
        if isinstance(entry.title_renderer, TextRendering)
        and entry.title_renderer._provider._text == ("void\nsphere",)
    )

    assert sphere_entry.title_renderer._provider._color == Color.kirby()


def test_pair_bluetooth_mode_is_registered(loop) -> None:
    configure(loop)

    pair_entry = next(
        entry
        for entry in loop.components.game_modes.state.entries
        if isinstance(entry.title_renderer, TextRendering)
        and entry.title_renderer._provider._text == ("pair bt",)
    )

    assert any(
        isinstance(renderer, ControllerPairingRenderer)
        for renderer in pair_entry.renderer.renderers
    )


def test_juicebox_friend_beacon_title_is_neon_green(loop) -> None:
    configure(loop)

    friend_beacon_entry = next(
        entry
        for entry in loop.components.game_modes.state.entries
        if isinstance(entry.title_renderer, TextRendering)
        and entry.title_renderer._provider._text == ("friend\nbeacon",)
    )
    multi_scene = next(
        renderer
        for renderer in friend_beacon_entry.renderer.renderers
        if isinstance(renderer, MultiScene)
    )
    juicebox_title = next(
        scene
        for scene in multi_scene.scenes
        if scene._provider._text == ("Where's\njuicebox",)
    )
    anil_title = next(
        scene
        for scene in multi_scene.scenes
        if scene._provider._text == ("Where's\nanil",)
    )

    assert juicebox_title._provider._color == JUICEBOX_FRIEND_BEACON_COLOR
    assert anil_title._provider._color == FRIEND_BEACON_COLOR


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


def test_spectrum_title_uses_compact_pixel_font(loop) -> None:
    configure(loop)

    spectrum_entry = next(
        entry
        for entry in loop.components.game_modes.state.entries
        if isinstance(entry.title_renderer, TextRendering)
        and entry.title_renderer._provider._text == ("spectrum",)
    )
    title_renderer = spectrum_entry.title_renderer

    assert isinstance(title_renderer, TextRendering)
    assert title_renderer._provider._font_size == 10


def test_mandelbulb_mode_follows_mandelbrot(loop) -> None:
    configure(loop)

    entries = loop.components.game_modes.state.entries
    mandelbrot_index = next(
        index
        for index, entry in enumerate(entries)
        if any(
            isinstance(renderer, MandelbrotMode)
            for renderer in entry.renderer.renderers
        )
    )
    mandelbulb_entry = entries[mandelbrot_index + 1]

    assert any(
        isinstance(renderer, MandelbulbScene)
        for renderer in mandelbulb_entry.renderer.renderers
    )
    assert isinstance(mandelbulb_entry.title_renderer, TextRendering)
    assert mandelbulb_entry.title_renderer._provider._text == ("bulb",)


def test_tixyland_mode_uses_dpad_scene_selection(loop) -> None:
    configure(loop)

    tixyland_entry = next(
        entry
        for entry in loop.components.game_modes.state.entries
        if isinstance(entry.title_renderer, TextRendering)
        and entry.title_renderer._provider._text == ("tixyland",)
    )
    multi_scene = next(
        renderer
        for renderer in tixyland_entry.renderer.renderers
        if isinstance(renderer, MultiScene)
    )

    assert multi_scene._enable_dpad_scene_selection


def test_birds_mode_is_registered(loop) -> None:
    configure(loop)

    birds_entry = next(
        entry
        for entry in loop.components.game_modes.state.entries
        if isinstance(entry.title_renderer, TextRendering)
        and entry.title_renderer._provider._text == ("birds",)
    )

    assert any(
        isinstance(renderer, BirdFlockRenderer)
        for renderer in birds_entry.renderer.renderers
    )


def test_tree_mode_is_registered(loop) -> None:
    configure(loop)

    tree_entry = next(
        entry
        for entry in loop.components.game_modes.state.entries
        if isinstance(entry.title_renderer, TextRendering)
        and entry.title_renderer._provider._text == ("tree",)
    )

    assert any(
        isinstance(renderer, WavingTreeRenderer)
        for renderer in tree_entry.renderer.renderers
    )
