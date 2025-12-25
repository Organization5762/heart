from heart.peripheral.core.providers import register_provider
from heart.renderers.l_system.provider import \
    LSystemStateProvider  # noqa: F401
from heart.renderers.l_system.renderer import LSystem  # noqa: F401
from heart.renderers.l_system.state import LSystemState  # noqa: F401

register_provider(LSystemStateProvider, LSystemStateProvider)
