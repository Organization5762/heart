from contextlib import nullcontext
from unittest.mock import Mock, patch

import pytest

from heart import DeviceDisplayMode
from heart.navigation import GameModes, GameModeState
from heart.navigation import game_modes as game_modes_module


class DummyRenderer:
    def __init__(self, name: str) -> None:
        self.name = name
        self.reset_calls = 0
        self.device_display_mode = DeviceDisplayMode.FULL
        self.initialize_calls = 0

    def get_renderers(self, peripheral_manager):
        return [self]

    def initialize(self, *_args, **_kwargs) -> None:
        self.initialize_calls += 1

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


def _make_window() -> Mock:
    window = Mock()
    window.screen = None
    window.display_mode.side_effect = lambda _mode: nullcontext(window)
    return window


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

    def test_initialize_registered_renderers_reports_progress(self) -> None:
        """Verify initialization reports progress for every registered renderer so startup feedback stays accurate while scenes warm up."""
        game_modes = GameModes()
        title_renderer = DummyRenderer("title")
        mode_renderer = DummyRenderer("mode")
        post_processor = DummyRenderer("post")
        game_modes.set_state(
            GameModeState(
                title_renderers=[title_renderer],
                renderers=[mode_renderer],
                post_processors=[post_processor],
            )
        )
        window = _make_window()
        peripheral_manager = Mock()
        orientation = Mock()

        with patch.object(game_modes, "_render_initialization_progress") as progress:
            game_modes._initialize_registered_renderers(
                window=window,
                peripheral_manager=peripheral_manager,
                orientation=orientation,
            )

        assert progress.call_args_list == [
            ((window,), {"completed": 0, "total": 3}),
            ((window,), {"completed": 1, "total": 3}),
            ((window,), {"completed": 2, "total": 3}),
            ((window,), {"completed": 3, "total": 3}),
        ]
        assert title_renderer.initialize_calls == 1
        assert mode_renderer.initialize_calls == 1
        assert post_processor.initialize_calls == 1

    def test_initialize_registered_renderers_logs_failures_with_renderer_name(
        self,
    ) -> None:
        """Verify initialization logs the renderer name on failure so startup crashes identify the broken scene immediately."""
        game_modes = GameModes()
        broken_renderer = DummyRenderer("broken")
        broken_renderer.initialize = Mock(side_effect=RuntimeError("boom"))
        game_modes.set_state(
            GameModeState(
                title_renderers=[broken_renderer],
                renderers=[],
                post_processors=[],
            )
        )
        window = _make_window()
        peripheral_manager = Mock()
        orientation = Mock()

        with patch.object(game_modes_module, "logger") as logger:
            with pytest.raises(RuntimeError, match="boom"):
                game_modes._initialize_registered_renderers(
                    window=window,
                    peripheral_manager=peripheral_manager,
                    orientation=orientation,
                )

        logger.exception.assert_called_once_with(
            "Failed to initialize renderer %s",
            broken_renderer.name,
        )

    def test_render_initialization_progress_logs_terminal_bar(self) -> None:
        """Verify initialization progress logs a terminal bar so startup remains observable even when the window cannot draw the progress UI."""
        game_modes = GameModes()
        window = Mock()
        window.screen = None

        with patch.object(game_modes_module.logger, "info") as info:
            game_modes._render_initialization_progress(
                window=window,
                completed=1,
                total=4,
            )

        info.assert_called_once_with(
            "Initializing app controller components (%s of %s) [%s]",
            1,
            4,
            "######------------------",
        )


if __name__ == "__main__":
    pytest.main()
