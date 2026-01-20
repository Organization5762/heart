from __future__ import annotations

from dataclasses import dataclass

import reactivex
from reactivex import operators as ops

from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import ObservableProvider
from heart.renderers.sliding_image.state import SlidingImageState, SlidingRendererState
from heart.utilities.reactivex_threads import pipe_in_background


@dataclass(frozen=True)
class SlidingStateSnapshot:
    renderer: SlidingRendererState
    image: SlidingImageState


class SlidingImageStateProvider(ObservableProvider[SlidingImageState]):
    def __init__(self, peripheral_manager: PeripheralManager):
        self._peripheral_manager = peripheral_manager

    def observable(self) -> reactivex.Observable[SlidingImageState]:
        switcher_stream = pipe_in_background(
            reactivex.merge(
                *(
                    peripheral.observe
                    for peripheral in self._peripheral_manager.peripherals
                    if peripheral.device_name == "sliding-image"
                )
            ),
            ops.map(SlidingImageState.unwrap_peripheral),
        )
        return pipe_in_background(
            switcher_stream,
            ops.distinct_until_changed(),
            ops.share(),
        )


class SlidingRendererStateProvider(ObservableProvider[SlidingRendererState]):
    def __init__(self, peripheral_manager: PeripheralManager):
        self._peripheral_manager = peripheral_manager

    def observable(self) -> reactivex.Observable[SlidingRendererState]:
        stream = pipe_in_background(
            reactivex.merge(
                *(
                    peripheral.observe
                    for peripheral in self._peripheral_manager.peripherals
                    if peripheral.device_name == "sliding-renderer"
                )
            ),
            ops.map(SlidingRendererState.unwrap_peripheral),
        )
        return pipe_in_background(
            stream,
            ops.distinct_until_changed(),
            ops.share(),
        )
