from heart.peripheral.core.providers import container
from heart.renderers.led_wave_boat.provider import LedWaveBoatStateProvider
from heart.renderers.led_wave_boat.renderer import LedWaveBoat  # noqa: F401

container[LedWaveBoatStateProvider] = LedWaveBoatStateProvider
