from heart.peripheral.core.providers import register_provider

from .provider import MainSwitchProvider

register_provider(MainSwitchProvider, MainSwitchProvider)
