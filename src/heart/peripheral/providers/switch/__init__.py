from heart.peripheral.core.providers import container

from .provider import MainSwitchProvider

container[MainSwitchProvider] = MainSwitchProvider
