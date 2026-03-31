from __future__ import annotations

import time
from dataclasses import replace
from typing import Any, Generic, TypeVar

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.peripheral.core.manager import PeripheralManager
from heart.runtime.display_context import DisplayContext
from heart.utilities.logging import get_logger

logger = get_logger(__name__)

StateT = TypeVar("StateT")


class AtomicBaseRenderer(Generic[StateT]):
    """Base renderer that manages an immutable state snapshot."""

    def __init__(self, *args, **kwargs) -> None:
        self.initialized = False
        self._state: StateT | None = None
        self.device_display_mode = DeviceDisplayMode.MIRRORED

    @property
    def state(self) -> StateT:
        assert self._state is not None
        return self._state

    def set_state(self, state: StateT) -> None:
        self._state = state

    def update_state(self, **changes: Any) -> None:
        assert self._state is not None
        self._state = replace(self._state, **changes)

    @property
    def name(self) -> str:
        return self.__class__.__name__

    def is_initialized(self) -> bool:
        return self.initialized

    def get_renderers(self) -> list["AtomicBaseRenderer[StateT]"]:
        return [self]

    def real_process(
        self,
        window: DisplayContext,
        orientation: Orientation,
    ) -> None:
        raise NotImplementedError("Please implement")

    def _internal_process(
        self,
        window: DisplayContext,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        if not self.is_initialized():
            raise ValueError("Needs to be initialized")

        start_ns = time.perf_counter_ns()
        self.real_process(window=window, orientation=orientation)
        duration_ms = (time.perf_counter_ns() - start_ns) / 1_000_000
        logger.debug(
            "renderer.frame",
            extra={
                "renderer": self.name,
                "duration_ms": duration_ms,
            },
        )

    def reset(self):
        pass
