import os
import sys
import types

import pytest

from heart.device import Cube, Device
from heart.environment import GameLoop
from heart.peripheral.core.manager import PeripheralManager


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
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    loop = GameLoop(device=device, peripheral_manager=manager)
    # We just initialize the PyGame screen because peripherals and the fact that we expect, in practice,
    # for this to be a singleton _shouldn't_ be that important for testing
    loop._initialize_screen()
    return loop
