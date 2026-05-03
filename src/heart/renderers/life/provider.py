from typing import Callable

import numpy as np
from manyfold import MergeNode, StreamNode

from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.providers.randomness import RandomnessProvider
from heart.peripheral.providers.switch import MainSwitchProvider
from heart.renderers.life.state import LifeState
from heart.utilities.env import Configuration


class LifeStateProvider:
    def __init__(
        self,
        peripheral_manager: PeripheralManager,
        main_switch: MainSwitchProvider,
        randomness: RandomnessProvider,
    ) -> None:
        self._pm = peripheral_manager
        self._main_switch = main_switch
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
            return lambda s: s._update_grid()

        window_sizes: StreamNode[tuple[int, int]] = (
            self._pm.window.filter(lambda w: w is not None)
            .map(lambda w: w.get_size())
            .distinct_until_changed()
            .share()
            .share()
        )
        initial_state: StreamNode[LifeState] = (
            window_sizes.take(1).map(create_new_grid).map(create_state).share()
        )
        reseed_states: StreamNode[LifeState] = (
            self._main_switch.observable()
            .with_latest_from(window_sizes)
            .map(lambda pair: create_new_grid(pair[1]))
            .map(create_state)
            .share()
            .share()
        )
        injected_states: StreamNode[LifeState] = MergeNode.merge(
            initial_state, reseed_states
        )
        operations: StreamNode[StateOp] = MergeNode.merge(
            injected_states.map(op_from_injected).share(),
            self._pm.frame_tick_controller.observable().map(op_from_tick).share(),
        )
        result: StreamNode[LifeState] = initial_state.flat_map(
            lambda first_state: operations.scan(
                lambda acc, op: op(acc), seed=first_state
            )
            .start_with(first_state)
            .share()
        ).share()
        return result
