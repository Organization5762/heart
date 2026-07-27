"""Validate multi-scene renderer lifetime management."""

from __future__ import annotations

from contextlib import nullcontext
from unittest.mock import Mock

from heart.navigation import MultiScene
from heart.peripheral.core.input import (GamepadDpadValue, GamepadSnapshot,
                                         GamepadSnapshotEvent)
from heart.peripheral.core.input.profiles.navigation import ActivateIntent
from heart.renderers import StatefulBaseRenderer


class _Subscription:
    def __init__(self) -> None:
        self.dispose_calls = 0

    def dispose(self) -> None:
        self.dispose_calls += 1


class _NavigationProfile:
    def __init__(self) -> None:
        self.activate_callback = None
        self.subscription = _Subscription()

    def subscribe_events(self, *, on_activate, **_kwargs):
        self.activate_callback = on_activate
        return self.subscription


class _PeripheralManager:
    def __init__(self, *, with_gamepad: bool = False) -> None:
        self.navigation_profile = _NavigationProfile()
        self.input_io = Mock()
        self.input_io.navigation = self.navigation_profile
        self.gamepad = _Gamepad() if with_gamepad else None
        self.input_io.controls = _ControlSurface(self.gamepad or _DisconnectedGamepad())


class _Gamepad:
    def __init__(self) -> None:
        self.dpad = GamepadDpadValue()
        self.sample_include_tapped_buttons: list[bool] = []

    def sample(
        self, *, include_tapped_buttons: bool = True, source: str = "test"
    ) -> tuple[GamepadSnapshotEvent, ...]:
        del source
        self.sample_include_tapped_buttons.append(include_tapped_buttons)
        return (
            GamepadSnapshotEvent(
                joystick_id=0,
                snapshot=GamepadSnapshot(
                    connected=True,
                    identifier="pad",
                    dpad=self.dpad,
                ),
            ),
        )


class _DisconnectedGamepad:
    def sample(
        self, *, include_tapped_buttons: bool = True, source: str = "test"
    ) -> tuple[GamepadSnapshotEvent, ...]:
        del include_tapped_buttons, source
        return ()


class _ControlSurface:
    def __init__(self, gamepad: _Gamepad | _DisconnectedGamepad) -> None:
        self._gamepad = gamepad

    def gamepads(self) -> tuple[GamepadSnapshotEvent, ...]:
        return self._gamepad.sample(include_tapped_buttons=False)


class _Scene(StatefulBaseRenderer[int]):
    def __init__(self, name: str) -> None:
        super().__init__()
        self._name = name
        self.initialize_calls = 0
        self.reset_calls = 0
        self.process_calls = 0

    @property
    def name(self) -> str:
        return self._name

    def _create_initial_state(self, *_args, **_kwargs) -> int:
        self.initialize_calls += 1
        return 0

    def real_process(self, *_args, **_kwargs) -> None:
        self.process_calls += 1

    def reset(self) -> None:
        self.reset_calls += 1
        self.initialized = False
        super().reset()


def _window() -> Mock:
    window = Mock()
    window.screen = None
    window.display_mode.side_effect = lambda _mode: nullcontext(window)
    return window


class TestMultiSceneLifecycle:
    def test_initialize_does_not_eagerly_initialize_child_scenes(self) -> None:
        first = _Scene("first")
        second = _Scene("second")
        multi_scene = MultiScene([first, second])
        manager = _PeripheralManager()

        multi_scene.initialize(
            window=_window(),
            peripheral_manager=manager,
            orientation=Mock(),
        )

        assert multi_scene.initialized is True
        assert first.initialize_calls == 0
        assert second.initialize_calls == 0
        assert multi_scene.get_renderers() == [first]

    def test_scene_switch_resets_previous_active_scene(self) -> None:
        first = _Scene("first")
        second = _Scene("second")
        multi_scene = MultiScene([first, second])
        manager = _PeripheralManager()

        multi_scene.initialize(
            window=_window(),
            peripheral_manager=manager,
            orientation=Mock(),
        )
        first.initialize(
            window=_window(), peripheral_manager=manager, orientation=Mock()
        )

        assert manager.navigation_profile.activate_callback is not None
        manager.navigation_profile.activate_callback(
            ActivateIntent(source="test", request_id="scene-switch")
        )

        assert first.reset_calls == 1
        assert multi_scene.get_renderers() == [second]

    def test_reset_disposes_navigation_and_resets_child_scenes(self) -> None:
        first = _Scene("first")
        second = _Scene("second")
        multi_scene = MultiScene([first, second])
        manager = _PeripheralManager()

        multi_scene.initialize(
            window=_window(),
            peripheral_manager=manager,
            orientation=Mock(),
        )
        multi_scene.reset()

        assert manager.navigation_profile.subscription.dispose_calls == 1
        assert first.reset_calls == 1
        assert second.reset_calls == 1
        assert multi_scene.initialized is False

    def test_dpad_right_and_left_step_through_scenes(self) -> None:
        first = _Scene("first")
        second = _Scene("second")
        third = _Scene("third")
        multi_scene = MultiScene([first, second, third])
        manager = _PeripheralManager(with_gamepad=True)

        multi_scene.initialize(
            window=_window(),
            peripheral_manager=manager,
            orientation=Mock(),
        )

        assert multi_scene.get_renderers() == [first]
        manager.gamepad.dpad = GamepadDpadValue(x=1)
        assert multi_scene.get_renderers() == [second]
        manager.gamepad.dpad = GamepadDpadValue()
        assert multi_scene.get_renderers() == [second]
        assert multi_scene.get_renderers() == [second]
        manager.gamepad.dpad = GamepadDpadValue(x=-1)
        assert multi_scene.get_renderers() == [first]
        assert manager.gamepad.sample_include_tapped_buttons == [
            False,
            False,
            False,
            False,
            False,
        ]

    def test_one_frame_dpad_bounce_does_not_repeat_scene_selection(self) -> None:
        first = _Scene("first")
        second = _Scene("second")
        third = _Scene("third")
        multi_scene = MultiScene([first, second, third])
        manager = _PeripheralManager(with_gamepad=True)

        multi_scene.initialize(
            window=_window(),
            peripheral_manager=manager,
            orientation=Mock(),
        )

        manager.gamepad.dpad = GamepadDpadValue(x=1)
        assert multi_scene.get_renderers() == [second]
        manager.gamepad.dpad = GamepadDpadValue()
        assert multi_scene.get_renderers() == [second]
        manager.gamepad.dpad = GamepadDpadValue(x=1)
        assert multi_scene.get_renderers() == [second]

    def test_dpad_scene_selection_can_be_disabled(self) -> None:
        first = _Scene("first")
        second = _Scene("second")
        multi_scene = MultiScene(
            [first, second],
            enable_dpad_scene_selection=False,
        )
        manager = _PeripheralManager(with_gamepad=True)

        multi_scene.initialize(
            window=_window(),
            peripheral_manager=manager,
            orientation=Mock(),
        )
        manager.gamepad.dpad = GamepadDpadValue(x=1)

        assert multi_scene.get_renderers() == [first]

    def test_dpad_left_wraps_to_last_scene(self) -> None:
        first = _Scene("first")
        second = _Scene("second")
        third = _Scene("third")
        multi_scene = MultiScene([first, second, third])
        manager = _PeripheralManager(with_gamepad=True)

        multi_scene.initialize(
            window=_window(),
            peripheral_manager=manager,
            orientation=Mock(),
        )
        manager.gamepad.dpad = GamepadDpadValue(x=-1)

        assert multi_scene.get_renderers() == [third]

    def test_held_dpad_direction_does_not_repeat(self) -> None:
        first = _Scene("first")
        second = _Scene("second")
        third = _Scene("third")
        multi_scene = MultiScene([first, second, third])
        manager = _PeripheralManager(with_gamepad=True)

        multi_scene.initialize(
            window=_window(),
            peripheral_manager=manager,
            orientation=Mock(),
        )
        manager.gamepad.dpad = GamepadDpadValue(x=1)

        assert multi_scene.get_renderers() == [second]
        assert multi_scene.get_renderers() == [second]

    def test_get_renderers_reads_dpad_after_warmup_reset(self) -> None:
        first = _Scene("first")
        second = _Scene("second")
        multi_scene = MultiScene([first, second])
        manager = _PeripheralManager(with_gamepad=True)

        multi_scene.initialize(
            window=_window(),
            peripheral_manager=manager,
            orientation=Mock(),
        )
        multi_scene.reset()
        manager.gamepad.dpad = GamepadDpadValue(x=1)

        assert multi_scene.initialized is False
        assert multi_scene.get_renderers() == [second]
        assert multi_scene.initialized is False
