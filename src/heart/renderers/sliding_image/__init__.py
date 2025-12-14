from heart.peripheral.core.providers import container
from heart.renderers.sliding_image.provider import (
    SlidingImageStateProvider, SlidingRendererStateProvider)
from heart.renderers.sliding_image.renderer import (SlidingImage,
                                                    SlidingRenderer)
from heart.renderers.sliding_image.state import (SlidingImageState,
                                                 SlidingRendererState)

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
