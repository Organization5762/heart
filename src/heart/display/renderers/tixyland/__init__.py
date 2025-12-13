from heart.display.renderers.tixyland.provider import TixylandStateProvider
from heart.display.renderers.tixyland.renderer import Tixyland  # noqa: F401
from heart.peripheral.core.providers import container

container[TixylandStateProvider] = TixylandStateProvider
