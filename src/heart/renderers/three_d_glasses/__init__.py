from heart.peripheral.core.providers import register_provider
from heart.renderers.three_d_glasses.provider import \
    ThreeDGlassesStateProvider as ThreeDGlassesStateProvider
from heart.renderers.three_d_glasses.renderer import \
    ThreeDGlassesRenderer as ThreeDGlassesRenderer
from heart.renderers.three_d_glasses.state import \
    ThreeDGlassesState as ThreeDGlassesState

register_provider(ThreeDGlassesStateProvider, ThreeDGlassesStateProvider)
