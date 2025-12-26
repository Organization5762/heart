from heart.device.selection import select_device
from heart.runtime.container import RuntimeContainer, build_runtime_container
from heart.runtime.game_loop import GameLoop
from heart.runtime.render_pipeline import RendererVariant
from heart.utilities.env import Configuration


def build_game_loop_container(*, x11_forward: bool) -> RuntimeContainer:
    render_variant = RendererVariant.parse(Configuration.render_variant())
    device = select_device(x11_forward=x11_forward)
    return build_runtime_container(
        device=device,
        render_variant=render_variant,
    )


def build_game_loop(*, x11_forward: bool) -> GameLoop:
    resolver = build_game_loop_container(x11_forward=x11_forward)
    return resolver.resolve(GameLoop)
