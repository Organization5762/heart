from heart.peripheral.core.providers import container
from heart.renderers.tixyland.provider import TixylandStateProvider
from heart.renderers.tixyland.renderer import Tixyland  # noqa: F401

container[TixylandStateProvider] = TixylandStateProvider
