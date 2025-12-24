from heart.peripheral.core.providers import container
from heart.renderers.modules.devices.switch.provider import MainSwitchProvider

container[MainSwitchProvider] = MainSwitchProvider
