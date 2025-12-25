from heart.peripheral.core.providers import register_provider
from heart.renderers.life.provider import LifeStateProvider

register_provider(LifeStateProvider, LifeStateProvider)
