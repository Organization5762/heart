from heart.peripheral.core.providers import container
from heart.renderers.modules.life.provider import LifeStateProvider

container[LifeStateProvider] = LifeStateProvider
