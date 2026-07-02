from __future__ import annotations

from manyfold import ConstantNode

from heart.device import Device, Orientation
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import ObservableProvider
from heart.peripheral.core.variables import Variable
from heart.renderers.three_fractal.state import FractalSceneState
from heart.runtime.display_context import DisplayContext


class FractalSceneProvider(ObservableProvider[FractalSceneState]):
    def __init__(self, device: Device) -> None:
        self.device = device

    def initial_state(
        self,
        window: DisplayContext,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> FractalSceneState:
        from heart.renderers.three_fractal.renderer import FractalRuntime

        runtime = FractalRuntime(device=self.device)
        return FractalSceneState(runtime=runtime)

    def observable(
        self, *, initial_state: FractalSceneState
    ) -> Variable[FractalSceneState]:
        return ConstantNode(initial_state).observable()
