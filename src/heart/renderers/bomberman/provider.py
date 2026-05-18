from __future__ import annotations

import random

from manyfold import StreamNode

from heart.peripheral.core.input import GamepadSnapshot, KeyboardSnapshot
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import ObservableProvider
from heart.renderers.bomberman.state import (BombermanState,
                                             advance_bomberman_state,
                                             create_initial_bomberman_state,
                                             input_from_snapshots)


class BombermanStateProvider(ObservableProvider[BombermanState]):
    def __init__(
        self,
        *,
        rng: random.Random | None = None,
        soft_block_density: float = 0.42,
    ) -> None:
        self._rng = rng or random.Random()
        self._soft_block_density = soft_block_density

    def observable(
        self,
        peripheral_manager: PeripheralManager,
    ) -> StreamNode[BombermanState]:
        initial_state = create_initial_bomberman_state(
            rng=self._rng,
            soft_block_density=self._soft_block_density,
        )
        keyboard_stream = peripheral_manager.keyboard_controller.snapshot_stream().start_with(
            KeyboardSnapshot(pressed_keys=frozenset(), timestamp_ms=0.0)
        )
        gamepad_stream = peripheral_manager.gamepad_controller.snapshot_stream().start_with(
            GamepadSnapshot(connected=False, identifier=None)
        )

        frame_inputs = (
            peripheral_manager.frame_tick_controller.observable()
            .with_latest_from(keyboard_stream, gamepad_stream)
            .map(
                lambda latest: (
                    latest[0],
                    input_from_snapshots(latest[1], latest[2]),
                )
            )
        )

        return (
            frame_inputs.scan(
                lambda state, latest: advance_bomberman_state(
                    state,
                    latest[0],
                    latest[1],
                    rng=self._rng,
                ),
                seed=initial_state,
            )
            .start_with(initial_state)
        )
