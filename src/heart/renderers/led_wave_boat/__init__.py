from heart.peripheral.core.providers import register_provider
from heart.renderers.led_wave_boat.provider import LedWaveBoatStateProvider
from heart.renderers.led_wave_boat.renderer import LedWaveBoat  # noqa: F401

register_provider(LedWaveBoatStateProvider, LedWaveBoatStateProvider)
