import types

import pygame
import pytest
from pytest_benchmark.fixture import BenchmarkFixture

from heart.display.renderers.pixels import RandomPixel
from heart.environment import GameLoop, RendererVariant
from heart.peripheral.core import events


@pytest.mark.parametrize("num_renderers", [1, 5, 10, 25, 50, 100, 1000])
@pytest.mark.parametrize(
    "renderer_variant", [RendererVariant.BINARY, RendererVariant.ITERATIVE]
)
def test_rendering_many_objects(
    benchmark: BenchmarkFixture,
    loop: GameLoop,
    num_renderers: int,
    renderer_variant: RendererVariant,
) -> None:
    mode = loop.add_mode("Test")

    for _ in range(num_renderers):
        mode.add_renderer(RandomPixel(num_pixels=1, brightness=1))

    # https://chatgpt.com/share/68056214-a5e4-8001-8fd0-ca966dbecf9b
    benchmark(
        lambda: loop._one_loop(
            mode.renderers, override_renderer_variant=renderer_variant
        )
    )


def test_game_loop_shares_event_bus_with_manager(loop: GameLoop) -> None:
    assert loop.peripheral_manager.event_bus is loop.event_bus


def test_handle_events_emits_to_event_bus(loop: GameLoop, monkeypatch) -> None:
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


def test_handle_events_emits_custom_system_event(loop: GameLoop, monkeypatch) -> None:
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
