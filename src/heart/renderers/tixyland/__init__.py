from heart.peripheral.core.providers import register_provider
from heart.renderers.tixyland.provider import TixylandStateProvider
from heart.renderers.tixyland.renderer import Tixyland  # noqa: F401

register_provider(TixylandStateProvider, TixylandStateProvider)
