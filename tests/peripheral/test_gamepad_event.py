from __future__ import annotations

from collections import deque

import pytest

from heart.peripheral.gamepad.gamepad import Gamepad


class _StubJoystick:
    def __init__(self) -> None:
        self.buttons = [0, 0]
        self.axes = [0.0]
        self.hat = (0, 0)

    def get_numbuttons(self) -> int:
        return len(self.buttons)

    def get_numaxes(self) -> int:
        return len(self.axes)

    def get_button(self, index: int) -> int:
        return self.buttons[index]

    def get_axis(self, index: int) -> float:
        return self.axes[index]

    def get_hat(self, index: int) -> tuple[int, int]:
        assert index == 0
        return self.hat

    def get_name(self) -> str:
        return "8BitDo Lite 2"

    def init(self) -> None:  # pragma: no cover - not exercised in tests
        return None

    def quit(self) -> None:  # pragma: no cover - not exercised in tests
        return None


class TestPeripheralGamepadEvent:
    """Group Peripheral Gamepad Event Bus tests so peripheral gamepad event bus behaviour stays reliable. This preserves confidence in peripheral gamepad event bus for end-to-end scenarios."""

    def test_gamepad_update_emits_bus_events(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify that gamepad update emits bus events. This ensures input actions propagate to gameplay logic in real time."""
        from heart.peripheral.gamepad import gamepad as gamepad_module

        tick_sequence = deque([0, 100, 200, 300])

        monkeypatch.setattr(gamepad_module.pygame.event, "pump", lambda: None)
        monkeypatch.setattr(gamepad_module.pygame.time, "get_ticks", lambda: tick_sequence.popleft())

        joystick = _StubJoystick()
        captured: list[tuple[str, dict, int]] = []

        # for event_type in (Gamepad.EVENT_BUTTON, Gamepad.EVENT_AXIS, Gamepad.EVENT_DPAD):
        #     subscribe(
        #         event_type,
        #         lambda event, et=event_type: captured.append(
        #             (et, event.data, event.producer_id)
        #         ),
        #     )

        gamepad = Gamepad(joystick_id=3, joystick=joystick)

        joystick.buttons = [1, 0]
        joystick.axes = [0.5]
        joystick.hat = (1, 0)
        gamepad._update()

        assert (Gamepad.EVENT_BUTTON, {"button": 0, "pressed": True}, 3) in captured
        assert (Gamepad.EVENT_AXIS, {"axis": 0, "value": 0.5}, 3) in captured
        assert (Gamepad.EVENT_DPAD, {"x": 1, "y": 0}, 3) in captured

        previous_len = len(captured)
        gamepad._update()  # No state changes; should not emit new events
        assert len(captured) == previous_len

        joystick.buttons = [0, 0]
        joystick.axes = [0.0]
        joystick.hat = (0, 0)
        gamepad._update()

        assert (Gamepad.EVENT_BUTTON, {"button": 0, "pressed": False}, 3) in captured
        assert (Gamepad.EVENT_AXIS, {"axis": 0, "value": 0.0}, 3) in captured
        assert (Gamepad.EVENT_DPAD, {"x": 0, "y": 0}, 3) in captured

        # entry = state_store.get_latest(Gamepad.EVENT_BUTTON, producer_id=3)
        entry = None
        assert entry is not None
        assert entry.data == {"button": 0, "pressed": False}
