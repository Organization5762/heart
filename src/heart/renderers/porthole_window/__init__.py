from heart.peripheral.core.providers import container
from heart.renderers.porthole_window.provider import \
    PortholeWindowStateProvider
from heart.renderers.porthole_window.renderer import \
    PortholeWindowRenderer  # noqa: F401

container[PortholeWindowStateProvider] = PortholeWindowStateProvider
