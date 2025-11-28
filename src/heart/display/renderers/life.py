import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np
import pygame
import reactivex
from pygame import Surface
from pygame.time import Clock
from reactivex import Observable
from reactivex import operators as ops
from scipy.ndimage import convolve

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.display.renderers import StatefulBaseRenderer, StateT
from heart.peripheral.core.manager import PeripheralManager


@dataclass
class LifeState:
    grid: np.ndarray
    cache_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    kernel: np.ndarray | None = field(default=None)

    def _update_grid(self) -> Any:
        kernel = self.kernel
        if kernel is None:
            kernel = np.array([[1, 1, 1], [1, 0, 1], [1, 1, 1]])
        
        # Count the number of neighbors
        neighbors = convolve(self.grid, kernel, mode="constant", cval=0)
        new_grid = (neighbors == 3) | (self.grid & (neighbors == 2))

        assert new_grid.shape == self.grid.shape, "Grid size must match"

        new_grid =  new_grid.astype(int)
        return LifeState(grid=new_grid, cache_id=self.cache_id)


class Life(StatefulBaseRenderer[LifeState]):
    def __init__(self) -> None:
        super().__init__()
        # AtomicBaseRenderer reinitializes device_display_mode; restore FULL to
        # preserve the original renderer behaviour of operating on the entire
        # device surface rather than the per-tile mirrored view.
        self.device_display_mode = DeviceDisplayMode.FULL

    def real_process(
        self,
        window: Surface,
        clock: Clock,
        orientation: Orientation,
    ) -> None:
        # if 1, make white, else make black
        # We need to project these all to 3 dimenesions
        updated_colors = np.repeat(self.state.grid[:, :, np.newaxis], 3, axis=2) * 255
        pygame.surfarray.blit_array(window, updated_colors)

        assert self.state.grid.shape == window.get_size(), "Grid size must match window size"

    def state_observable(
        self,
        peripheral_manager: PeripheralManager,
    ) -> Observable[StateT]:
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
        window_sizes: Observable[tuple[int, int]] = (
            peripheral_manager.window.pipe(
                ops.map(lambda w: w.get_size()),
                ops.distinct_until_changed(),
                ops.share(),
            )
        )

        # We create an initial state
        initial_state: Observable[LifeState] = window_sizes.pipe(
            ops.take(1),
            ops.map(create_new_grid),
            ops.map(create_state),
        )

        # If the button changes, reseed the state
        reseed_states: Observable[LifeState] = (
            peripheral_manager.get_main_switch_subscription().pipe(
                ops.with_latest_from(window_sizes),
                ops.map(lambda pair: create_new_grid((pair[1]))),
                ops.map(create_state),
                ops.share(),
            )
        )


        # Combine the initial + concat state
        injected_states: Observable[LifeState] = reactivex.merge(
            initial_state,
            reseed_states
        )

        # Merge the initial state + update streams
        operations: Observable[StateOp] = reactivex.merge(
            injected_states.pipe(
                ops.map(op_from_injected),
            ),
            peripheral_manager.game_tick.pipe(
                ops.map(op_from_tick),
            )
        )


        result: Observable[LifeState] = initial_state.pipe(
            ops.flat_map(
                lambda first_state: operations.pipe(
                    ops.scan(lambda acc, op: op(acc), seed=first_state),
                    ops.start_with(first_state),
                )
            ),
            ops.share(),
        )

        return result        