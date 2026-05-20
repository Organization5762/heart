from typing import Callable

import numpy as np
from manyfold import MergeNode, StreamNode

from heart.peripheral.core.input import GamepadButton, GamepadSnapshot
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.providers.randomness import RandomnessProvider
from heart.renderers.life.state import LifeState
from heart.utilities.env import Configuration


class LifeStateProvider:
    def __init__(
        self,
        peripheral_manager: PeripheralManager,
        randomness: RandomnessProvider,
    ) -> None:
        self._pm = peripheral_manager
        self._randomness = randomness

    def observable(
        self, peripheral_manager: PeripheralManager | None = None
    ) -> StreamNode[LifeState]:
        StateOp = Callable[[LifeState], LifeState]
        life_seed = Configuration.life_random_seed()
        rng = (
            LifeState.resolve_rng(life_seed)
            if life_seed is not None
            else self._randomness.numpy_rng()
        )

        def create_new_grid(size: tuple[int, int]) -> np.ndarray:
            return LifeState.random_grid(size, rng)

        def create_state(x: np.ndarray) -> LifeState:
            return LifeState(grid=x)

        def op_from_injected(new_state: LifeState) -> StateOp:
            return lambda _: new_state

        def op_from_tick(_: object) -> StateOp:
            gamepads = self._pm.input_io.gamepad.sample()
            if any(
                _should_reseed_from_gamepad(event.snapshot)
                for event in gamepads
            ):
                return lambda s: create_state(create_new_grid(s.grid.shape))
            return lambda s: s._update_grid()

        window_sizes: StreamNode[tuple[int, int]] = (
            self._pm.window.filter(lambda w: w is not None)
            .map(lambda w: w.get_size())
            .distinct_until_changed()


        )
        initial_state: StreamNode[LifeState] = (
            window_sizes.take(1).map(create_new_grid).map(create_state)
        )
        reseed_states: StreamNode[LifeState] = (
            self._pm.input_io.main_switch_stream()
            .map(lambda switch_event: switch_event.state)
            .with_latest_from(window_sizes)
            .map(lambda pair: create_new_grid(pair[1]))
            .map(create_state)


        )
        injected_states: StreamNode[LifeState] = MergeNode.merge(
            initial_state, reseed_states
        )
        operations: StreamNode[StateOp] = MergeNode.merge(
            injected_states.map(op_from_injected),
            self._pm.input_io.frame_tick_stream().map(op_from_tick),
        )
        result: StreamNode[LifeState] = initial_state.flat_map(
            lambda first_state: operations.scan(
                lambda acc, op: op(acc), seed=first_state
            )
            .start_with(first_state)

        )
        return result


def _should_reseed_from_gamepad(gamepad: GamepadSnapshot) -> bool:
    return gamepad.connected and gamepad.button_tapped(GamepadButton.PLUS)
