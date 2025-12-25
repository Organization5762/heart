from heart.peripheral.core.providers import register_provider
from heart.renderers.heart_title_screen.provider import \
    HeartTitleScreenStateProvider
from heart.renderers.heart_title_screen.renderer import \
    HeartTitleScreen  # noqa: F401

register_provider(HeartTitleScreenStateProvider, HeartTitleScreenStateProvider)
