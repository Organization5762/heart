from heart.modules.devices.acceleration.provider import \
    AllAccelerometersProvider
from heart.peripheral.core.providers import container

container[AllAccelerometersProvider] = AllAccelerometersProvider
