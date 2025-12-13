from heart.display.renderers.l_system.provider import \
    LSystemStateProvider  # noqa: F401
from heart.display.renderers.l_system.renderer import LSystem  # noqa: F401
from heart.display.renderers.l_system.state import LSystemState  # noqa: F401
from heart.peripheral.core.providers import container

container[LSystemStateProvider] = LSystemStateProvider
