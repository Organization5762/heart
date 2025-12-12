from heart.display.renderers.water_title_screen.provider import \
    WaterTitleScreenStateProvider
from heart.display.renderers.water_title_screen.renderer import \
    WaterTitleScreen  # noqa: F401
from heart.peripheral.core.providers import container

container[WaterTitleScreenStateProvider] = WaterTitleScreenStateProvider
