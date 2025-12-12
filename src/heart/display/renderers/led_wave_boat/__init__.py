from heart.display.renderers.led_wave_boat.provider import \
    LedWaveBoatStateProvider
from heart.display.renderers.led_wave_boat.renderer import \
    LedWaveBoat  # noqa: F401
from heart.peripheral.core.providers import container

container[LedWaveBoatStateProvider] = LedWaveBoatStateProvider
