from heart.peripheral.core.providers import container
from heart.renderers.combined_bpm_screen.provider import \
    CombinedBpmScreenStateProvider
from heart.renderers.combined_bpm_screen.renderer import \
    CombinedBpmScreen  # noqa: F401
from heart.renderers.combined_bpm_screen.state import \
    CombinedBpmScreenState  # noqa: F401

container[CombinedBpmScreenStateProvider] = CombinedBpmScreenStateProvider
