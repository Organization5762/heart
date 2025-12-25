from heart.peripheral.core.providers import register_provider
from heart.renderers.porthole_window.provider import \
    PortholeWindowStateProvider
from heart.renderers.porthole_window.renderer import \
    PortholeWindowRenderer  # noqa: F401

register_provider(PortholeWindowStateProvider, PortholeWindowStateProvider)
