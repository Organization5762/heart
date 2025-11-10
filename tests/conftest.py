import sys
import types
from collections import deque
from typing import Callable

import pygame
import pytest

from heart.device import Cube, Device
from heart.environment import GameLoop
from heart.peripheral.core.manager import PeripheralManager


class _StubClock:
    def __init__(
        self,
        *times: int,
        default: int = 0,
        repeat_last: bool = True,
    ) -> None:
        self._times: deque[int] = deque(times)
        self._last: int | None = None
        self._default = default
        self._repeat_last = repeat_last

    def get_time(self) -> int:
        if self._times:
            self._last = self._times.popleft()
            return self._last

        if self._repeat_last and self._last is not None:
            return self._last

        return self._default


@pytest.fixture(autouse=True)
def dummy_sdl_video_driver(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    yield


@pytest.fixture(autouse=True)
def init_pygame() -> None:
    pygame.init()
    yield
    pygame.quit()


@pytest.fixture
def enable_input_event_bus(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENABLE_INPUT_EVENT_BUS", "1")
    yield


@pytest.fixture
def stub_clock_factory() -> Callable[..., _StubClock]:
    def _factory(*times: int, **kwargs) -> _StubClock:
        return _StubClock(*times, **kwargs)

    return _factory


class _StubMode:
    def __init__(self) -> None:
        self.renderers: list[object] = []

    def add_renderer(self, renderer: object) -> None:
        self.renderers.append(renderer)


class _StubAppController:
    def __init__(self) -> None:
        self.modes: list[_StubMode] = []

    def add_mode(self, title: str | None = None) -> _StubMode:
        mode = _StubMode()
        self.modes.append(mode)
        return mode

    def add_scene(self) -> object:
        return object()

    def initialize(self, *args, **kwargs) -> None:  # pragma: no cover - stub
        return None

    def get_renderers(self, *args, **kwargs) -> list[object]:
        return self.modes[0].renderers if self.modes else []

    def is_empty(self) -> bool:
        return not self.modes


if "heart.navigation" not in sys.modules:
    navigation_stub = types.ModuleType("heart.navigation")
    navigation_stub.AppController = _StubAppController
    navigation_stub.ComposedRenderer = object
    navigation_stub.MultiScene = object
    sys.modules["heart.navigation"] = navigation_stub


class FakeFixtureDevice(Device):
    def individual_display_size(self) -> tuple[int, int]:
        return (64, 64)


@pytest.fixture()
def orientation() -> Cube:
    return Cube.sides()


@pytest.fixture()
def device(orientation) -> Device:
    return FakeFixtureDevice(orientation=orientation)


@pytest.fixture()
def manager() -> PeripheralManager:
    return PeripheralManager()


@pytest.fixture()
def loop(manager, device) -> GameLoop:
    loop = GameLoop(device=device, peripheral_manager=manager)
    # We just initialize the PyGame screen because peripherals and the fact that we expect, in practice,
    # for this to be a singleton _shouldn't_ be that important for testing
    loop._initialize_screen()
    return loop
