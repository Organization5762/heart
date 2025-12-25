from heart.peripheral.core.providers import register_provider
from heart.renderers.combined_bpm_screen.provider import \
    CombinedBpmScreenStateProvider
from heart.renderers.combined_bpm_screen.renderer import \
    CombinedBpmScreen  # noqa: F401
from heart.renderers.combined_bpm_screen.state import \
    CombinedBpmScreenState  # noqa: F401

register_provider(CombinedBpmScreenStateProvider, CombinedBpmScreenStateProvider)
