from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

import numpy as np

from heart.device import Orientation
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers import StatefulBaseRenderer
from heart.renderers.sliding_image.provider import (
    SlidingImageStateProvider,
    SlidingRendererStateProvider,
)
from heart.renderers.sliding_image.state import SlidingImageState, SlidingRendererState
from heart.runtime.display_context import DisplayContext


@dataclass(frozen=True)
class SlidingImageSpec:
    renderer: SlidingRendererState
    image: SlidingImageState


class SlidingImageRenderer(StatefulBaseRenderer[SlidingImageState]):
    def __init__(self, context: DisplayContext, spec: SlidingImageSpec):
        super().__init__(context, spec.image)
        self._spec = spec

    def render(self, state: SlidingImageState) -> np.ndarray:
        return state.render()

    def reset(self) -> None:
        return self._state.reset()

    @property
    def width(self) -> int:
        return self._state.width

    @property
    def orientation(self) -> Orientation:
        return self._state.orientation


class SlidingImageSpecBuilder(Protocol):
    def __call__(self, context: DisplayContext) -> SlidingImageSpec:
        """Build a renderer spec."""


class SlidingImageSpecProvider:
    def __init__(self, peripheral_manager: PeripheralManager):
        self._peripheral_manager = peripheral_manager

    def __call__(self, context: DisplayContext) -> SlidingImageSpec:
        renderer_provider = SlidingRendererStateProvider(self._peripheral_manager)
        image_provider = SlidingImageStateProvider(self._peripheral_manager)
        return SlidingImageSpec(
            renderer=renderer_provider.observable().pipe(SlidingRendererState.parse),
            image=image_provider.observable().pipe(SlidingImageState.parse),
        )


class SlidingImageRendererFactory:
    def __init__(self, spec_provider: SlidingImageSpecProvider):
        self._spec_provider = spec_provider

    def __call__(self, context: DisplayContext) -> SlidingImageRenderer:
        return SlidingImageRenderer(context, self._spec_provider(context))


class SlidingImageRendererSpecRegistry:
    def __init__(self, spec_providers: Sequence[SlidingImageSpecProvider]):
        self._spec_providers = spec_providers

    def register(self, spec_provider: SlidingImageSpecProvider) -> None:
        self._spec_providers.append(spec_provider)
