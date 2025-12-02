from heart.modules.devices.switch.provider import MainSwitchProvider
from heart.peripheral.core.providers import container

container[MainSwitchProvider] = MainSwitchProvider
