from heart.environment import GameLoop
from heart.renderers.channel_diffusion import ChannelDiffusionRenderer


def configure(loop: GameLoop) -> None:
    mode = loop.add_mode()
    mode.add_renderer(ChannelDiffusionRenderer())
