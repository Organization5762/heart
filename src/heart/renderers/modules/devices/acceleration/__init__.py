from heart.peripheral.core.providers import container
from heart.renderers.modules.devices.acceleration.provider import \
    AllAccelerometersProvider

container[AllAccelerometersProvider] = AllAccelerometersProvider
