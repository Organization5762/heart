from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from heart.navigation import GameModes


class DummyRenderer:
    def __init__(self, name: str) -> None:
        self.name = name
        self.reset_calls = 0

    def get_renderers(self, peripheral_manager):
        return [self]

    def reset(self) -> None:
        self.reset_calls += 1


def _make_game_modes(count: int = 3) -> GameModes:
    game_modes = GameModes()
    game_modes.renderers = [DummyRenderer(f"mode-{i}") for i in range(count)]
    game_modes.title_renderers = [DummyRenderer(f"title-{i}") for i in range(count)]
    game_modes.in_select_mode = True
    game_modes.previous_mode_index = 0
    game_modes.sliding_transition = None
    game_modes._active_mode_index = 0
    return game_modes


def test_active_renderer_creates_slide_transition_when_mode_changes() -> None:
    game_modes = _make_game_modes(count=2)

    with patch("heart.navigation.SlideTransitionRenderer") as slide_cls:
        transition = Mock()
        slide_cls.return_value = transition

        result = game_modes.active_renderer(mode_offset=1)

    assert result is transition
    slide_cls.assert_called_once_with(
        renderer_A=game_modes.title_renderers[0],
        renderer_B=game_modes.title_renderers[1],
        direction=1,
    )
    assert game_modes.previous_mode_index == 1


def test_active_renderer_wraps_with_negative_direction() -> None:
    game_modes = _make_game_modes(count=3)

    with patch("heart.navigation.SlideTransitionRenderer") as slide_cls:
        transition = Mock()
        slide_cls.return_value = transition

        result = game_modes.active_renderer(mode_offset=-1)

    assert result is transition
    slide_cls.assert_called_once_with(
        renderer_A=game_modes.title_renderers[0],
        renderer_B=game_modes.title_renderers[-1],
        direction=-1,
    )
    assert game_modes.previous_mode_index == len(game_modes.renderers) - 1


def test_active_renderer_returns_existing_transition_until_finished() -> None:
    game_modes = _make_game_modes(count=2)
    transition = Mock()
    transition.is_done.return_value = False
    game_modes.sliding_transition = transition

    result = game_modes.active_renderer(mode_offset=0)

    assert result is transition
    transition.is_done.assert_called_once()


def test_active_renderer_returns_title_renderer_in_select_mode() -> None:
    game_modes = _make_game_modes(count=2)
    game_modes.sliding_transition = None
    game_modes.previous_mode_index = 0

    result = game_modes.active_renderer(mode_offset=0)

    assert result is game_modes.title_renderers[0]
    assert all(renderer.reset_calls == 1 for renderer in game_modes.renderers)


def test_active_renderer_returns_mode_when_not_in_select_mode() -> None:
    game_modes = _make_game_modes(count=3)
    game_modes.in_select_mode = False
    game_modes.previous_mode_index = 1
    game_modes._active_mode_index = 1
    game_modes.sliding_transition = None

    result = game_modes.active_renderer(mode_offset=0)

    assert result is game_modes.renderers[1]
    assert game_modes.previous_mode_index == 1


if __name__ == "__main__":
    pytest.main()
