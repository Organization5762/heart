from contextlib import nullcontext

import pygame
import pytest

from heart import DeviceDisplayMode
from heart.navigation.game_modes import GameModeState, ModeEntry
from heart.renderers import StatefulBaseRenderer
from heart.runtime.game_loop import GameLoop


class _Renderer(StatefulBaseRenderer):
    def __init__(self, *, display_mode: DeviceDisplayMode) -> None:
        super().__init__()
        self.device_display_mode = display_mode
        self.reset_calls = 0

    def reset(self) -> None:
        self.reset_calls += 1
        self.initialized = False
        super().reset()


class TestGameLoop:
    """Exercise core GameLoop guardrails so lifecycle assumptions stay reliable for runtime orchestration."""

    def test_singleton_preserves_first_instance(
        self,
        device,
        resolver,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Ensure the first GameLoop remains active so global access stays predictable during runtime setup."""
        monkeypatch.setattr("heart.runtime.game_loop.ACTIVE_GAME_LOOP", None)

        first_loop = GameLoop(device=device, resolver=resolver)
        second_loop = GameLoop(device=device, resolver=resolver)

        first_loop._set_singleton()
        second_loop._set_singleton()

        assert GameLoop.get_game_loop() is first_loop

    def test_one_loop_requires_initialized_screen(self, device, resolver) -> None:
        """Confirm _one_loop refuses to run without a screen so rendering doesn't fail silently in production."""
        loop = GameLoop(device=device, resolver=resolver)

        with pytest.raises(RuntimeError, match="GameLoop screen is not initialized"):
            loop._one_loop([])

    def test_one_loop_presents_rendered_frame_to_device(
        self,
        device,
        resolver,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Ensure _one_loop forwards each rendered frame to the device so live outputs and streaming targets stay updated."""
        loop = GameLoop(device=device, resolver=resolver)
        loop.ensure_screen_initialized()
        assert loop.components.display.screen is not None

        rendered_surface = pygame.Surface(loop.components.display.screen.get_size())
        monkeypatch.setattr(loop, "render_frame", lambda renderers: rendered_surface)
        monkeypatch.setattr(loop, "_apply_post_processors", lambda surface: None)

        presented_screens: list[pygame.Surface] = []
        monkeypatch.setattr(device, "set_screen", presented_screens.append)

        loop._one_loop([])

        assert presented_screens == [loop.components.display.screen]

    def test_max_fps_can_be_overridden_by_environment(
        self,
        device,
        resolver,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Allow runtime perf experiments without editing code or changing the default cap."""
        monkeypatch.setenv("HEART_MAX_FPS", "60")

        loop = GameLoop(device=device, resolver=resolver)

        assert loop.max_fps == 60

    def test_render_frame_resets_initialized_opengl_renderers_on_display_mode_change(
        self,
        device,
        resolver,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Reset stale OpenGL resources before pygame recreates the display context."""
        loop = GameLoop(device=device, resolver=resolver)
        loop.ensure_screen_initialized()
        renderer = _Renderer(display_mode=DeviceDisplayMode.OPENGL)
        renderer.initialized = True
        loop.components.game_modes.set_state(
            GameModeState(
                entries=[ModeEntry(title_renderer=renderer, renderer=renderer)]
            )
        )
        loop.components.display.last_render_mode = (
            DeviceDisplayMode.MIRRORED.to_pygame_mode()
        )
        monkeypatch.setattr(
            loop.components.display,
            "display_mode",
            lambda _mode: nullcontext(loop.components.display),
        )
        monkeypatch.setattr(
            "heart.runtime.game_loop.ComposedRenderer.render_batch",
            lambda *args, **kwargs: None,
        )

        loop.render_frame([renderer])

        assert renderer.reset_calls == 1

    def test_render_frame_keeps_opengl_renderers_when_display_mode_is_stable(
        self,
        device,
        resolver,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Avoid reinitializing shader-backed renderers when the GL context stays alive."""
        loop = GameLoop(device=device, resolver=resolver)
        loop.ensure_screen_initialized()
        renderer = _Renderer(display_mode=DeviceDisplayMode.OPENGL)
        renderer.initialized = True
        loop.components.game_modes.set_state(
            GameModeState(
                entries=[ModeEntry(title_renderer=renderer, renderer=renderer)]
            )
        )
        loop.components.display.last_render_mode = (
            DeviceDisplayMode.OPENGL.to_pygame_mode()
        )
        monkeypatch.setattr(
            loop.components.display,
            "display_mode",
            lambda _mode: nullcontext(loop.components.display),
        )
        monkeypatch.setattr(
            "heart.runtime.game_loop.ComposedRenderer.render_batch",
            lambda *args, **kwargs: None,
        )

        loop.render_frame([renderer])

        assert renderer.reset_calls == 0
