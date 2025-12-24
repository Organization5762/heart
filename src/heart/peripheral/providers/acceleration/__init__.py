from heart.peripheral.core.providers import container

from .provider import AllAccelerometersProvider

container[AllAccelerometersProvider] = AllAccelerometersProvider
