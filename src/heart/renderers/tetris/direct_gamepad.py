from __future__ import annotations

import time
from dataclasses import dataclass, field

from heart.peripheral.core.input import (GamepadAxis, GamepadButton,
                                         GamepadDpadValue,
                                         GamepadSnapshotEvent)
from heart.peripheral.core.input.gamepad import DEFAULT_GAMEPAD_AXIS_DEAD_ZONE


@dataclass(frozen=True, slots=True)
class DirectGamepadSnapshot:
    connected: bool
    identifier: str | None
    buttons: dict[GamepadButton, bool] = field(default_factory=dict)
    tapped_buttons: frozenset[GamepadButton] = frozenset()
    axes: dict[GamepadAxis, float] = field(default_factory=dict)
    dpad: GamepadDpadValue = GamepadDpadValue()
    timestamp_monotonic: float = 0.0
    slot: int = 0

    def button_held(self, button: GamepadButton) -> bool:
        return self.buttons.get(button, False)

    def button_tapped(self, button: GamepadButton) -> bool:
        return button in self.tapped_buttons

    def axis_value(
        self,
        axis: GamepadAxis,
        *,
        dead_zone: float = DEFAULT_GAMEPAD_AXIS_DEAD_ZONE,
    ) -> float:
        value = self.axes.get(axis, 0.0)
        if abs(value) < dead_zone:
            return 0.0
        return value


class DirectTetrisGamepads:
    """Present central PubSub snapshots through Tetris's slot-based model."""

    def __init__(self) -> None:
        self._snapshots_by_slot: dict[int, DirectGamepadSnapshot] = {}

    def refresh(
        self,
        events: tuple[GamepadSnapshotEvent, ...],
        *,
        player_count: int,
    ) -> None:
        self._snapshots_by_slot = {
            event.joystick_id: _from_event(event)
            for event in events
            if event.joystick_id < player_count
        }

    def snapshot_for_slot(self, slot: int) -> DirectGamepadSnapshot:
        return self._snapshots_by_slot.get(
            slot,
            DirectGamepadSnapshot(
                connected=False,
                identifier=None,
                timestamp_monotonic=time.monotonic(),
                slot=slot,
            ),
        )


def _from_event(event: GamepadSnapshotEvent) -> DirectGamepadSnapshot:
    snapshot = event.snapshot
    return DirectGamepadSnapshot(
        connected=snapshot.connected,
        identifier=snapshot.identifier,
        buttons=snapshot.buttons,
        tapped_buttons=snapshot.tapped_buttons,
        axes=snapshot.axes,
        dpad=snapshot.dpad,
        timestamp_monotonic=snapshot.timestamp_monotonic,
        slot=event.joystick_id,
    )
