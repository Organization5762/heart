
from typing import Callable

import numpy as np
import reactivex

from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.providers.switch import MainSwitchProvider
from heart.peripheral.uwb import ops
from heart.renderers.life.state import LifeState


class LifeStateProvider:
    def __init__(self, peripheral_manager: PeripheralManager, main_switch: MainSwitchProvider):
        self._pm = peripheral_manager
        self._main_switch = main_switch

    def observable(
        self,
    ) -> reactivex.Observable[LifeState]:
        StateOp = Callable[[LifeState], LifeState]
        def create_new_grid(size):
            return np.random.choice([0, 1], size=size)

        def create_state(x: np.ndarray) -> LifeState:
            return LifeState(grid=x)

        def op_from_injected(new_state: LifeState) -> StateOp:
            return lambda _: new_state

        def op_from_tick(_: object) -> StateOp:
            # Advance the simulation one step
            return lambda s: s._update_grid()

        # If the window size changes, we want to observe and correct for this
        window_sizes: reactivex.Observable[tuple[int, int]] = (
            self._pm.window.pipe(
                ops.filter(lambda w: w is not None),
                ops.map(lambda w: w.get_size()),
                ops.distinct_until_changed(),
                ops.share(),
            )
        )

        # We create an initial state
        initial_state: reactivex.Observable[LifeState] = window_sizes.pipe(
            ops.take(1),
            ops.map(create_new_grid),
            ops.map(create_state),
        )

        # If the button changes, reseed the state
        reseed_states: reactivex.Observable[LifeState] = (
            self._main_switch.observable().pipe(
                ops.with_latest_from(window_sizes),
                ops.map(lambda pair: create_new_grid((pair[1]))),
                ops.map(create_state),
                ops.share(),
            )
        )

        # Combine the initial + concat state
        injected_states: reactivex.Observable[LifeState] = reactivex.merge(
            initial_state,
            reseed_states
        )

        # Merge the initial state + update streams
        operations: reactivex.Observable[StateOp] = reactivex.merge(
            injected_states.pipe(
                ops.map(op_from_injected),
            ),
            self._pm.game_tick.pipe(
                ops.map(op_from_tick),
            )
        )

        result: reactivex.Observable[LifeState] = initial_state.pipe(
            ops.flat_map(
                lambda first_state: operations.pipe(
                    ops.scan(lambda acc, op: op(acc), seed=first_state),
                    ops.start_with(first_state),
                )
            ),
            ops.share(),
        )

        return result        
