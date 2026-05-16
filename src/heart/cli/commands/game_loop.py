from heart.device.selection import select_device
from heart.runtime.container import RuntimeContainer
from heart.runtime.container.initialize import build_runtime_container
from heart.runtime.game_loop import GameLoop


def build_game_loop_container() -> RuntimeContainer:
    device = select_device()
    return build_runtime_container(device=device)


def build_game_loop() -> GameLoop:
    resolver = build_game_loop_container()
    return resolver.resolve(GameLoop)
