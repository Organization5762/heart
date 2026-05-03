"""Render the runtime's interpreted gamepad snapshot into a pygame window."""

from __future__ import annotations

import json

import pygame

from heart.device import Rectangle
from heart.device.local import LocalScreen
from heart.peripheral.core.input import GamepadSnapshot
from heart.peripheral.core.manager import PeripheralManager
from heart.runtime.container import build_runtime_container
from heart.runtime.display_context import DisplayContext
from heart.runtime.peripheral_runtime import PeripheralRuntime
from heart.utilities.reactivex_threads import shutdown

WINDOW_WIDTH = 900
WINDOW_HEIGHT = 700
FPS = 60
BACKGROUND = (12, 12, 16)
TEXT = (235, 235, 235)
ACCENT = (120, 200, 255)
PADDING = 16
LINE_HEIGHT = 18


def _snapshot_summary(snapshot: GamepadSnapshot) -> dict[str, object]:
    active_buttons = sorted(
        button.value for button, pressed in snapshot.buttons.items() if pressed
    )
    tapped_buttons = sorted(button.value for button in snapshot.tapped_buttons)
    active_axes = {
        axis.value: round(value, 3)
        for axis, value in snapshot.axes.items()
        if abs(value) >= 0.1
    }
    return {
        "connected": snapshot.connected,
        "identifier": snapshot.identifier,
        "buttons": active_buttons,
        "tapped": tapped_buttons,
        "axes": active_axes,
        "dpad": {
            "x": snapshot.dpad.x,
            "y": snapshot.dpad.y,
        },
    }


def _draw_lines(
    surface: pygame.Surface,
    *,
    font: pygame.font.Font,
    title_font: pygame.font.Font,
    frame: int,
    summary: dict[str, object],
) -> None:
    surface.fill(BACKGROUND)

    y = PADDING
    title = title_font.render("Gamepad Probe", True, ACCENT)
    surface.blit(title, (PADDING, y))
    y += 32

    status_line = (
        f"frame={frame} connected={summary['connected']} identifier={summary['identifier']}"
    )
    surface.blit(font.render(status_line, True, TEXT), (PADDING, y))
    y += LINE_HEIGHT * 2

    for line in json.dumps(summary, indent=2, sort_keys=True).splitlines():
        rendered = font.render(line, True, TEXT)
        surface.blit(rendered, (PADDING, y))
        y += LINE_HEIGHT

    y += LINE_HEIGHT
    hint = "Press buttons / move sticks. Close window or Ctrl-C to quit."
    surface.blit(font.render(hint, True, ACCENT), (PADDING, y))


def main() -> None:
    orientation = Rectangle.with_layout(columns=1, rows=1)
    device = LocalScreen(
        width=WINDOW_WIDTH,
        height=WINDOW_HEIGHT,
        orientation=orientation,
    )
    container = build_runtime_container(device=device)
    peripheral_manager = container.resolve(PeripheralManager)
    peripheral_runtime = container.resolve(PeripheralRuntime)
    display = container.resolve(DisplayContext)

    display.initialize()
    if display.screen is None or display.clock is None:
        raise RuntimeError("Gamepad probe display did not initialize")

    pygame.display.set_caption("Heart Gamepad Probe")
    font = pygame.font.Font(None, 24)
    title_font = pygame.font.Font(None, 32)

    peripheral_manager.detect()
    peripheral_manager.start()

    latest_snapshot = GamepadSnapshot(connected=False, identifier=None)

    def _set_snapshot(snapshot: GamepadSnapshot) -> None:
        nonlocal latest_snapshot
        latest_snapshot = snapshot

    peripheral_manager.gamepad_controller.snapshot_stream().subscribe(on_next=_set_snapshot)

    running = True
    frame = 0
    try:
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

            peripheral_runtime.tick()

            _draw_lines(
                display.screen,
                font=font,
                title_font=title_font,
                frame=frame,
                summary=_snapshot_summary(latest_snapshot),
            )
            pygame.display.flip()

            display.clock.tick(FPS)
            peripheral_manager.clock.on_next(display.clock)
            peripheral_runtime.tick()
            frame += 1
    except KeyboardInterrupt:
        pass
    finally:
        shutdown.on_next(True)
        shutdown.on_completed()
        shutdown.dispose()
        pygame.quit()


if __name__ == "__main__":
    main()
