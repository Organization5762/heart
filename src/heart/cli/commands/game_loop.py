from heart.device.selection import select_device
from heart.peripheral.core.providers import container
from heart.runtime.game_loop import GameLoop
from heart.runtime.render_pipeline import RendererVariant
from heart.utilities.env import Configuration


def build_game_loop(*, x11_forward: bool) -> GameLoop:
    render_variant = RendererVariant.parse(Configuration.render_variant())
    return GameLoop(
        device=select_device(x11_forward=x11_forward),
        resolver=container,
        render_variant=render_variant,
    )
