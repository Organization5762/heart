from heart.display.renderers.heart_title_screen.provider import \
    HeartTitleScreenStateProvider
from heart.display.renderers.heart_title_screen.renderer import \
    HeartTitleScreen  # noqa: F401
from heart.peripheral.core.providers import container

container[HeartTitleScreenStateProvider] = HeartTitleScreenStateProvider
