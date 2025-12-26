from heart.peripheral.core.providers import (register_provider,
                                             register_singleton_provider)
from heart.renderers.tixyland.factory import TixylandFactory  # noqa: F401
from heart.renderers.tixyland.provider import TixylandStateProvider
from heart.renderers.tixyland.renderer import Tixyland  # noqa: F401

register_provider(TixylandStateProvider, TixylandStateProvider)
register_singleton_provider(
    TixylandFactory,
    lambda builder: TixylandFactory(lambda: builder[TixylandStateProvider]),
)
