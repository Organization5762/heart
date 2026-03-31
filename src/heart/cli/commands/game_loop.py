from heart.device.selection import select_device
from heart.runtime.container import RuntimeContainer
from heart.runtime.container.initialize import build_runtime_container
from heart.runtime.game_loop import GameLoop


def build_game_loop_container(*, x11_forward: bool) -> RuntimeContainer:
    device = select_device(x11_forward=x11_forward)
    return build_runtime_container(device=device)


def build_game_loop(*, x11_forward: bool) -> GameLoop:
    resolver = build_game_loop_container(x11_forward=x11_forward)
    return resolver.resolve(GameLoop)
