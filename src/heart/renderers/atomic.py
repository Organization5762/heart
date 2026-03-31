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
        self.warmup = True
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

    def process(
        self,
        window: DisplayContext,
        *args: Any,
        orientation: Orientation | None = None,
        **kwargs: Any,
    ) -> None:
        resolved_orientation = self._resolve_orientation(
            args=args,
            orientation=orientation,
        )
        self._invoke_real_process(window=window, orientation=resolved_orientation)

    def real_process(
        self,
        window: DisplayContext,
        orientation: Orientation,
    ) -> None:
        raise NotImplementedError("Please implement")

    def _internal_process(
        self,
        window: DisplayContext,
        peripheral_manager: PeripheralManager | None = None,
        orientation: Orientation | None = None,
        *args: Any,
    ) -> None:
        if not self.is_initialized():
            raise ValueError("Needs to be initialized")

        resolved_orientation = self._resolve_orientation(
            args=args,
            orientation=orientation,
        )
        start_ns = time.perf_counter_ns()
        self._invoke_real_process(window=window, orientation=resolved_orientation)
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

    @staticmethod
    def _resolve_orientation(
        *,
        args: tuple[Any, ...],
        orientation: Orientation | None,
    ) -> Orientation:
        if orientation is not None:
            return orientation
        if not args:
            raise TypeError("orientation is required")
        return args[-1]

    def _invoke_real_process(
        self,
        *,
        window: DisplayContext,
        orientation: Orientation,
    ) -> None:
        try:
            self.real_process(window=window, orientation=orientation)
        except TypeError as exc:
            if "clock" not in str(exc):
                raise
            try:
                self.real_process(
                    window=window,
                    clock=None,
                    orientation=orientation,
                )
            except TypeError as clock_exc:
                if "pygame.surface.Surface" not in str(clock_exc):
                    raise
                if not hasattr(window, "screen"):
                    raise
                self.real_process(
                    window=window.screen,
                    clock=None,
                    orientation=orientation,
                )
