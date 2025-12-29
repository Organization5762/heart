import sys
import types
from collections import deque
from typing import Callable

import pygame
import pytest
from hypothesis import HealthCheck, settings

from heart.device import Cube, Device
from heart.peripheral.core.manager import PeripheralManager
from heart.runtime.container import RuntimeContainer
from heart.runtime.container.initialize import build_runtime_container
from heart.runtime.game_loop import GameLoop
from heart.runtime.rendering.pipeline import RendererVariant

settings.register_profile(
    "default",
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
settings.load_profile("default")


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
def default_render_merge_strategy(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set the default render merge strategy to keep tests deterministic."""

    monkeypatch.setenv("HEART_RENDER_MERGE_STRATEGY", "batched")
    yield


@pytest.fixture(autouse=True)
def default_reactivex_stream_coalesce_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Disable stream coalescing for deterministic reactive tests; mutates env vars per test."""

    monkeypatch.setenv("HEART_RX_STREAM_COALESCE_WINDOW_MS", "0")
    yield


@pytest.fixture()
def render_merge_strategy_in_place(monkeypatch: pytest.MonkeyPatch) -> None:
    """Opt into in-place merge strategy for tests that assert pairwise merges."""

    monkeypatch.setenv("HEART_RENDER_MERGE_STRATEGY", "in_place")
    yield

@pytest.fixture(autouse=True)
def init_pygame() -> None:
    pygame.init()
    yield
    pygame.quit()


@pytest.fixture(autouse=True, scope="session")
def configure_sdl_video_driver() -> None:
    """Force pygame to use the dummy SDL driver so headless tests remain stable."""

    patcher = pytest.MonkeyPatch()
    patcher.setenv("SDL_VIDEODRIVER", "dummy")
    try:
        yield
    finally:
        patcher.undo()


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
def resolver(device: Device) -> RuntimeContainer:
    return build_runtime_container(
        device=device,
        render_variant=RendererVariant.ITERATIVE,
    )


@pytest.fixture()
def loop(manager, device, resolver) -> GameLoop:
    loop = GameLoop(device=device, resolver=resolver)
    # We just initialize the PyGame screen because peripherals and the fact that we expect, in practice,
    # for this to be a singleton _shouldn't_ be that important for testing
    loop._initialize_screen()
    return loop
