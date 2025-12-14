from heart.peripheral.core.providers import container
from heart.renderers.water_title_screen.provider import \
    WaterTitleScreenStateProvider
from heart.renderers.water_title_screen.renderer import \
    WaterTitleScreen  # noqa: F401

container[WaterTitleScreenStateProvider] = WaterTitleScreenStateProvider
