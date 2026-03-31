"""Legacy renderer base kept as a thin compatibility wrapper."""

from heart.device import Orientation
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers.atomic import AtomicBaseRenderer
from heart.runtime.display_context import DisplayContext


class BaseRenderer(AtomicBaseRenderer[None]):
    def initialize(
        self,
        window: DisplayContext,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        if self.warmup:
            self.process(window, peripheral_manager, orientation)
        self.initialized = True

    def _internal_process(
        self,
        window: DisplayContext,
        peripheral_manager: PeripheralManager | None = None,
        orientation: Orientation | None = None,
        *args: object,
    ) -> None:
        if not self.is_initialized():
            if peripheral_manager is None or orientation is None:
                raise TypeError(
                    "BaseRenderer initialization requires peripheral_manager and orientation"
                )
            self.initialize(window, peripheral_manager, orientation)
        super()._internal_process(
            window=window,
            peripheral_manager=peripheral_manager,
            orientation=orientation,
            *args,
        )
