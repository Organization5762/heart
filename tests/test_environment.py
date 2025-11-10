import os
import types

import pygame
import pytest
from pytest_benchmark.fixture import BenchmarkFixture

from heart.display.renderers.pixels import RandomPixel
from heart.environment import GameLoop, RendererVariant
from heart.peripheral.core import events
from heart.peripheral.core.manager import PeripheralManager
from tests.conftest import FakeFixtureDevice


class TestEnvironment:
    """Group Environment tests so environment behaviour stays reliable. This preserves confidence in environment for end-to-end scenarios."""

    @pytest.mark.parametrize("num_renderers", [1, 5, 10, 25, 50, 100, 1000])
    @pytest.mark.parametrize(
        "renderer_variant", [RendererVariant.BINARY, RendererVariant.ITERATIVE]
    )
    def test_rendering_many_objects(
        self,
        benchmark: BenchmarkFixture,
        loop: GameLoop,
        num_renderers: int,
        renderer_variant: RendererVariant,
    ) -> None:
        """Verify that rendering many objects. This keeps rendering behaviour consistent across scenes."""
        mode = loop.add_mode("Test")

        for _ in range(num_renderers):
            mode.add_renderer(RandomPixel(num_pixels=1, brightness=1))

        # https://chatgpt.com/share/68056214-a5e4-8001-8fd0-ca966dbecf9b
        benchmark(
            lambda: loop._one_loop(
                mode.renderers, override_renderer_variant=renderer_variant
            )
        )



    def test_game_loop_shares_event_bus_with_manager(self, loop: GameLoop) -> None:
        """Verify that game loop shares event bus with manager. This ensures event orchestration remains reliable."""
        assert loop.peripheral_manager.event_bus is loop.event_bus



    def test_handle_events_emits_to_event_bus(self, loop: GameLoop, monkeypatch) -> None:
        """Verify that handle events emits to event bus. This ensures event orchestration remains reliable."""
        captured: list[dict[str, object]] = []

        loop.event_bus.subscribe("pygame/quit", lambda evt: captured.append(evt.data))

        fake_event = types.SimpleNamespace(type=pygame.QUIT, dict={})
        monkeypatch.setattr(pygame.event, "get", lambda: [fake_event])

        loop.running = True
        loop._handle_events()

        assert captured == [
            {
                "pygame_type": pygame.QUIT,
                "pygame_event_name": pygame.event.event_name(pygame.QUIT),
            }
        ]
        assert loop.running is False



    def test_handle_events_emits_custom_system_event(self, loop: GameLoop, monkeypatch) -> None:
        """Verify that handle events emits custom system event. This ensures event orchestration remains reliable."""
        captured: list[int] = []
        joystick_reset = events.REQUEST_JOYSTICK_MODULE_RESET

        loop.event_bus.subscribe(
            "system/request_joystick_module_reset", lambda evt: captured.append(evt.data["pygame_type"])
        )

        fake_event = types.SimpleNamespace(type=joystick_reset, dict={})

        calls: dict[str, int] = {"quit": 0, "init": 0}

        def _mark_quit() -> None:
            calls["quit"] += 1

        def _mark_init() -> None:
            calls["init"] += 1

        monkeypatch.setattr(pygame.joystick, "quit", _mark_quit)
        monkeypatch.setattr(pygame.joystick, "init", _mark_init)
        monkeypatch.setattr(pygame.event, "get", lambda: [fake_event])

        loop._handle_events()

        assert calls == {"quit": 1, "init": 1}
        assert captured == [joystick_reset]



    def test_handle_events_supports_missing_event_payload(self, loop: GameLoop, monkeypatch) -> None:
        """Verify that handle events supports missing event payload. This ensures event orchestration remains reliable."""
        captured: list[dict[str, object]] = []

        loop.event_bus.subscribe(
            "pygame/noevent", lambda evt: captured.append(evt.data)
        )

        fake_event = types.SimpleNamespace(type=pygame.NOEVENT, dict=None)
        monkeypatch.setattr(pygame.event, "get", lambda: [fake_event])

        loop._handle_events()

        assert captured == [
            {
                "pygame_type": pygame.NOEVENT,
                "pygame_event_name": pygame.event.event_name(pygame.NOEVENT),
            }
        ]



    def test_multiple_game_loops_can_coexist(self, orientation) -> None:
        """Verify that multiple game loops can coexist. This maintains stable runtime control flow."""
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        manager_one = PeripheralManager()
        device_one = FakeFixtureDevice(orientation=orientation)
        loop_one = GameLoop(device=device_one, peripheral_manager=manager_one)
        loop_one._initialize_screen()

        manager_two = PeripheralManager()
        device_two = FakeFixtureDevice(orientation=orientation)
        loop_two = GameLoop(device=device_two, peripheral_manager=manager_two)
        loop_two._initialize_screen()

        assert loop_one.device is device_one
        assert loop_two.device is device_two

        pygame.quit()
