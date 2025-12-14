from heart.peripheral.core.providers import container
from heart.renderers.l_system.provider import \
    LSystemStateProvider  # noqa: F401
from heart.renderers.l_system.renderer import LSystem  # noqa: F401
from heart.renderers.l_system.state import LSystemState  # noqa: F401

container[LSystemStateProvider] = LSystemStateProvider
