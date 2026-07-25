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


def _entry_by_title(loop, title: str):
    return next(
        entry
        for entry in loop.components.game_modes.state.entries
        if isinstance(entry.title_renderer, TextRendering)
        and entry.title_renderer._provider._text == (title,)
    )


def test_2026_library_registers_the_expected_interactive_modes(loop) -> None:
    configure(loop)

    pair_entry = _entry_by_title(loop, "pair bt")
    birds_entry = _entry_by_title(loop, "birds")
    tree_entry = _entry_by_title(loop, "tree")
    tixyland_entry = _entry_by_title(loop, "tixyland")

    assert any(
        isinstance(renderer, ControllerPairingRenderer)
        for renderer in pair_entry.renderer.renderers
    )
    assert any(
        isinstance(renderer, BirdFlockRenderer)
        for renderer in birds_entry.renderer.renderers
    )
    assert any(
        isinstance(renderer, WavingTreeRenderer)
        for renderer in tree_entry.renderer.renderers
    )
    tixyland = next(
        renderer
        for renderer in tixyland_entry.renderer.renderers
        if isinstance(renderer, MultiScene)
    )
    assert tixyland._enable_dpad_scene_selection

    entries = loop.components.game_modes.state.entries
    mandelbrot_index = next(
        index
        for index, entry in enumerate(entries)
        if any(
            isinstance(renderer, MandelbrotMode)
            for renderer in entry.renderer.renderers
        )
    )
    assert any(
        isinstance(renderer, MandelbulbScene)
        for renderer in entries[mandelbrot_index + 1].renderer.renderers
    )


def test_2026_library_preserves_visible_title_treatment(loop) -> None:
    configure(loop)

    assert _entry_by_title(loop, "void\nsphere").title_renderer._provider._color == (
        Color.kirby()
    )
    vibe_title = _entry_by_title(loop, "vibe").title_renderer
    assert vibe_title._provider._color == Color.kirby()
    assert vibe_title._provider._y_location == 0.3359375
    assert _entry_by_title(loop, "spectrum").title_renderer._provider._font_size == 10

    friend_entry = _entry_by_title(loop, "friend\nbeacon")
    friend_scenes = next(
        renderer
        for renderer in friend_entry.renderer.renderers
        if isinstance(renderer, MultiScene)
    ).scenes
    titles = {scene._provider._text: scene for scene in friend_scenes}
    assert (
        titles[("Where's\njuicebox",)]._provider._color == JUICEBOX_FRIEND_BEACON_COLOR
    )
    assert titles[("Where's\nanil",)]._provider._color == FRIEND_BEACON_COLOR
