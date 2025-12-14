from heart.display.renderers.sliding_image.provider import (
    SlidingImageStateProvider, SlidingRendererStateProvider)
from heart.display.renderers.sliding_image.renderer import (SlidingImage,
                                                            SlidingRenderer)
from heart.display.renderers.sliding_image.state import (SlidingImageState,
                                                         SlidingRendererState)
from heart.peripheral.core.providers import container

container[SlidingImageStateProvider] = SlidingImageStateProvider
container[SlidingRendererStateProvider] = SlidingRendererStateProvider

__all__ = [
    "SlidingImage",
    "SlidingRenderer",
    "SlidingImageState",
    "SlidingRendererState",
    "SlidingImageStateProvider",
    "SlidingRendererStateProvider",
]
