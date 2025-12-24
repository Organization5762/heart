from heart.peripheral.core.providers import container
from heart.renderers.water_cube.provider import WaterCubeStateProvider

container[WaterCubeStateProvider] = WaterCubeStateProvider
