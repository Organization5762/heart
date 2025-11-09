from __future__ import annotations

from collections.abc import Callable

from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.switch import SwitchState


class SwitchStateConsumer:
    """Utility mixin that maintains cached main switch state."""

    def __init__(self) -> None:
        self._switch_state: SwitchState | None = None
        self._switch_unsubscribe: Callable[[], None] | None = None

    def bind_switch(self, peripheral_manager: PeripheralManager) -> None:
        """Subscribe to main switch state updates."""

        if self._switch_unsubscribe is not None:
            return
        self._switch_state = peripheral_manager.get_main_switch_state()
        self._switch_unsubscribe = peripheral_manager.subscribe_main_switch(
            self._handle_switch_update
        )

    def unbind_switch(self) -> None:
        """Remove the active subscription, if any."""

        if self._switch_unsubscribe is None:
            return
        self._switch_unsubscribe()
        self._switch_unsubscribe = None
        self._switch_state = None

    def get_switch_state(self) -> SwitchState:
        """Return the most recent switch state snapshot."""

        if self._switch_state is None:
            raise RuntimeError("Switch state has not been initialized")
        return self._switch_state

    # ------------------------------------------------------------------
    # Hooks for subclasses
    # ------------------------------------------------------------------
    def on_switch_state(self, state: SwitchState) -> None:
        """Hook invoked after the cached state is updated."""

    def _handle_switch_update(self, state: SwitchState) -> None:
        self._switch_state = state
        self.on_switch_state(state)
