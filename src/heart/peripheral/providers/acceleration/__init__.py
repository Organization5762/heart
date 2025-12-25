from heart.peripheral.core.providers import register_provider

from .provider import AllAccelerometersProvider

register_provider(AllAccelerometersProvider, AllAccelerometersProvider)
