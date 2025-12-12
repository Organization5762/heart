from unittest.mock import Mock, patch

import pytest

from heart.navigation import GameModes, GameModeState


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
    game_modes.set_state(GameModeState())
    game_modes.state.renderers = [DummyRenderer(f"mode-{i}") for i in range(count)]
    game_modes.state.title_renderers = [DummyRenderer(f"title-{i}") for i in range(count)]
    game_modes.state.in_select_mode = True
    game_modes.state.previous_mode_index = 0
    game_modes.state.sliding_transition = None
    game_modes.state._active_mode_index = 0
    return game_modes


class TestNavigationGameModes:
    """Group Navigation Game Modes tests so navigation game modes behaviour stays reliable. This preserves confidence in navigation game modes for end-to-end scenarios."""

    def test_active_renderer_creates_slide_transition_when_mode_changes(self) -> None:
        """Verify that active_renderer builds a slide transition when the active mode index changes. This keeps navigation animations smooth when switching between games."""
        game_modes = _make_game_modes(count=2)

        with patch("heart.navigation.SlideTransitionProvider") as provider_cls, patch(
            "heart.navigation.SlideTransitionRenderer"
        ) as slide_cls:
            provider = Mock()
            transition = Mock()
            provider_cls.return_value = provider
            slide_cls.return_value = transition

            game_modes.state.mode_offset = 1
            result = game_modes.state.active_renderer()

        assert result is transition
        provider_cls.assert_called_once_with(
            renderer_a=game_modes.state.title_renderers[0],
            renderer_b=game_modes.state.title_renderers[1],
            direction=1,
        )
        slide_cls.assert_called_once_with(provider)
        assert game_modes.state.previous_mode_index == 1



    def test_active_renderer_wraps_with_negative_direction(self) -> None:
        """Verify that active_renderer wraps from the first mode to the last when stepping negatively. This preserves intuitive cycling so users can scroll backwards seamlessly."""
        game_modes = _make_game_modes(count=3)

        with patch("heart.navigation.SlideTransitionProvider") as provider_cls, patch(
            "heart.navigation.SlideTransitionRenderer"
        ) as slide_cls:
            provider = Mock()
            transition = Mock()
            provider_cls.return_value = provider
            slide_cls.return_value = transition

            game_modes.state.mode_offset = -1
            result = game_modes.state.active_renderer()

        assert result is transition
        provider_cls.assert_called_once_with(
            renderer_a=game_modes.state.title_renderers[0],
            renderer_b=game_modes.state.title_renderers[-1],
            direction=-1,
        )
        slide_cls.assert_called_once_with(provider)
        assert game_modes.state.previous_mode_index == len(game_modes.state.renderers) - 1



    def test_active_renderer_returns_existing_transition_until_finished(self) -> None:
        """Verify that active_renderer reuses an in-progress transition until it completes. This avoids allocating redundant transitions that could stutter rendering."""
        game_modes = _make_game_modes(count=2)
        transition = Mock()
        transition.is_done.return_value = False
        game_modes.state.sliding_transition = transition

        game_modes.state.mode_offset = 0
        result = game_modes.state.active_renderer()

        assert result is transition
        transition.is_done.assert_called_once()



    def test_active_renderer_zero_offset_prefers_forward_steps_when_equal(self) -> None:
        """Verify that active_renderer prefers the forward direction when offsets are symmetric. This defines deterministic behaviour so inputs feel consistent."""
        game_modes = _make_game_modes(count=4)
        game_modes.state.previous_mode_index = 0
        game_modes.state._active_mode_index = 2

        with patch("heart.navigation.SlideTransitionProvider") as provider_cls, patch(
            "heart.navigation.SlideTransitionRenderer"
        ) as slide_cls:
            provider = Mock()
            transition = Mock()
            provider_cls.return_value = provider
            slide_cls.return_value = transition

            game_modes.state.mode_offset = 0
            result = game_modes.state.active_renderer()

        assert result is transition
        provider_cls.assert_called_once_with(
            renderer_a=game_modes.state.title_renderers[0],
            renderer_b=game_modes.state.title_renderers[2],
            direction=1,
        )
        slide_cls.assert_called_once_with(provider)
        assert game_modes.state.previous_mode_index == 2



    def test_active_renderer_zero_offset_prefers_shortest_wrap_direction(self) -> None:
        """Verify that active_renderer wraps in the shortest direction when the last mode is closer. This minimizes animation time so the UI responds briskly."""
        game_modes = _make_game_modes(count=4)
        game_modes.state.previous_mode_index = 0
        game_modes.state._active_mode_index = len(game_modes.state.renderers) - 1

        with patch("heart.navigation.SlideTransitionProvider") as provider_cls, patch(
            "heart.navigation.SlideTransitionRenderer"
        ) as slide_cls:
            provider = Mock()
            transition = Mock()
            provider_cls.return_value = provider
            slide_cls.return_value = transition

            game_modes.state.mode_offset = 0
            result = game_modes.state.active_renderer()

        assert result is transition
        provider_cls.assert_called_once_with(
            renderer_a=game_modes.state.title_renderers[0],
            renderer_b=game_modes.state.title_renderers[-1],
            direction=-1,
        )
        slide_cls.assert_called_once_with(provider)
        assert game_modes.state.previous_mode_index == len(game_modes.state.renderers) - 1



    def test_active_renderer_returns_title_renderer_in_select_mode(self) -> None:
        """Verify that active_renderer returns the title renderer while the UI is in select mode. This ensures selection screens stay visible while browsing options."""
        game_modes = _make_game_modes(count=2)
        game_modes.state.sliding_transition = None
        game_modes.state.previous_mode_index = 0

        game_modes.state.mode_offset = 0
        result = game_modes.state.active_renderer()

        assert result is game_modes.state.title_renderers[0]



    def test_active_renderer_returns_mode_when_not_in_select_mode(self) -> None:
        """Verify that active_renderer returns the active gameplay renderer when not in select mode. This keeps gameplay responsive once a selection is made."""
        game_modes = _make_game_modes(count=3)
        game_modes.state.in_select_mode = False
        game_modes.state.previous_mode_index = 1
        game_modes.state._active_mode_index = 1
        game_modes.state.sliding_transition = None

        game_modes.state.mode_offset = 0
        result = game_modes.state.active_renderer()

        assert result is game_modes.state.renderers[1], game_modes.state.renderers
        assert game_modes.state.previous_mode_index == 1


if __name__ == "__main__":
    pytest.main()
