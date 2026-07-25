from __future__ import annotations

import numpy as np

from heart.peripheral.core.input import (GamepadButton, GamepadSnapshot,
                                         GamepadSnapshotEvent)
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.providers.randomness import RandomnessProvider
from heart.renderers.life.provider import (LifeStateProvider,
                                           _should_reseed_from_gamepad)
from heart.renderers.life.state import LifeState


class _Clock:
    def __init__(self, delta_ms: float = 16.0) -> None:
        self.delta_ms = delta_ms

    def get_time(self) -> float:
        return self.delta_ms

    def get_fps(self) -> float:
        return 60.0


class _Window:
    def __init__(self, size: tuple[int, int]) -> None:
        self._size = size

    def get_size(self) -> tuple[int, int]:
        return self._size


def test_plus_button_tap_reseeds_life_grid(monkeypatch) -> None:
    manager = PeripheralManager()
    provider = LifeStateProvider(
        peripheral_manager=manager,
        randomness=RandomnessProvider(seed=1),
    )
    snapshots = iter(
        [
            _gamepad_snapshot(),
            _gamepad_snapshot(tapped_buttons=frozenset({GamepadButton.PLUS})),
        ]
    )
    observed_states: list[LifeState] = []
    monkeypatch.setattr(
        manager.input_io.controls,
        "gamepads",
        lambda **_kwargs: (
            GamepadSnapshotEvent(joystick_id=0, snapshot=next(snapshots)),
        ),
    )

    provider.states().subscribe(observed_states.append)
    manager.window.on_next(_Window((8, 8)))
    manager.input_io.frame_ticks.advance(_Clock())
    manager.input_io.frame_ticks.advance(_Clock())

    assert len(observed_states) >= 3
    assert observed_states[-1].grid.shape == (8, 8)
    assert not np.array_equal(observed_states[-1].grid, observed_states[-2].grid)


def test_gamepad_reseed_uses_button_tap_not_held_state() -> None:
    held_snapshot = _gamepad_snapshot(buttons={GamepadButton.PLUS: True})
    tapped_snapshot = _gamepad_snapshot(tapped_buttons=frozenset({GamepadButton.PLUS}))

    assert not _should_reseed_from_gamepad(held_snapshot)
    assert _should_reseed_from_gamepad(tapped_snapshot)


def _gamepad_snapshot(
    *,
    buttons: dict[GamepadButton, bool] | None = None,
    tapped_buttons: frozenset[GamepadButton] = frozenset(),
) -> GamepadSnapshot:
    return GamepadSnapshot(
        connected=True,
        identifier="test-pad",
        buttons=buttons or {},
        tapped_buttons=tapped_buttons,
    )
