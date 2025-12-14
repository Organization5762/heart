from heart.peripheral.core.providers import container
from heart.renderers.heart_title_screen.provider import \
    HeartTitleScreenStateProvider
from heart.renderers.heart_title_screen.renderer import \
    HeartTitleScreen  # noqa: F401

container[HeartTitleScreenStateProvider] = HeartTitleScreenStateProvider
