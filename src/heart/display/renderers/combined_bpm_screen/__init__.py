from heart.display.renderers.combined_bpm_screen.provider import \
    CombinedBpmScreenStateProvider
from heart.display.renderers.combined_bpm_screen.renderer import \
    CombinedBpmScreen  # noqa: F401
from heart.display.renderers.combined_bpm_screen.state import \
    CombinedBpmScreenState  # noqa: F401
from heart.peripheral.core.providers import container

container[CombinedBpmScreenStateProvider] = CombinedBpmScreenStateProvider
