"""Validate Kirby mode controls."""

from __future__ import annotations

from contextlib import nullcontext
from unittest.mock import Mock

from heart.peripheral.core.input import GamepadController, GamepadDpadValue
from heart.renderers import StatefulBaseRenderer
from heart.renderers.kirby import renderer as kirby_module
from heart.renderers.kirby.renderer import KirbyScene
from heart.renderers.kirby.state import KirbyState


class _Subscription:
    def __init__(self) -> None:
        self.dispose_calls = 0

    def dispose(self) -> None:
        self.dispose_calls += 1


class _NavigationProfile:
    def __init__(self) -> None:
        self.subscriptions: list[_Subscription] = []
        self.on_activate = None

    def subscribe_events(self, *, on_activate=None, **_kwargs):
        subscription = _Subscription()
        self.subscriptions.append(subscription)
        if on_activate is not None:
            self.on_activate = on_activate
        return subscription


class _Gamepad:
    def __init__(self) -> None:
        self.dpad = GamepadDpadValue()

    def is_connected(self) -> bool:
        return True


class _PeripheralManager:
    def __init__(self) -> None:
        self.navigation_profile = _NavigationProfile()
        self.gamepad = _Gamepad()

    def get_gamepad(self) -> _Gamepad:
        return self.gamepad


class _Scene(StatefulBaseRenderer[int]):
    def __init__(self, name: str) -> None:
        super().__init__(state=0)
        self._name = name
        self.reset_calls = 0

    @property
    def name(self) -> str:
        return self._name

    def real_process(self, *_args, **_kwargs) -> None:
        return None

    def reset(self) -> None:
        self.reset_calls += 1
        super().reset()


def _window() -> Mock:
    window = Mock()
    window.screen = None
    window.display_mode.side_effect = lambda _mode: nullcontext(window)
    return window


def _kirby_scene(monkeypatch) -> KirbyScene:
    monkeypatch.setattr(
        kirby_module.KirbyState,
        "build",
        lambda: KirbyState(
            scenes=[
                _Scene("one"),
                _Scene("two"),
                _Scene("three"),
            ]
        ),
    )
    return KirbyScene()


def _stub_dpad_read(monkeypatch) -> None:
    monkeypatch.setattr(GamepadController, "_mapping_for_gamepad", lambda _gamepad: Mock())
    monkeypatch.setattr(
        GamepadController,
        "_read_dpad",
        lambda gamepad, _mapping: gamepad.dpad,
    )


class TestKirbyScene:
    def test_dpad_right_and_left_step_through_sprite_loops(self, monkeypatch) -> None:
        _stub_dpad_read(monkeypatch)
        scene = _kirby_scene(monkeypatch)
        manager = _PeripheralManager()

        scene.initialize(
            window=_window(),
            peripheral_manager=manager,
            orientation=Mock(),
        )

        assert scene.get_renderers()[0].name == "one"
        manager.gamepad.dpad = GamepadDpadValue(x=1)
        assert scene.get_renderers()[0].name == "two"
        manager.gamepad.dpad = GamepadDpadValue()
        assert scene.get_renderers()[0].name == "two"
        manager.gamepad.dpad = GamepadDpadValue(x=-1)
        assert scene.get_renderers()[0].name == "one"

    def test_dpad_left_wraps_to_last_sprite_loop(self, monkeypatch) -> None:
        _stub_dpad_read(monkeypatch)
        scene = _kirby_scene(monkeypatch)
        manager = _PeripheralManager()

        scene.initialize(
            window=_window(),
            peripheral_manager=manager,
            orientation=Mock(),
        )
        manager.gamepad.dpad = GamepadDpadValue(x=-1)

        assert scene.get_renderers()[0].name == "three"

    def test_held_dpad_direction_does_not_repeat(self, monkeypatch) -> None:
        _stub_dpad_read(monkeypatch)
        scene = _kirby_scene(monkeypatch)
        manager = _PeripheralManager()

        scene.initialize(
            window=_window(),
            peripheral_manager=manager,
            orientation=Mock(),
        )
        manager.gamepad.dpad = GamepadDpadValue(x=1)

        assert scene.get_renderers()[0].name == "two"
        assert scene.get_renderers()[0].name == "two"

    def test_get_renderers_reads_dpad_after_warmup_reset(self, monkeypatch) -> None:
        _stub_dpad_read(monkeypatch)
        scene = _kirby_scene(monkeypatch)
        manager = _PeripheralManager()

        scene.initialize(
            window=_window(),
            peripheral_manager=manager,
            orientation=Mock(),
        )
        scene.reset()
        manager.gamepad.dpad = GamepadDpadValue(x=1)

        assert scene.initialized is False
        assert scene.get_renderers()[0].name == "two"
        assert scene.initialized is False
