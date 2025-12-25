from __future__ import annotations

from typing import Generic

import pygame
from reactivex import Observable
from reactivex.disposable import Disposable

from heart.device import Orientation
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import (ObservableProvider,
                                             StaticStateProvider)
from heart.renderers.atomic import AtomicBaseRenderer, StateT


class StatefulBaseRenderer(AtomicBaseRenderer[StateT], Generic[StateT]):
    def __init__(
        self,
        builder: ObservableProvider[StateT] | None = None,
        state: StateT | None = None,
        *args,
        **kwargs,
    ) -> None:
        if builder is not None and state is not None:
            raise ValueError("StatefulBaseRenderer accepts a builder or state, not both")

        if builder is None and state is not None:
            builder = StaticStateProvider(state)

        self.builder = builder
        self._subscription: Disposable | None = None
        super().__init__(*args, **kwargs)

    def state_observable(
        self,
        peripheral_manager: PeripheralManager,
    ) -> Observable[StateT]:
        assert self.builder is not None
        return self.builder.observable()

    def initialize(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        if self.builder is not None:
            observable = self.state_observable(
                peripheral_manager=peripheral_manager,
            )
            self._subscription = observable.subscribe(on_next=self.set_state)
            if self.warmup:
                screen = self._get_input_screen(window, orientation)
                self.process(screen, clock, peripheral_manager, orientation)
            self.initialized = True
            return

        if not hasattr(self, "_create_initial_state"):
            msg = "StatefulBaseRenderer requires a builder or _create_initial_state"
            raise ValueError(msg)

        state = self._create_initial_state(
            window=window,
            clock=clock,
            peripheral_manager=peripheral_manager,
            orientation=orientation,
        )
        self.set_state(state)
        if self.warmup:
            screen = self._get_input_screen(window, orientation)
            self.process(screen, clock, peripheral_manager, orientation)
        self.initialized = True

    def reset(self):
        if self._subscription is not None:
            self._subscription.dispose()
            self._subscription = None
        super().reset()
