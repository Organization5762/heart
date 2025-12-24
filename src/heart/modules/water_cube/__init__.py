from heart.modules.water_cube.provider import WaterCubeStateProvider
from heart.peripheral.core.providers import container

container[WaterCubeStateProvider] = WaterCubeStateProvider
