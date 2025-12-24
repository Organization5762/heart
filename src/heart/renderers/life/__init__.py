from heart.peripheral.core.providers import container
from heart.renderers.life.provider import LifeStateProvider

container[LifeStateProvider] = LifeStateProvider
