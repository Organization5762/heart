from heart.peripheral.core.providers import container
from heart.renderers.sliding_image.provider import \
    SlidingImageStateProvider as SlidingImageStateProvider
from heart.renderers.sliding_image.provider import \
    SlidingRendererStateProvider as SlidingRendererStateProvider
from heart.renderers.sliding_image.renderer import SlidingImage as SlidingImage
from heart.renderers.sliding_image.renderer import \
    SlidingRenderer as SlidingRenderer
from heart.renderers.sliding_image.state import \
    SlidingImageState as SlidingImageState
from heart.renderers.sliding_image.state import \
    SlidingRendererState as SlidingRendererState

container[SlidingImageStateProvider] = SlidingImageStateProvider
container[SlidingRendererStateProvider] = SlidingRendererStateProvider
