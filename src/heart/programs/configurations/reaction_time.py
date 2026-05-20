from heart.peripheral.providers.randomness import RandomnessProvider
from heart.renderers.reaction_time import ReactionTimeRenderer
from heart.runtime.game_loop import GameLoop


def configure(loop: GameLoop) -> None:
    mode = loop.add_mode("reaction")
    mode.add_renderer(ReactionTimeRenderer(randomness=RandomnessProvider()))
    loop.components.game_modes.state.in_select_mode = False
