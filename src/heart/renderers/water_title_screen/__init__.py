from heart.peripheral.core.providers import register_provider
from heart.renderers.water_title_screen.provider import \
    WaterTitleScreenStateProvider
from heart.renderers.water_title_screen.renderer import \
    WaterTitleScreen  # noqa: F401

register_provider(WaterTitleScreenStateProvider, WaterTitleScreenStateProvider)
