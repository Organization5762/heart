from heart.peripheral.core.providers import register_singleton_provider

from .provider import RandomnessProvider

register_singleton_provider(RandomnessProvider, RandomnessProvider)
