from heart.modules.life.provider import LifeStateProvider
from heart.peripheral.core.providers import container

container[LifeStateProvider] = LifeStateProvider
