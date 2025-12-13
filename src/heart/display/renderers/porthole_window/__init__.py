from heart.display.renderers.porthole_window.provider import \
    PortholeWindowStateProvider
from heart.display.renderers.porthole_window.renderer import \
    PortholeWindowRenderer  # noqa: F401
from heart.peripheral.core.providers import container

container[PortholeWindowStateProvider] = PortholeWindowStateProvider
